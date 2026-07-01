# Deployment Guide

The PRD requires one always-on remote MCP server that Claude and ChatGPT can both reach. This project uses FastMCP with Streamable HTTP for hosted deployments.

## Required Environment

| Variable | Example | Notes |
| --- | --- | --- |
| `DATABASE_URL` | platform-provided | Preferred production Postgres URL. |
| `INTERVIEW_PREP_DB_PATH` | `/data/interview_prep.sqlite3` | SQLite fallback path when `DATABASE_URL` is unset. |
| `MCP_TRANSPORT` | `streamable-http` | Remote MCP transport. |
| `MCP_HOST` | `0.0.0.0` | Bind address for hosted container platforms. |
| `PORT` | platform-provided | Preferred hosted port variable. Falls back to `MCP_PORT`. |
| `OAUTH_LOGIN_SECRET` | generated secret | Enables ChatGPT Developer Mode OAuth. Enter this secret in the approval form during connection. |
| `OAUTH_TOKEN_TTL_SECONDS` | `3600` | OAuth access-token lifetime. |
| `OAUTH_REFRESH_TOKEN_TTL_SECONDS` | `2592000` | OAuth refresh-token lifetime. |
| `MCP_BEARER_TOKEN` | generated secret | Optional bearer-token mode for API clients that can pass Authorization directly. Leave unset when using OAuth. |
| `MCP_ALLOW_UNAUTHENTICATED_HTTP` | `false` | Allows unauthenticated HTTP only for local or tunnel testing. Never enable for public deployments. |
| `OIDC_ISSUER_URL` | `https://issuer.example.com` | Enables public OIDC/JWT bearer-token verification. |
| `OIDC_JWKS_URL` | `https://issuer.example.com/.well-known/jwks.json` | Optional JWKS override. Defaults to the issuer JWKS path. |
| `OIDC_AUDIENCE` | `interview-prep-mcp` | JWT audience required for public OIDC launch. |
| `OIDC_SUBJECT_CLAIM` | `sub` | Stable JWT claim used as `studies.owner_subject`. |
| `OIDC_REQUIRED_SCOPES` | `study:read study:write` | Required scopes for MCP access tokens. |
| `PUBLIC_SERVICE_NAME` | `Interview Prep MCP` | Name shown on public informational pages. |
| `PUBLIC_CONTACT_EMAIL` | `support@example.com` | Support/privacy contact shown on public pages. |
| `RATE_LIMIT_PER_MINUTE` | `120` | In-memory per-subject MCP tool-call limit per service instance. |
| `MCP_PUBLIC_BASE_URL` | `https://your-app.example.com` | Public HTTPS base URL used in auth metadata. |
| `MCP_DEFAULT_SUBJECT` | `bem` | Owner subject for local unauthenticated runs and simple private auth modes. |

The MCP endpoint path is:

```text
https://your-app.example.com/mcp
```

Public support and review pages are served at `/`, `/privacy`, `/terms`, `/support`, and `/healthz`.

Those public responses include restrictive security headers: Content Security Policy, `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, and frame denial headers.

## Deployment Verification

Before deploying a public release, run the local release gate and then the production config checker in the same environment variables that the service will use:

```bash
python3 scripts/release_check.py
python3 scripts/check_production_config.py
python3 scripts/check_database_schema.py
```

For private review deployments that intentionally use approval-secret OAuth instead of OIDC, run:

```bash
python3 scripts/check_production_config.py --allow-private-oauth
```

After every hosted deployment, run:

```bash
python3 scripts/verify_public_deployment.py https://your-app.example.com
MCP_AUTH_TOKEN=... python3 scripts/verify_authenticated_mcp.py https://your-app.example.com/mcp
```

For an invite-only reviewer deployment that intentionally uses `OAUTH_LOGIN_SECRET` before public OIDC is configured, run the public endpoint verifier with:

```bash
python3 scripts/verify_public_deployment.py https://your-app.example.com --allow-private-oauth
```

Do not use that flag for the final public launch check.

The verifier checks that public pages and health respond successfully and that unauthenticated `/mcp` access is rejected.
It also checks the OAuth protected-resource metadata at `/.well-known/oauth-protected-resource/mcp`, including the MCP resource URL, HTTPS authorization server, and `study:read` / `study:write` scopes.

The authenticated verifier uses a real bearer token from the reviewer or test account to initialize the remote MCP session, list tools, list prompts, and render the `review_due_items` prompt.

The Docker image also defines a container `HEALTHCHECK` against local `/healthz`, using `PORT` or `MCP_PORT`.

## Reviewer Demo Data

For app review or smoke testing, seed a safe demo account after the database is configured:

```bash
DATABASE_URL=... python3 scripts/seed_demo_data.py --subject reviewer-demo --with-attempts
```

Use a subject that exactly matches the OIDC subject claim for the reviewer account. The script is idempotent: rerunning it will not duplicate studies, topics, subtopics, or sample attempts. If a prior run only created part of the sample attempt history, rerunning with `--with-attempts` fills the missing sample attempts and reports final totals.

## OpenAI / ChatGPT API Usage

OpenAI remote MCP tools require a `server_url`; authenticated MCP servers can receive an OAuth-style bearer token through the `authorization` field.

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.5",
    tools=[
        {
            "type": "mcp",
            "server_label": "interview_prep",
            "server_description": "Bem's shared interview prep and spaced repetition state.",
            "server_url": "https://your-app.example.com/mcp",
            "authorization": "your-mcp-bearer-token",
            "require_approval": "never",
        }
    ],
    input="List my due interview prep subtopics.",
)

print(response.output_text)
```

