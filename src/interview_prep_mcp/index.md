# Folder Index

| Path | Description |
| --- | --- |
| [__init__.py](./__init__.py) | Package metadata exports. |
| [__main__.py](./__main__.py) | Module entrypoint for `python -m interview_prep_mcp`. |
| [auth.py](./auth.py) | Hosted HTTP auth wiring for OIDC, private OAuth, bearer-token, no-auth, and token subjects. |
| [config.py](./config.py) | Runtime database, transport, auth, host, port, and subject settings loaded from environment variables. |
| [db.py](./db.py) | SQLite/Postgres connection, schema initialization, and migration ledger recording. |
| [oauth.py](./oauth.py) | Approval-secret OAuth provider, approval form, subject handling, and token persistence for ChatGPT MCP connections. |
| [public_pages.py](./public_pages.py) | Public homepage, privacy, terms, support, and health response rendering for hosted deployments. |
| [rate_limit.py](./rate_limit.py) | In-memory per-subject rate limiter for MCP tool calls. |
| [server.py](./server.py) | FastMCP server and tool registration. |
| [service.py](./service.py) | Subject-scoped application operations backing all MCP tools, including account export and deletion. |
| [sm2.py](./sm2.py) | SM-2 spaced repetition update logic. |
