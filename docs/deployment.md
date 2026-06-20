# Deployment Guide

The PRD requires one always-on remote MCP server that Claude and ChatGPT can both reach. This project uses FastMCP with Streamable HTTP for hosted deployments.

## Required Environment

| Variable | Example | Notes |
| --- | --- | --- |
| `INTERVIEW_PREP_DB_PATH` | `/data/interview_prep.sqlite3` | SQLite path. Mount `/data` as persistent storage. |
| `MCP_TRANSPORT` | `streamable-http` | Remote MCP transport. |
| `MCP_HOST` | `0.0.0.0` | Bind address for hosted container platforms. |
| `PORT` | platform-provided | Preferred hosted port variable. Falls back to `MCP_PORT`. |
| `MCP_BEARER_TOKEN` | generated secret | Single-user access token. Do not commit this. |
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

## Auth Model

This repo implements a single-user bearer-token verifier. When `MCP_BEARER_TOKEN` is set, FastMCP requires bearer auth for HTTP transports. When it is unset, local stdio development remains unauthenticated.

This is intentionally simpler than a full OAuth authorization server. The MCP authorization spec allows authorization to be optional, but HTTP protected resource requests use the standard bearer-token header when auth is enabled.

Source: [MCP Authorization spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization).

## Railway Sketch

1. Deploy this repository with the included [Dockerfile](../Dockerfile).
2. Add a Railway Volume mounted at `/data`.
3. Set `MCP_TRANSPORT=streamable-http`.
4. Set `MCP_HOST=0.0.0.0`.
5. Set `MCP_BEARER_TOKEN` to a strong random value.
6. Set `MCP_PUBLIC_BASE_URL` to the Railway public HTTPS domain.
7. Connect clients to `https://<railway-domain>/mcp`.

## Production Database Note

The PRD names Postgres/Supabase as the preferred production database and SQLite as an acceptable local prototype path. The current implementation uses SQLite with a persistent volume. Moving to Postgres should happen before relying on the server for long-term critical history without filesystem-volume backups.
