# Folder Index

| Path | Description |
| --- | --- |
| [__init__.py](./__init__.py) | Package metadata exports. |
| [__main__.py](./__main__.py) | Module entrypoint for `python -m interview_prep_mcp`. |
| [auth.py](./auth.py) | Single-user bearer-token verifier for hosted HTTP MCP transports. |
| [config.py](./config.py) | Runtime database, transport, host, and port settings loaded from environment variables. |
| [db.py](./db.py) | SQLite connection and schema initialization. |
| [server.py](./server.py) | FastMCP server and tool registration. |
| [service.py](./service.py) | Application operations backing all MCP tools. |
| [sm2.py](./sm2.py) | SM-2 spaced repetition update logic. |