Source: [OpenAI MCP and Connectors guide](https://developers.openai.com/api/docs/guides/tools-connectors-mcp).

## Claude Custom Connector

Use the same remote MCP endpoint:

```text
https://your-app.example.com/mcp
```

Configure the connector to send:

```text
Authorization: Bearer your-mcp-bearer-token
```

## ChatGPT Developer Mode

ChatGPT Developer Mode custom apps currently offer OAuth, No Authentication, and Mixed Authentication. Use OAuth for the hosted Railway deployment.

Create the app with:

```text
Auth option: OAuth
MCP URL: https://your-app.example.com/mcp
```

The server exposes OAuth discovery, dynamic client registration, `/authorize`, `/token`, and `/revoke`. During the OAuth flow, the authorization page asks for `OAUTH_LOGIN_SECRET`. This keeps the connector suitable for private or invite-only deployments while letting ChatGPT use normal OAuth access and refresh tokens afterward.

## Auth Model

This repo supports four hosted auth modes:

- `OIDC_ISSUER_URL` set: public OIDC/JWT bearer-token verification is enabled.
- `OAUTH_LOGIN_SECRET` set and OIDC unset: private approval-secret OAuth is enabled.
- `MCP_BEARER_TOKEN` set and OAuth unset: static bearer-token mode is enabled.
- Both unset: local stdio development is unauthenticated. HTTP transports fail closed unless `MCP_ALLOW_UNAUTHENTICATED_HTTP=true` is explicitly set for non-public development.

OIDC mode validates JWTs against the configured JWKS URL and scopes tool calls to the configured subject claim. Private OAuth mode stores dynamic clients, pending authorizations, authorization codes, access tokens, and refresh tokens in the project database. In all auth modes, tool calls are scoped by the token `subject`; studies are owned by `studies.owner_subject`, and all nested topic/subtopic/attempt reads validate through that owning study.

See [public-auth.md](./public-auth.md) for the public provider contract and [production-env.example](./production-env.example) for a copyable production environment template.

## Public Multi-User Launch Notes

The database and service layer support multiple users in one deployment. For an open public launch, configure OIDC with an auth provider that issues a stable unique subject per user. The bundled approval-secret OAuth screen is still useful for private testing, but it is not a full public identity system.

Do not expose a deployment with auth disabled. No-auth mode is for local stdio or private development only.

The built-in rate limiter is per process and per authenticated subject. Keep it enabled for public deployment, but also use platform-level rate limiting if the host or gateway supports it.

Source: [MCP Authorization spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization).

## Railway Sketch

1. Deploy this repository with the included [Dockerfile](../Dockerfile).
2. Add a Railway Postgres database and set the app service `DATABASE_URL` to that database's connection URL.
3. Set `MCP_TRANSPORT=streamable-http`.
4. Set `MCP_HOST=0.0.0.0`.
5. For public users, configure `OIDC_ISSUER_URL`, optional `OIDC_JWKS_URL`, required `OIDC_AUDIENCE`, and required scopes. For ChatGPT Developer Mode or a private invite-only deployment, set `OAUTH_LOGIN_SECRET` to a strong random value instead.
6. Set `MCP_PUBLIC_BASE_URL` to the Railway public HTTPS domain.
7. Connect clients to `https://<railway-domain>/mcp`.

The approval-secret flow is not an open signup system.

Railway deployment settings are pinned in [../railway.json](../railway.json). The file uses Railway config-as-code to force the Dockerfile builder, set `/healthz` as the platform healthcheck, and use an on-failure restart policy. Railway merges config-as-code with dashboard settings for each deployment, with code values overriding dashboard values for that deployment.

## Codex Plugin Packaging

The repo-local plugin bundle lives at [../plugins/interview-prep-mcp](../plugins/interview-prep-mcp). It includes `.mcp.json` pointing at the current Railway MCP endpoint and a skill for the review loop. The marketplace entry is [../.agents/plugins/marketplace.json](../.agents/plugins/marketplace.json).

Build a shareable plugin archive with:

```bash
python3 scripts/package_plugin.py
```

The script writes `dist/interview-prep-mcp-<version>.plugin.zip`. Use `python3 scripts/package_plugin.py --check` when you only want to verify that packaging succeeds.

Use this plugin for development, workspace sharing, and install-flow testing. For public OpenAI distribution, submit the hosted MCP app through the OpenAI Platform dashboard; publishing an approved app is the path that creates the public Codex plugin distribution.

## Production Database Note

The PRD names Postgres/Supabase as the preferred production database and SQLite as an acceptable local prototype path. This implementation uses Postgres whenever `DATABASE_URL` is present and otherwise falls back to SQLite.

Schema initialization is idempotent and records applied schema versions in `schema_migrations`. Run `python3 scripts/check_database_schema.py` against the production environment to verify required tables, required columns, and applied migration versions. Before major production releases, inspect that ledger in Postgres and back up the database before deploying any schema-affecting change.
