# Folder Index

| Path | Description |
| --- | --- |
| [test_check_production_config.py](./test_check_production_config.py) | Tests production configuration checks for public and private review deployments. |
| [test_config_and_auth.py](./test_config_and_auth.py) | Unit tests for environment settings and hosted auth wiring. |
| [test_db_schema.py](./test_db_schema.py) | Tests schema initialization, legacy upgrade behavior, and migration ledger recording. |
| [test_dockerfile.py](./test_dockerfile.py) | Checks the container includes a `/healthz` healthcheck for hosted deployments. |
| [test_github_workflow.py](./test_github_workflow.py) | Checks that CI runs the release gate and uploads the plugin archive. |
| [test_manage_public_urls.py](./test_manage_public_urls.py) | Tests public base URL consistency checks and plugin metadata updates. |
| [test_mcp_contract.py](./test_mcp_contract.py) | Contract test that registered MCP tools and review annotations match the public tool surface. |
| [test_mcp_contract_diff.py](./test_mcp_contract_diff.py) | Tests MCP contract snapshot diffing for breaking and review-required changes. |
| [test_mcp_contract_snapshot.py](./test_mcp_contract_snapshot.py) | Tests machine-readable MCP contract snapshot generation and validation. |
| [test_oauth.py](./test_oauth.py) | Tests dynamic OAuth client registration, approval, token exchange, and token verification. |
| [test_oidc_jwt_verifier.py](./test_oidc_jwt_verifier.py) | Tests OIDC JWT verification with real signed RS256 tokens and public auth claim variants. |
| [test_package_plugin.py](./test_package_plugin.py) | Tests the shareable Codex plugin archive builder. |
| [test_public_pages.py](./test_public_pages.py) | Tests public homepage, privacy, terms, support, and health response rendering. |
| [test_rate_limit.py](./test_rate_limit.py) | Tests per-subject in-memory rate limiter behavior. |
| [test_railway_config.py](./test_railway_config.py) | Checks Railway config-as-code for Dockerfile build and healthcheck settings. |
| [test_release_check.py](./test_release_check.py) | Tests the local public release-check helper. |
| [test_seed_demo_data.py](./test_seed_demo_data.py) | Tests idempotent reviewer demo data seeding and subject isolation. |
| [test_service.py](./test_service.py) | Unit tests covering hierarchy CRUD, attempts, due queue, SM-2 behavior, and subject isolation. |
| [test_submission_packet.py](./test_submission_packet.py) | Tests OpenAI app submission packet generation and required review metadata. |
| [test_verify_authenticated_mcp.py](./test_verify_authenticated_mcp.py) | Tests authenticated hosted MCP smoke verifier contract validation. |
| [test_verify_public_deployment.py](./test_verify_public_deployment.py) | Tests hosted deployment verifier checks for public security headers. |
