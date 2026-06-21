# Folder Index

| Path | Description |
| --- | --- |
| [__init__.py](./__init__.py) | Package metadata exports. |
| [__main__.py](./__main__.py) | Module entrypoint for `python -m interview_prep_mcp`. |
| [auth.py](./auth.py) | Hosted HTTP auth wiring for no-auth, bearer-token, and OAuth modes. |
| [config.py](./config.py) | Runtime database, transport, host, and port settings loaded from environment variables. |
| [db.py](./db.py) | SQLite/Postgres connection and schema initialization. |
| [oauth.py](./oauth.py) | Single-user OAuth provider, approval form, and token persistence for ChatGPT MCP connections. |
| [server.py](./server.py) | FastMCP server and tool registration. |
| [service.py](./service.py) | Application operations backing all MCP tools. |
| [sm2.py](./sm2.py) | SM-2 spaced repetition update logic. |
