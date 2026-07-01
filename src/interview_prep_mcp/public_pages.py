"""Public informational routes for hosted deployments."""

from __future__ import annotations

import html
from typing import Any

from starlette.responses import HTMLResponse, JSONResponse

from .config import Settings

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


def render_home(settings: Settings) -> HTMLResponse:
    title = _escape(settings.public_service_name)
    mcp_url = _escape(settings.resource_server_url)
    privacy_url = _escape(_url(settings, "/privacy"))
    terms_url = _escape(_url(settings, "/terms"))
    support_url = _escape(_url(settings, "/support"))
    body = _page(
        title,
        f"""
        <h1>{title}</h1>
        <p>Shared study progress and spaced-repetition memory for MCP-compatible assistants.</p>
        <dl>
          <dt>MCP endpoint</dt>
          <dd><code>{mcp_url}</code></dd>
          <dt>What it stores</dt>
          <dd>Studies, topics, subtopics, quiz attempts, grading notes, and review schedules.</dd>
          <dt>How access is scoped</dt>
          <dd>Authenticated token subjects own their own study data. Tools do not accept user ids.</dd>
        </dl>
        <p><a href="{privacy_url}">Privacy</a> <a href="{terms_url}">Terms</a> <a href="{support_url}">Support</a></p>
        """,
    )
    return _html_response(body)


def render_privacy(settings: Settings) -> HTMLResponse:
    title = f"{_escape(settings.public_service_name)} Privacy"
    contact = _mailto(settings.public_contact_email)
    body = _page(
        title,
        f"""
        <h1>{title}</h1>
        <p>This service stores study data that users create through MCP clients.</p>
        <h2>Data collected</h2>
        <ul>
          <li>Authentication subject from the connected identity provider.</li>
          <li>Study, topic, and subtopic names and descriptions.</li>
          <li>Quiz attempts, scores, model notes, optional questions asked, and review schedule state.</li>
          <li>Operational metadata needed to run the service, such as timestamps and token records.</li>
        </ul>
        <h2>Data use</h2>
        <p>Data is used to return the user's study state, calculate spaced-repetition schedules, secure access, and operate the service.</p>
        <h2>Data sharing</h2>
        <p>Study data is not sold. MCP clients receive only data requested through authenticated tool calls for the current user.</p>
        <h2>Retention and deletion</h2>
        <p>Hierarchy delete tools soft-delete studies, topics, and subtopics to preserve review history. Users can export their account data with <code>export_my_data</code> and can hard-delete all study data with <code>delete_my_data</code> after explicit confirmation.</p>
        <h2>Contact</h2>
        <p>For privacy requests or manual help with export and deletion, contact {contact}.</p>
        """,
    )
    return _html_response(body)


def render_terms(settings: Settings) -> HTMLResponse:
    title = f"{_escape(settings.public_service_name)} Terms"
    contact = _mailto(settings.public_contact_email)
    body = _page(
        title,
        f"""
        <h1>{title}</h1>
        <p>This service is provided to help users track study progress and spaced-repetition review state through MCP-compatible clients.</p>
        <h2>Acceptable use</h2>
        <p>Do not use the service to store unlawful content, secrets, credentials, regulated medical records, financial account data, or other high-risk sensitive information.</p>
        <h2>Service behavior</h2>
        <p>The service provides study-memory tools and scheduling calculations. It does not guarantee interview outcomes, academic results, or continuous availability.</p>
        <h2>User responsibility</h2>
        <p>Users are responsible for the content they create and for reviewing assistant-generated quiz feedback before relying on it.</p>
        <h2>Changes</h2>
        <p>The service and these terms may change as the product evolves.</p>
        <h2>Contact</h2>
        <p>Questions about these terms can be sent to {contact}.</p>
        """,
    )
    return _html_response(body)


def render_support(settings: Settings) -> HTMLResponse:
    title = f"{_escape(settings.public_service_name)} Support"
    contact = _mailto(settings.public_contact_email)
    body = _page(
        title,
        f"""
        <h1>{title}</h1>
        <p>For account, privacy, deletion, export, or connector issues, contact {contact}. Authenticated users can also use the <code>export_my_data</code> and <code>delete_my_data</code> MCP tools directly.</p>
        <h2>Useful details to include</h2>
        <ul>
          <li>The client you used, such as ChatGPT, Codex, Claude, or API.</li>
          <li>The approximate time of the issue.</li>
          <li>The tool or workflow that failed.</li>
          <li>Any error message shown by the client.</li>
        </ul>
        <p>Do not send access tokens, passwords, or other secrets in support messages.</p>
        """,
    )
    return _html_response(body)


def render_health(settings: Settings) -> JSONResponse:
    payload: dict[str, Any] = {
        "status": "ok",
        "service": settings.public_service_name,
        "mcp_endpoint": settings.resource_server_url,
        "auth_modes": {
            "oidc": bool(settings.oidc_issuer_url),
            "private_oauth": bool(settings.oauth_login_secret),
            "static_bearer": bool(settings.bearer_token),
            "unauthenticated_http_allowed": settings.allow_unauthenticated_http,
        },
    }
    return JSONResponse(payload, headers=SECURITY_HEADERS)


def _html_response(body: str) -> HTMLResponse:
    return HTMLResponse(body, headers=SECURITY_HEADERS)


def _page(title: str, main: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
      body {{ font-family: system-ui, sans-serif; max-width: 48rem; margin: 4rem auto; padding: 0 1rem; line-height: 1.55; color: #1f2937; }}
      h1 {{ font-size: 2rem; line-height: 1.15; margin: 0 0 1rem; }}
      h2 {{ font-size: 1.15rem; margin-top: 2rem; }}
      a {{ color: #155eef; margin-right: 1rem; }}
      code {{ background: #f3f4f6; padding: .15rem .3rem; border-radius: .25rem; }}
      dt {{ font-weight: 700; margin-top: 1rem; }}
      dd {{ margin-left: 0; }}
    </style>
  </head>
  <body>
    <main>
      {main}
    </main>
  </body>
</html>"""


def _url(settings: Settings, path: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}{path}"


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _mailto(email: str) -> str:
    escaped = _escape(email)
    return f'<a href="mailto:{escaped}">{escaped}</a>'
