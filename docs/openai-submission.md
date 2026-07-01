# OpenAI App Submission Checklist

Use this when preparing the hosted MCP server for ChatGPT Apps Directory review and the resulting Codex Plugin Directory distribution.

Official OpenAI guidance to re-check before submission:

- App submission guidelines: <https://developers.openai.com/apps-sdk/app-submission-guidelines>
- Submission and maintenance guide: <https://developers.openai.com/apps-sdk/deploy/submission>

## App Metadata

| Field | Draft value |
| --- | --- |
| App name | Interview Prep MCP |
| Category | Education |
| Short description | Shared study progress and spaced-repetition memory for interviews and coursework. |
| MCP URL | `https://interview-and-learning-data-mcp-production.up.railway.app/mcp` |
| Homepage | `https://interview-and-learning-data-mcp-production.up.railway.app/` |
| Privacy policy | `https://interview-and-learning-data-mcp-production.up.railway.app/privacy` |
| Terms | `https://interview-and-learning-data-mcp-production.up.railway.app/terms` |
| Support | `https://interview-and-learning-data-mcp-production.up.railway.app/support` |

Replace the Railway domain with a stable custom domain before final public submission if one is available. OpenAI app base MCP URLs cannot change between versions; changing the base URL later requires a new app.

When changing the public domain, update plugin distribution metadata first:

```bash
python3 scripts/manage_public_urls.py --base-url https://interview-prep.example.com --write --check
```

Then regenerate the submission packet and MCP contract snapshot.

Generate a machine-readable copy of the app metadata, OIDC auth requirements, reviewer credential requirements, review prompts, scopes, tool contract, verification commands, and distribution notes with:

```bash
python3 scripts/build_submission_packet.py
```

The packet is written to `dist/openai-submission-packet.json` and is ignored by git.

Generate the scanned MCP contract snapshot with:

```bash
python3 scripts/build_mcp_contract_snapshot.py
```

The snapshot is written to `dist/mcp-contract-snapshot.json` and captures registered tools, schemas, annotations, prompts, website URL, and initialization instructions.

Compare a previous reviewed snapshot with a new snapshot before changing a published app:

```bash
python3 scripts/diff_mcp_contract.py previous-mcp-contract-snapshot.json dist/mcp-contract-snapshot.json
```

The diff exits non-zero when it detects breaking changes such as removed tools/prompts, base URL changes, required input additions, input type changes, or safety annotation changes. It also marks prompt title/description changes for review because those fields are part of the scanned app behavior.

## Test Prompts

Use a reviewer-safe demo account with seeded sample data.

Seed demo data for the reviewer account's token subject:

```bash
DATABASE_URL=... python3 scripts/seed_demo_data.py --subject reviewer-demo --with-attempts
```

The `--subject` value must match the stable subject claim issued for the reviewer account.

| Prompt | Expected behavior |
| --- | --- |
| "Show my due study reviews." | Calls `get_due_subtopics` and returns only demo-account due subtopics. |
| "Create a study called AI Engineering Interview." | Calls `create_study` and confirms the created study. |
| "Add Transformers as a topic under AI Engineering Interview." | Calls `create_topic` using the demo study id. |
| "Add Multi-head Attention as a subtopic." | Calls `create_subtopic` using the demo topic id. |
| "Quiz me on Multi-head Attention." | Asks a question; after the answer, calls `log_attempt` with score and notes. |
| "Show my history for Multi-head Attention." | Calls `get_subtopic_history` and summarizes attempts, trend, and next review date. |
| "Export my study data." | Calls `export_my_data` and summarizes what is included without exposing another account's data. |

## Tool Review Notes

