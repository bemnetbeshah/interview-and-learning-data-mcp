# Folder Index

| Path | Description |
| --- | --- |
| [__init__.py](./__init__.py) | Package marker so operational scripts can be imported by tests. |
| [build_mcp_contract_snapshot.py](./build_mcp_contract_snapshot.py) | Builds a machine-readable snapshot of registered MCP tools, prompts, and metadata. |
| [build_submission_packet.py](./build_submission_packet.py) | Builds a machine-readable OpenAI app submission packet from plugin metadata. |
| [check_database_schema.py](./check_database_schema.py) | Validates the configured database schema and migration ledger. |
| [check_production_config.py](./check_production_config.py) | Validates production environment settings before public deployment. |
| [diff_mcp_contract.py](./diff_mcp_contract.py) | Compares two MCP contract snapshots and flags breaking published-app changes. |
| [index.md](./index.md) | This folder inventory. |
| [manage_public_urls.py](./manage_public_urls.py) | Checks or updates public plugin/MCP URLs when moving to a custom domain. |
| [package_plugin.py](./package_plugin.py) | Builds a shareable zip archive of the repo-local Codex plugin. |
| [release_check.py](./release_check.py) | Runs local release gates for tests, script compilation, and plugin bundle structure. |
| [verify_authenticated_mcp.py](./verify_authenticated_mcp.py) | Verifies authenticated hosted MCP initialization, tools, prompts, and review prompt rendering. |
| [seed_demo_data.py](./seed_demo_data.py) | Seeds reviewer-safe demo study data for a configured owner subject. |
| [verify_public_deployment.py](./verify_public_deployment.py) | Checks public pages, security headers, health, and unauthenticated MCP rejection for a hosted deployment. |
