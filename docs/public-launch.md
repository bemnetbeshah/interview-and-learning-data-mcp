# Public Launch Plan

This project has two distribution surfaces:

1. A hosted remote MCP server that all clients call.
2. Install/discovery wrappers, such as a ChatGPT app submission or Codex plugin, that point users at that hosted server.

The hosted server is the product. Plugins and app listings are packaging around the same `/mcp` endpoint.

## Recommended Production Stack

| Layer | Recommendation | Reason |
| --- | --- | --- |
| Hosting | Railway for v1 | The repo already deploys there with Docker, public HTTPS, env vars, and Postgres. |
| Database | Postgres | Required for public multi-user persistence and operational backups. SQLite is local-only. |
| Auth | OIDC/OAuth provider | Public users need stable, unique subjects. The current approval-secret OAuth is invite/private only. |
| MCP transport | `streamable-http` | Required for remote clients such as ChatGPT, Codex, and Claude. |
| Distribution | OpenAI app submission plus repo-local Codex plugin | OpenAI app review is the public ChatGPT/Codex path; the repo plugin is useful for development and workspace installs. |

## Public-Readiness Requirements

- Use a stable production domain and keep it across app versions.
- Before final submission, run `scripts/manage_public_urls.py --base-url https://your-domain.example --write --check` so plugin metadata and MCP config use the same stable base URL.
- Set `DATABASE_URL` to production Postgres.
- Set `MCP_TRANSPORT=streamable-http`, `MCP_HOST=0.0.0.0`, and `MCP_PUBLIC_BASE_URL=https://...`.
- Do not run public HTTP with auth disabled. The server rejects unauthenticated HTTP unless `MCP_ALLOW_UNAUTHENTICATED_HTTP=true`.
- Configure `OIDC_ISSUER_URL`, JWKS, audience, subject claim, and scopes before opening access to arbitrary users.
- Keep `owner_subject` server-derived from auth. Never add `user_id` tool parameters.
- Avoid returning auth subjects in routine tool responses; expose account identifiers only through explicit account export.
- Maintain working `/privacy`, `/terms`, and `/support` pages before submitting to app/plugin directories.
- Serve public pages with restrictive security headers and a narrow Content Security Policy.
- Support account data export and deletion through authenticated MCP tools.
- Keep per-subject rate limiting enabled and add platform-level limits when available.
- Keep MCP tool annotations aligned with actual read/write/destructive behavior.
- Provide a demo account or reviewer-safe login path for app review.
- Keep tool names, schemas, and descriptions backward compatible once submitted.

## Auth Implementation Options

### Current Private Mode

`OAUTH_LOGIN_SECRET` enables a simple OAuth authorization server with dynamic client registration. It is useful for ChatGPT Developer Mode and invite-only testing, but it maps approvals to `MCP_DEFAULT_SUBJECT`, so it is not a true public identity system.

Use this mode for:

- Personal deployment.
- Private beta with a shared approval secret.
- Review of the MCP flow before integrating external identity.

Do not use it for open signup.

### Public Mode

For public launch, configure an identity provider such as Supabase Auth, Clerk, Auth0, WorkOS, or Cognito. The provider must issue JWT access tokens with a stable subject per user. Set:

```text
OIDC_ISSUER_URL=https://issuer.example.com
OIDC_JWKS_URL=https://issuer.example.com/.well-known/jwks.json
OIDC_AUDIENCE=interview-prep-mcp
OIDC_SUBJECT_CLAIM=sub
OIDC_REQUIRED_SCOPES=study:read study:write
```

The MCP auth layer validates the JWT and passes that subject into `InterviewPrepService.for_subject(...)`.

See [public-auth.md](./public-auth.md) for the detailed provider contract. The verifier accepts grants from `scope`, `scp`, `permissions`, `roles`, or `role`, but the recommended public grants remain `study:read` and `study:write`.

The implementation should preserve the current service contract:

