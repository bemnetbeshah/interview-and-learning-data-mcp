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
| Public base URL | `https://interview-and-learning-data-mcp-production.up.railway.app` |
| MCP endpoint | `https://interview-and-learning-data-mcp-production.up.railway.app/mcp` |
| Volume mount | `/data` |
| Database path | `/data/interview_prep.sqlite3` |

The bearer token is intentionally not written here. It is set in Railway as `MCP_BEARER_TOKEN` and mirrored locally in the gitignored `.env.local` file for connector setup.

## Verified

- Railway deployment status: `SUCCESS`
- Railway instance status: `RUNNING`
- Railway volume state: `READY`
- Public unauthenticated `/mcp` request returns `401`
- Public wrong-token `/mcp` request returns `401`
- Public correct-token `/mcp` request passes auth
- Remote MCP client handshake can list all PRD tools
- Remote MCP tool calls can create hierarchy records, log an attempt, reconnect, and read persisted history