- Read tools: `list_studies`, `list_topics`, `list_subtopics`, `get_due_subtopics`, `get_subtopic_history`, `export_my_data`.
- Write tools: `create_study`, `create_topic`, `create_subtopic`, `update_subtopic`, `delete_study`, `delete_topic`, `delete_subtopic`, `log_attempt`, `delete_my_data`.
- Hierarchy delete tools are soft deletes. They preserve history but hide active records.
- `delete_my_data` is a hard delete and requires the exact confirmation phrase `DELETE MY STUDY DATA`.
- Tools never accept a user id. The authenticated token subject scopes every query.
- Tool input schemas are intentionally minimal: hierarchy ids, study/topic/subtopic names, review scores/notes, optional review limits, and the deletion confirmation phrase only.
- Routine tool responses should not include auth subjects, access tokens, secrets, raw OAuth records, request ids, or internal trace ids. `export_my_data` is the explicit full-account export path.
- Tool annotations are set for review: read tools have `readOnlyHint=true`; closed-world writes have `openWorldHint=false`; only `delete_my_data` has `destructiveHint=true`.

## Prompt Review Notes

- `review_due_items` guides the normal due-review and `log_attempt` loop.
- `create_study_plan` guides hierarchy creation and tells the assistant to ask before write tools.
- `review_progress` keeps progress summaries grounded in read tools.
- `account_data_request` routes export and deletion requests through `export_my_data` and `delete_my_data`.

## Pre-Submission Gates

- Production env uses Postgres through `DATABASE_URL`.
- HTTP auth is enabled with OIDC or private review OAuth.
- `MCP_ALLOW_UNAUTHENTICATED_HTTP` is unset or `false`.
- `scripts/check_production_config.py` passes, or passes with `--allow-private-oauth` for a private review deployment.
- `scripts/check_database_schema.py` passes against the production database.
- `/`, `/privacy`, `/terms`, `/support`, and `/healthz` return successfully.
- Public pages and health responses include restrictive security headers, including Content Security Policy, no-store caching, no-referrer, and frame denial.
- `/.well-known/oauth-protected-resource/mcp` returns OAuth protected-resource metadata for the `/mcp` resource and advertises `study:read` / `study:write`.
- The deployed container reports healthy through its `/healthz` Docker healthcheck where the host exposes container health.
- `/mcp` rejects unauthenticated requests.
- `scripts/verify_public_deployment.py` passes against the production base URL.
- `scripts/verify_authenticated_mcp.py` passes against the production MCP URL with a reviewer/test bearer token.
- `RATE_LIMIT_PER_MINUTE` is set to an intentional production value.
- Reviewer demo data is seeded for the exact reviewer token subject.
- Tool annotations match actual behavior for read-only, write, destructive, and open-world hints.
- MCP initialization instructions describe the due-review workflow, SM-2 logging loop, auth scoping, export, and deletion behavior without including private user-specific data.
- A reviewer account can connect without MFA, SMS, or out-of-band manual approval.
- `scripts/release_check.py` passes before submission.
- `scripts/manage_public_urls.py --check` passes and the domain is the intended permanent submission domain.
- `scripts/package_plugin.py --check` passes, or `scripts/package_plugin.py` has produced the archive requested by the reviewer/store workflow.
- `scripts/build_submission_packet.py --check` passes, or `scripts/build_submission_packet.py` has produced the packet requested by the reviewer/store workflow.
- `scripts/build_mcp_contract_snapshot.py --check` passes, or `scripts/build_mcp_contract_snapshot.py` has produced the contract snapshot requested by the reviewer/store workflow.
- OpenAI Platform organization verification is complete for the individual or business name used in the listing.
- The submitting user has `api.apps.write`; reviewers can view status with `api.apps.read`.
- The project used for submission has global data residency if OpenAI still disallows EU data-residency projects for app submission.
- Test credentials are for a fully featured demo account with sample data and no MFA, SMS, email verification, or manual approval step.

## Versioning Rule

After OpenAI scans an app draft, treat tool names, schemas, descriptions, annotations, and MCP initialization instructions as a versioned contract. Deploy backward-compatible server fixes freely, but do not remove or rename published tools without a new reviewed app version and a rollback plan.

Keep a copy of the snapshot submitted for review. Use `scripts/diff_mcp_contract.py` to compare that reviewed snapshot against future builds before deploying metadata-affecting changes.

OpenAI's current dashboard flow creates the public Codex plugin distribution when an approved ChatGPT app is published. Use the repo-local plugin archive for development, workspace installs, manual review, or teammate testing; do not treat the local archive as a substitute for the public OpenAI app review flow.