- MCP tools receive study/topic/subtopic ids only.
- Auth determines the current subject.
- Database queries validate ownership through `studies.owner_subject`.

## Plugin and App Distribution

### OpenAI ChatGPT App and Codex Plugin Directory

The public OpenAI path is app submission through the OpenAI Platform dashboard. Submit the hosted MCP endpoint, OAuth credentials, app metadata, screenshots, test prompts, privacy policy, terms, and review credentials. When an approved app is published, OpenAI creates the Codex plugin distribution for that app.

Important operational rule: OpenAI snapshots MCP metadata during app draft scanning. Server-only fixes can ship without resubmission only when they preserve the published tool contract. Removing or renaming tools requires a new reviewed version and can break existing users if deployed early.

### Repo-Local Codex Plugin

This repo includes a development/workspace plugin at:

```text
plugins/interview-prep-mcp
```

The plugin bundles:

- `.codex-plugin/plugin.json` for plugin metadata.
- `.mcp.json` pointing at the hosted Railway MCP endpoint.
- `skills/interview-prep/SKILL.md` for tool-use workflow guidance.
- `.agents/plugins/marketplace.json` so Codex can discover the plugin from this repo.

Build a shareable archive for review or manual distribution with:

```bash
python3 scripts/package_plugin.py
```

The archive is written to `dist/interview-prep-mcp-<version>.plugin.zip` and is intentionally ignored by git.

After cloning the repo, add the repo marketplace if Codex does not discover it automatically:

```bash
codex plugin marketplace add .
```

Then install `interview-prep-mcp` from the repo marketplace and complete OAuth when prompted.

### Claude

Claude can use the same hosted MCP endpoint:

```text
https://interview-and-learning-data-mcp-production.up.railway.app/mcp
```

For public use, Claude should connect through the same OAuth-backed identity model as ChatGPT/Codex. Static bearer mode is acceptable only for private API-style testing.

## Better Product Implementation Path

Short term:

- Keep the MCP server focused and headless.
- Use the bundled plugin skill to make agents follow the review loop consistently.
- Configure and test a public OIDC provider integration using [oidc-provider-setup.md](./oidc-provider-setup.md).
- Replace placeholder support contact and Railway domain with production values.
- Use `scripts/manage_public_urls.py` to update plugin distribution metadata when replacing the Railway domain.
- Run `scripts/release_check.py` before tagging or submitting a public build.
- Build a plugin archive with `scripts/package_plugin.py` when a reviewer or teammate needs a file artifact.
- Build an app submission packet with `scripts/build_submission_packet.py` when copying metadata into review or store workflows.
- Build an MCP contract snapshot with `scripts/build_mcp_contract_snapshot.py` before comparing reviewed tool metadata between versions.
- Compare reviewed and new snapshots with `scripts/diff_mcp_contract.py` before deploying metadata-affecting changes.
- Run `scripts/check_production_config.py` with production environment variables before deployment.
- Run `scripts/verify_public_deployment.py` against the production domain after each deployment.
- For private reviewer deployments that intentionally use approval-secret OAuth before OIDC is live, run `scripts/verify_public_deployment.py --allow-private-oauth`; final public launch should pass without that flag.
- Run `scripts/verify_authenticated_mcp.py` against the production MCP URL with a reviewer/test bearer token after auth is configured.
- Seed reviewer-safe demo data with `scripts/seed_demo_data.py` for the exact reviewer token subject.

Medium term:

- Add a minimal account/data portal for export and deletion.
- Add a read-only progress dashboard after the MCP flow is stable.
- Add structured tags to `model_notes` only after enough real attempts show useful categories.
- Add durable distributed rate limiting and abuse monitoring if traffic outgrows one service instance.

Avoid building a separate LLM-specific API. The PRD's single remote MCP server is still the cleanest architecture because ChatGPT, Codex, and Claude can share the same tools and database.
