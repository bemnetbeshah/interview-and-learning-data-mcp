"""Small single-user OAuth provider for hosted ChatGPT MCP connections."""

from __future__ import annotations

import html
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from .config import Settings
from .db import Database

READ_SCOPE = "study:read"
WRITE_SCOPE = "study:write"
VALID_SCOPES = [READ_SCOPE, WRITE_SCOPE]
SUBJECT = "bem"


@dataclass(frozen=True)
class PendingAuthorization:
    request_id: str
    client_id: str
    state: str | None
    scopes: list[str]
    code_challenge: str
    redirect_uri: str
    redirect_uri_provided_explicitly: bool
    resource: str | None
    expires_at: float


class PersonalOAuthProvider:
    """OAuth authorization server provider backed by the project database."""

    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        row = self._fetchone("SELECT client_info FROM oauth_clients WHERE client_id = ?", (client_id,))
        if not row:
            return None
        return OAuthClientInformationFull.model_validate_json(row["client_info"])

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.db.execute(
            """
            INSERT INTO oauth_clients (client_id, client_info)
            VALUES (?, ?)
            ON CONFLICT (client_id) DO UPDATE SET client_info = EXCLUDED.client_info
            """,
            (client_info.client_id, client_info.model_dump_json()),
        )
        self.db.commit()

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        if not client.client_id:
            raise AuthorizeError("invalid_request", "client_id is required")

        requested_scopes = params.scopes or VALID_SCOPES
        invalid_scopes = sorted(set(requested_scopes) - set(VALID_SCOPES))
        if invalid_scopes:
            raise AuthorizeError("invalid_scope", f"Unsupported scopes: {' '.join(invalid_scopes)}")

        request_id = secrets.token_urlsafe(32)
        self.db.execute(
            """
            INSERT INTO oauth_pending_authorizations (
                request_id, client_id, state, scopes_json, code_challenge,
                redirect_uri, redirect_uri_provided_explicitly, resource, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                client.client_id,
                params.state,
                json.dumps(requested_scopes),
                params.code_challenge,
                str(params.redirect_uri),
                bool(params.redirect_uri_provided_explicitly),
                params.resource,
                time.time() + 600,
            ),
        )
        self.db.commit()
        return f"{self.settings.public_base_url.rstrip('/')}/oauth/approve?request_id={request_id}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        row = self._fetchone(
            "SELECT * FROM oauth_authorization_codes WHERE code = ? AND used_at IS NULL",
            (authorization_code,),
        )
        if not row:
            return None
        return AuthorizationCode(
            code=row["code"],
            scopes=json.loads(row["scopes_json"]),
            expires_at=float(row["expires_at"]),
            client_id=row["client_id"],
            code_challenge=row["code_challenge"],
            redirect_uri=AnyUrl(row["redirect_uri"]),
            redirect_uri_provided_explicitly=bool(row["redirect_uri_provided_explicitly"]),
            resource=row["resource"],
            subject=row["subject"],
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self.db.execute(
            "UPDATE oauth_authorization_codes SET used_at = CURRENT_TIMESTAMP WHERE code = ?",
            (authorization_code.code,),
        )
        token = self._issue_access_token(
            client_id=authorization_code.client_id,
            scopes=authorization_code.scopes,
            resource=authorization_code.resource,
            subject=authorization_code.subject or SUBJECT,
        )
        refresh_token = self._issue_refresh_token(
            client_id=authorization_code.client_id,
            scopes=authorization_code.scopes,
            subject=authorization_code.subject or SUBJECT,
        )
        self.db.commit()
        return OAuthToken(
            access_token=token,
            expires_in=self.settings.oauth_token_ttl_seconds,
            scope=" ".join(authorization_code.scopes),
            refresh_token=refresh_token,
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        row = self._fetchone("SELECT * FROM oauth_refresh_tokens WHERE token = ?", (refresh_token,))
        if not row:
            return None
        return RefreshToken(
            token=row["token"],
            client_id=row["client_id"],
            scopes=json.loads(row["scopes_json"]),
            expires_at=int(row["expires_at"]),
            subject=row["subject"],
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if refresh_token.expires_at and refresh_token.expires_at < int(time.time()):
            raise TokenError("invalid_grant", "refresh token has expired")

        self.db.execute("DELETE FROM oauth_refresh_tokens WHERE token = ?", (refresh_token.token,))
        token = self._issue_access_token(
            client_id=refresh_token.client_id,
            scopes=scopes,
            resource=self.settings.resource_server_url,
            subject=refresh_token.subject or SUBJECT,
        )
        new_refresh_token = self._issue_refresh_token(
            client_id=refresh_token.client_id,
            scopes=scopes,
            subject=refresh_token.subject or SUBJECT,
        )
        self.db.commit()
        return OAuthToken(
            access_token=token,
            expires_in=self.settings.oauth_token_ttl_seconds,
            scope=" ".join(scopes),
            refresh_token=new_refresh_token,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = self._fetchone("SELECT * FROM oauth_access_tokens WHERE token = ?", (token,))
        if not row or int(row["expires_at"]) < int(time.time()):
            return None
        resource = row["resource"]
        if resource and resource.rstrip("/") != self.settings.resource_server_url.rstrip("/"):
            return None
        scopes = json.loads(row["scopes_json"])
        return AccessToken(
            token=row["token"],
            client_id=row["client_id"],
            scopes=scopes,
            expires_at=int(row["expires_at"]),
            resource=resource,
            subject=row["subject"],
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self.db.execute("DELETE FROM oauth_access_tokens WHERE token = ?", (token.token,))
        self.db.execute("DELETE FROM oauth_refresh_tokens WHERE token = ?", (token.token,))
        self.db.commit()

    def get_pending_authorization(self, request_id: str) -> PendingAuthorization | None:
        row = self._fetchone("SELECT * FROM oauth_pending_authorizations WHERE request_id = ?", (request_id,))
        if not row or float(row["expires_at"]) < time.time():
            return None
        return PendingAuthorization(
            request_id=row["request_id"],
            client_id=row["client_id"],
            state=row["state"],
            scopes=json.loads(row["scopes_json"]),
            code_challenge=row["code_challenge"],
            redirect_uri=row["redirect_uri"],
            redirect_uri_provided_explicitly=bool(row["redirect_uri_provided_explicitly"]),
            resource=row["resource"],
            expires_at=float(row["expires_at"]),
        )

    def approve_pending_authorization(self, pending: PendingAuthorization) -> str:
        code = secrets.token_urlsafe(32)
        self.db.execute("DELETE FROM oauth_pending_authorizations WHERE request_id = ?", (pending.request_id,))
        self.db.execute(
            """
            INSERT INTO oauth_authorization_codes (
                code, client_id, scopes_json, code_challenge, redirect_uri,
                redirect_uri_provided_explicitly, resource, subject, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code,
                pending.client_id,
                json.dumps(pending.scopes),
                pending.code_challenge,
                pending.redirect_uri,
                pending.redirect_uri_provided_explicitly,
                pending.resource,
                SUBJECT,
                time.time() + 300,
            ),
        )
        self.db.commit()
        return construct_redirect_uri(pending.redirect_uri, code=code, state=pending.state)

    def verify_login_secret(self, candidate: str) -> bool:
        expected = self.settings.oauth_login_secret or ""
        return bool(expected) and hmac.compare_digest(candidate, expected)

    def _issue_access_token(self, client_id: str, scopes: list[str], resource: str | None, subject: str) -> str:
        token = secrets.token_urlsafe(48)
        expires_at = int(time.time()) + self.settings.oauth_token_ttl_seconds
        self.db.execute(
            """
            INSERT INTO oauth_access_tokens (token, client_id, scopes_json, resource, subject, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token, client_id, json.dumps(scopes), resource, subject, expires_at),
        )
        return token

    def _issue_refresh_token(self, client_id: str, scopes: list[str], subject: str) -> str:
        token = secrets.token_urlsafe(48)
        expires_at = int(time.time()) + self.settings.oauth_refresh_token_ttl_seconds
        self.db.execute(
            """
            INSERT INTO oauth_refresh_tokens (token, client_id, scopes_json, subject, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token, client_id, json.dumps(scopes), subject, expires_at),
        )
        return token

    def _fetchone(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        row = self.db.execute(sql, params).fetchone()
        return dict(row) if row else None


def render_approval_form(pending: PendingAuthorization, error: str | None = None) -> HTMLResponse:
    escaped_error = f"<p class='error'>{html.escape(error)}</p>" if error else ""
    scopes = " ".join(html.escape(scope) for scope in pending.scopes)
    body = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Authorize Interview Prep MCP</title>
        <style>
          body {{ font-family: system-ui, sans-serif; max-width: 34rem; margin: 4rem auto; padding: 0 1rem; }}
          label, input, button {{ display: block; width: 100%; box-sizing: border-box; }}
          input {{ padding: .7rem; margin: .4rem 0 1rem; }}
          button {{ padding: .75rem; cursor: pointer; }}
          .error {{ color: #b00020; }}
          .muted {{ color: #555; }}
        </style>
      </head>
      <body>
        <h1>Authorize Interview Prep MCP</h1>
        <p>ChatGPT is requesting access to your study tools.</p>
        <p class="muted">Scopes: {scopes}</p>
        {escaped_error}
        <form method="post">
          <input type="hidden" name="request_id" value="{html.escape(pending.request_id)}">
          <label for="login_secret">OAuth login secret</label>
          <input id="login_secret" name="login_secret" type="password" autocomplete="current-password" required>
          <button type="submit">Authorize</button>
        </form>
      </body>
    </html>
    """
    return HTMLResponse(body)


async def handle_oauth_approval(request: Request, provider: PersonalOAuthProvider) -> Response:
    if request.method == "GET":
        request_id = request.query_params.get("request_id", "")
        pending = provider.get_pending_authorization(request_id)
        if not pending:
            return HTMLResponse("Authorization request expired or not found.", status_code=400)
        return render_approval_form(pending)

    form: FormData = await request.form()
    request_id = str(form.get("request_id", ""))
    login_secret = str(form.get("login_secret", ""))
    pending = provider.get_pending_authorization(request_id)
    if not pending:
        return HTMLResponse("Authorization request expired or not found.", status_code=400)
    if not provider.verify_login_secret(login_secret):
        return render_approval_form(pending, "Incorrect login secret.")
    return RedirectResponse(provider.approve_pending_authorization(pending), status_code=302)
