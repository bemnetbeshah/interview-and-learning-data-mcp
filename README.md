# Interview Prep MCP Server

An MCP server that lets Claude and ChatGPT share the same study-progress database for interview prep, coursework, and spaced repetition. The current architecture supports multiple authenticated subjects in one database, with each user's tools scoped to their own study data.

The product source of truth is [interview_prep_mcp_prd.md](./interview_prep_mcp_prd.md).

## What It Implements

- Study hierarchy: Study -> Topic -> Subtopic.
- Append-only quiz attempts with score, model notes, and optional question text.
- Subtopic state snapshots with mastery, ease factor, interval, next review date, and streak.
- Server-side SM-2 scheduling so LLM clients never calculate intervals.
- MCP tools for reads, writes, and hierarchy management.
- Public-safe MCP initialization instructions that guide clients through the review loop and data boundaries.
- MCP prompts for due reviews, study-plan creation, progress review, and account data requests.
- Postgres persistence for production and SQLite fallback for local development.
- Per-user data isolation using the authenticated token subject.
- Repo-local Codex plugin packaging for development and workspace installs.

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
| `OAUTH_LOGIN_SECRET` | unset | Enables approval-secret OAuth for ChatGPT Developer Mode when set. |
| `MCP_BEARER_TOKEN` | unset | Enables static bearer-token auth when set and OAuth is unset. |
| `MCP_ALLOW_UNAUTHENTICATED_HTTP` | `false` | Allows unauthenticated HTTP only for non-public development. |
| `OIDC_ISSUER_URL` | unset | Enables public OIDC/JWT bearer-token verification when set. |
| `OIDC_JWKS_URL` | `<issuer>/.well-known/jwks.json` | JWKS endpoint for validating OIDC access tokens. |
| `OIDC_AUDIENCE` | unset | JWT audience required for public OIDC launch, usually `interview-prep-mcp`. |
| `OIDC_SUBJECT_CLAIM` | `sub` | JWT claim used as the stable study owner subject. |
| `OIDC_REQUIRED_SCOPES` | `study:read study:write` | Required access-token scopes for MCP tool calls. |
| `PUBLIC_SERVICE_NAME` | `Interview Prep MCP` | Name shown on public informational pages. |
| `PUBLIC_CONTACT_EMAIL` | `support@example.com` | Support/privacy contact shown on public pages. |
| `RATE_LIMIT_PER_MINUTE` | `120` | In-memory per-subject MCP tool-call limit per service instance. |
| `MCP_DEFAULT_SUBJECT` | `bem` | Owner subject used for local unauthenticated runs and simple single-subject auth. |

## Multi-User Architecture

The public-ready data model scopes all studies by `owner_subject`, and all topic, subtopic, attempt, and review-state access is validated through that owning study. MCP tools do not accept a `user_id`; hosted requests derive the subject from the OAuth or bearer token so clients cannot select another account by passing an id.

For public deployments, configure `OIDC_ISSUER_URL` and related OIDC settings so access tokens are issued by a real identity provider and each user gets a stable `owner_subject`.

The included OAuth approval-secret flow remains best suited to private or invite-only deployments.

Remote HTTP transports refuse to start without OAuth or bearer auth unless `MCP_ALLOW_UNAUTHENTICATED_HTTP=true` is explicitly set for non-public development.

## Tools

The server exposes the PRD tool surface:

| Tool | Purpose |
| --- | --- |
| `list_studies` | Return all active studies. |
| `list_topics` | Return topics within a study. |
| `list_subtopics` | Return subtopics within a topic with current mastery. |
| `get_due_subtopics` | Return due review items, optionally scoped to a study. |
| `get_subtopic_history` | Return attempts, trend, and scheduling state for one subtopic. |
| `export_my_data` | Export all studies, topics, subtopics, attempts, and review state for the authenticated user. |
| `delete_my_data` | Hard-delete all study data for the authenticated user after explicit confirmation. |
| `log_attempt` | Record a score and notes, then update SM-2 scheduling. |
| `create_study` | Add a study. |
| `create_topic` | Add a topic under a study. |
| `create_subtopic` | Add a subtopic under a topic. |
| `update_subtopic` | Edit subtopic name or description. |
| `delete_study` | Soft-delete a study. |
| `delete_topic` | Soft-delete a topic. |
| `delete_subtopic` | Soft-delete a subtopic. |

