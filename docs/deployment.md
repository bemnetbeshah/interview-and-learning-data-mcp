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
| `MCP_PUBLIC_BASE_URL` | `https://your-app.example.com` | Public HTTPS base URL used in auth metadata. |

The MCP endpoint path is:

```text
https://your-app.example.com/mcp
```

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

The server exposes OAuth discovery, dynamic client registration, `/authorize`, `/token`, and `/revoke`. During the OAuth flow, the authorization page asks for `OAUTH_LOGIN_SECRET`. This keeps the connector single-user while letting ChatGPT use normal OAuth access and refresh tokens afterward.

## Auth Model

This repo supports three hosted auth modes:

- `OAUTH_LOGIN_SECRET` set: OAuth is enabled and HTTP MCP requests require OAuth bearer tokens.
- `MCP_BEARER_TOKEN` set and OAuth unset: static bearer-token mode is enabled.
- Both unset: HTTP and local stdio development are unauthenticated.

OAuth mode stores dynamic clients, pending authorizations, authorization codes, access tokens, and refresh tokens in the project database.

Source: [MCP Authorization spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization).

## Railway Sketch

1. Deploy this repository with the included [Dockerfile](../Dockerfile).
2. Add a Railway Postgres database and set the app service `DATABASE_URL` to that database's connection URL.
3. Set `MCP_TRANSPORT=streamable-http`.
4. Set `MCP_HOST=0.0.0.0`.
5. For ChatGPT Developer Mode, set `OAUTH_LOGIN_SECRET` to a strong random value and leave `MCP_BEARER_TOKEN` unset.
6. Set `MCP_PUBLIC_BASE_URL` to the Railway public HTTPS domain.
7. Connect clients to `https://<railway-domain>/mcp`.

## Production Database Note

The PRD names Postgres/Supabase as the preferred production database and SQLite as an acceptable local prototype path. This implementation uses Postgres whenever `DATABASE_URL` is present and otherwise falls back to SQLite.
