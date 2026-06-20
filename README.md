# Interview Prep MCP Server

A personal MCP server that lets Claude and ChatGPT share the same study-progress database for interview prep, coursework, and spaced repetition.

The product source of truth is [interview_prep_mcp_prd.md](./interview_prep_mcp_prd.md).

## What It Implements

- Study hierarchy: Study -> Topic -> Subtopic.
- Append-only quiz attempts with score, model notes, and optional question text.
- Subtopic state snapshots with mastery, ease factor, interval, next review date, and streak.
- Server-side SM-2 scheduling so LLM clients never calculate intervals.
- MCP tools for reads, writes, and hierarchy management.
- Postgres persistence for production and SQLite fallback for local development.

## Local Setup

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run

```bash
interview-prep-mcp
```

By default the server uses stdio transport and stores data in `data/interview_prep.sqlite3`.

Useful environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `INTERVIEW_PREP_DB_PATH` | `data/interview_prep.sqlite3` | SQLite database path. |
| `DATABASE_URL` | unset | Postgres connection URL. Takes precedence over SQLite when set. |
| `MCP_TRANSPORT` | `stdio` | FastMCP transport, for example `stdio` or `streamable-http` depending on the installed MCP SDK. |
| `MCP_HOST` | `127.0.0.1` | Host for HTTP transports. |
| `MCP_PORT` / `PORT` | `8000` | Port for HTTP transports. `PORT` is checked first for platform hosts. |

## Tools

The server exposes the PRD tool surface:

| Tool | Purpose |
| --- | --- |
| `list_studies` | Return all active studies. |
| `list_topics` | Return topics within a study. |
| `list_subtopics` | Return subtopics within a topic with current mastery. |
| `get_due_subtopics` | Return due review items, optionally scoped to a study. |
| `get_subtopic_history` | Return attempts, trend, and scheduling state for one subtopic. |
| `log_attempt` | Record a score and notes, then update SM-2 scheduling. |
| `create_study` | Add a study. |
| `create_topic` | Add a topic under a study. |
| `create_subtopic` | Add a subtopic under a topic. |
| `update_subtopic` | Edit subtopic name or description. |
| `delete_study` | Soft-delete a study. |
| `delete_topic` | Soft-delete a topic. |
| `delete_subtopic` | Soft-delete a subtopic. |

## Test

```bash
python -m unittest discover -s tests
```

## Deployment Notes

The PRD calls for one hosted remote MCP server reachable by Claude and ChatGPT. This repo supports that path through FastMCP and uses Postgres when `DATABASE_URL` is configured.

The included [Dockerfile](./Dockerfile) runs the server with `MCP_TRANSPORT=streamable-http` and binds to `0.0.0.0`. SQLite remains available for local development or small single-volume deployments.

See [docs/deployment.md](./docs/deployment.md) for remote MCP URLs, bearer-token auth, and client connection examples.
