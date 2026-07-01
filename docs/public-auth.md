# Public Auth Setup

Public launch requires an external OAuth/OIDC identity provider that can issue JWT access tokens for the hosted MCP server. The server validates those tokens and uses one stable JWT claim as `owner_subject`.

## Provider Contract

Choose a provider that can supply all of the following:

| Requirement | Production value |
| --- | --- |
| Issuer URL | HTTPS issuer used in the token `iss` claim. |
| JWKS URL | HTTPS key set for verifying JWT signatures. Defaults to `<issuer>/.well-known/jwks.json` when unset. |
| Audience | Stable API audience for this MCP server, such as `interview-prep-mcp`. |
| Subject | Stable per-user identifier in `sub` or another configured claim. |
| Grants | `study:read` and `study:write` in `scope`, `scp`, `permissions`, `roles`, or `role`. |
| Review account | Demo login with sample data and no MFA, SMS, email challenge, or manual approval. |

The verifier accepts the common grant claims above so providers such as Auth0, Clerk, WorkOS, Cognito, or a custom OAuth server can fit without changing tool schemas. Keep the required grant strings strict for the public app unless a provider forces a different claim model.

For a step-by-step launch checklist, see [oidc-provider-setup.md](./oidc-provider-setup.md).

## Recommended v1 Provider Shape

Use an OAuth provider that supports a first-party API resource and custom API scopes. Configure:

```text
API audience: interview-prep-mcp
Scopes: study:read study:write
Subject claim: sub
Access token format: JWT
Signing algorithm: RS256 or another asymmetric JWT algorithm supported by PyJWT/JWKS
```

Then set the hosted environment:

```text
OIDC_ISSUER_URL=https://issuer.example.com
OIDC_JWKS_URL=https://issuer.example.com/.well-known/jwks.json
OIDC_AUDIENCE=interview-prep-mcp
OIDC_SUBJECT_CLAIM=sub
OIDC_REQUIRED_SCOPES=study:read study:write
```

The OpenAI app submission should use OAuth and the hosted MCP URL. The provider must let ChatGPT complete the login flow without extra manual steps for the review account.

## Supabase Auth Note

Supabase is still a good production Postgres choice for this project. Supabase Auth can also issue JWTs, but confirm the exact JWT signing mode, JWKS URL, audience, and grant claims for the project before using it as the public app identity provider.

Do not point this server at a Supabase JWT secret or symmetric-key-only setup for public launch. This implementation expects JWKS-backed token verification.

## Auth Modes by Stage

| Stage | Mode | Required env |
| --- | --- | --- |
| Local stdio development | No auth | `MCP_TRANSPORT=stdio` |
| Private hosted review | Approval-secret OAuth | `OAUTH_LOGIN_SECRET`, Postgres, HTTPS base URL |
| API smoke testing | Static bearer | `MCP_BEARER_TOKEN`, HTTPS base URL |
| Public launch | External OIDC/JWT | `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, required grants, Postgres |

Never set `MCP_ALLOW_UNAUTHENTICATED_HTTP=true` for public or reviewer-facing deployments.

## Reviewer Account Data

After the reviewer account exists, decode one reviewer access token locally or inspect it in the provider dashboard to find the exact subject claim. Seed sample data for that subject:

```bash
DATABASE_URL=... python3 scripts/seed_demo_data.py --subject <reviewer-subject> --with-attempts
```

The `--subject` value must match the claim configured by `OIDC_SUBJECT_CLAIM`.