## Prompts

The server also exposes MCP prompts for common workflows:

| Prompt | Purpose |
| --- | --- |
| `review_due_items` | Start a due-review session and log each attempt. |
| `create_study_plan` | Create or extend a study hierarchy with approval before writes. |
| `review_progress` | Summarize due work, weak spots, and trends using read tools. |
| `account_data_request` | Route export and deletion requests through the right account-data tools. |

## Test

```bash
python -m unittest discover -s tests
```

Before packaging or submitting a public release, run the combined local gate:

```bash
python3 scripts/release_check.py
```

To produce a shareable plugin archive for review or manual distribution:

```bash
python3 scripts/package_plugin.py
```

To produce a machine-readable OpenAI app submission packet:

```bash
python3 scripts/build_submission_packet.py
```

To produce a machine-readable MCP contract snapshot:

```bash
python3 scripts/build_mcp_contract_snapshot.py
```

To compare a previous reviewed snapshot against a new build:

```bash
python3 scripts/diff_mcp_contract.py previous-mcp-contract-snapshot.json dist/mcp-contract-snapshot.json
```

To update plugin distribution metadata when moving to a custom domain:

```bash
python3 scripts/manage_public_urls.py --base-url https://interview-prep.example.com --write --check
```

The same release gate runs in GitHub Actions on pull requests, pushes to `main` and `public-facing-version`, and manual workflow dispatch. The workflow uploads the plugin archive, OpenAI submission packet, MCP contract snapshot, and public launch docs as CI artifacts.

## Deployment Notes

The PRD calls for one hosted remote MCP server reachable by Claude and ChatGPT. This repo supports that path through FastMCP and uses Postgres when `DATABASE_URL` is configured.

The included [Dockerfile](./Dockerfile) runs the server with `MCP_TRANSPORT=streamable-http` and binds to `0.0.0.0`. SQLite remains available for local development or small single-volume deployments.

[railway.json](./railway.json) pins Railway deployment settings for the Dockerfile builder, `/healthz` platform healthcheck, and restart policy.

See [docs/deployment.md](./docs/deployment.md) for remote MCP URLs, OAuth, bearer-token auth, and client connection examples.

See [docs/public-launch.md](./docs/public-launch.md) for the recommended public hosting, database, auth, OpenAI app submission, Claude connector, and Codex plugin plan.

See [docs/public-auth.md](./docs/public-auth.md), [docs/oidc-provider-setup.md](./docs/oidc-provider-setup.md), and [docs/production-env.example](./docs/production-env.example) for the external OIDC provider contract, setup runbook, and production environment template.

The hosted service also serves public review/support pages:

- `/` for a product overview and MCP endpoint.
- `/privacy` for privacy disclosures.
- `/terms` for service terms.
- `/support` for contact and troubleshooting.
- `/healthz` for non-secret service health metadata.

See [docs/openai-submission.md](./docs/openai-submission.md) for app review metadata and test prompts.

After deploying, run the public endpoint verifier:

```bash
python3 scripts/release_check.py
python3 scripts/check_production_config.py
python3 scripts/verify_public_deployment.py https://your-app.example.com
MCP_AUTH_TOKEN=... python3 scripts/verify_authenticated_mcp.py https://your-app.example.com/mcp
```

To seed reviewer-safe demo data:

```bash
DATABASE_URL=... python3 scripts/seed_demo_data.py --subject reviewer-demo --with-attempts
```

## Codex Plugin

This repo includes a Codex plugin bundle at [plugins/interview-prep-mcp](./plugins/interview-prep-mcp) and a repo marketplace at [.agents/plugins/marketplace.json](./.agents/plugins/marketplace.json). The plugin points Codex at the hosted Railway MCP endpoint and bundles a skill that guides study-review workflows.

If Codex does not discover the repo marketplace automatically, add it from the repo root:

```bash
codex plugin marketplace add .
```

For a shareable archive, run `python3 scripts/package_plugin.py`. The generated `dist/interview-prep-mcp-<version>.plugin.zip` contains the plugin manifest, MCP server config, skill, assets folder, and folder indexes.
