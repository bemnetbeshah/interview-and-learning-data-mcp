# Railway Deployment

Current production deployment:

| Item | Value |
| --- | --- |
| Project | `Interview and Learning Data MCP` |
| Project ID | `10204dea-5b09-45f3-8fc2-961220fb777f` |
| Environment | `production` |
| Environment ID | `b72fa4f2-869a-4619-849f-f345f383dfdb` |
| Service | `Interview and Learning Data MCP` |
| Service ID | `cb1a079a-7d9e-4d63-8b9f-04adac9ec0eb` |
| Postgres service | `Postgres` |
| Postgres service ID | `387f80e2-b34c-4712-b740-09bbf587d810` |
| Public base URL | `https://interview-and-learning-data-mcp-production.up.railway.app` |
| MCP endpoint | `https://interview-and-learning-data-mcp-production.up.railway.app/mcp` |
| Database | Railway Postgres via `DATABASE_URL` |
| Auth mode | OAuth for ChatGPT Developer Mode |

This branch includes [../railway.json](../railway.json) so future deployments use the repo-pinned Dockerfile builder, `/healthz` platform healthcheck, and on-failure restart policy instead of relying only on dashboard settings.

`OAUTH_LOGIN_SECRET` is set in Railway and mirrored locally in the gitignored `.env.local` file. Use that value in the browser approval form during the ChatGPT OAuth connection flow. `MCP_BEARER_TOKEN` is unset in Railway so OAuth is the active hosted auth mode.

## Verified

- Railway deployment status: `SUCCESS`
- Latest app deployment ID: `c8f99c7d-5d04-44d8-b3cc-f45948224844`
- Railway instance status: `RUNNING`
- Railway Postgres is configured through `DATABASE_URL`
- Railway Postgres service status: `SUCCESS` / `RUNNING`
- Public unauthenticated raw `/mcp` request returns `401` with a protected-resource metadata link
- OAuth authorization server metadata is available at `/.well-known/oauth-authorization-server`
- OAuth protected-resource metadata is available at `/.well-known/oauth-protected-resource/mcp`
- Remote MCP client handshake can list all PRD tools after OAuth bearer-token authorization
- Remote MCP tool calls can create hierarchy records in Postgres, log an attempt, reconnect, and read persisted history
