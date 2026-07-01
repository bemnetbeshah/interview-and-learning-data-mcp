# OIDC Provider Setup Runbook

Use this runbook when turning the hosted MCP server from private review into a public multi-user service.

The MCP server does not create public accounts itself. A real identity provider owns login, consent, token issuance, and reviewer credentials. The server validates JWT access tokens and uses the configured subject claim as the database owner key.

## Provider Choice

Pick a provider that can issue asymmetric JWT access tokens and publish a JWKS endpoint. Good fits include Auth0, Clerk, WorkOS, Cognito, or another OIDC provider with custom API audiences and scopes.

For v1, prefer the provider that is fastest to configure correctly:

| Need | What to verify |
| --- | --- |
| Public login | Hosted OAuth login page supports ChatGPT/Codex/Claude browser flows. |
| JWT access tokens | Access tokens are signed JWTs, not opaque strings. |
| JWKS | Public HTTPS key set is available for verification. |
| Audience | Token `aud` can equal `interview-prep-mcp` or a stable API identifier. |
| Subject | Token has a stable per-user `sub` claim. |
| Grants | Token includes `study:read` and `study:write` in a claim accepted by the server. |
| Review | Demo account can log in without MFA, SMS, manual approval, or email challenge. |

Do not use symmetric JWT secrets for public launch. This server is designed for JWKS-backed verification.

## Provider Dashboard Checklist

1. Create an application for the MCP client login flow.
2. Create an API/resource for the MCP server.
3. Set the API audience to `interview-prep-mcp` or another stable identifier.
4. Add scopes or permissions:
   - `study:read`
   - `study:write`
5. Configure access tokens as signed JWTs using RS256, RS384, RS512, ES256, ES384, or ES512.
6. Confirm the issuer URL exactly matches the token `iss` claim.
7. Locate the JWKS URL, usually under the issuer's OIDC discovery metadata.
8. Create a reviewer/demo user with no MFA or manual approval requirement.
9. Make sure the reviewer user receives both study scopes in its access token.

Provider dashboards use different labels. Treat "API identifier", "resource", "audience", and "authorization server audience" as the same concept for this server.

## Railway Environment

Set these values in Railway or the selected host:

```text
MCP_TRANSPORT=streamable-http
MCP_HOST=0.0.0.0
MCP_PUBLIC_BASE_URL=https://<stable-domain>
MCP_RESOURCE_SERVER_URL=https://<stable-domain>/mcp
MCP_ALLOW_UNAUTHENTICATED_HTTP=false

DATABASE_URL=<production-postgres-url>

OIDC_ISSUER_URL=https://<provider-issuer>
OIDC_JWKS_URL=https://<provider-issuer>/.well-known/jwks.json
OIDC_AUDIENCE=interview-prep-mcp
OIDC_SUBJECT_CLAIM=sub
OIDC_REQUIRED_SCOPES=study:read study:write

OAUTH_LOGIN_SECRET=
MCP_BEARER_TOKEN=
RATE_LIMIT_PER_MINUTE=120
PUBLIC_CONTACT_EMAIL=<real-support-email>
```

Run the config gate with those environment variables loaded:

```bash
python3 scripts/check_production_config.py
```

For public launch, this command should pass without `--allow-private-oauth`.

## Token Inspection

Before submitting for review, inspect one reviewer access token and confirm:

| Claim | Expected |
| --- | --- |
| `iss` | Matches `OIDC_ISSUER_URL`. |
| `aud` | Matches `OIDC_AUDIENCE`, unless the provider requires disabling audience verification. |
| `sub` | Stable reviewer subject used for demo data seeding. |
| `exp` | Present and in the future. |
| scopes/grants | Includes `study:read` and `study:write`. |

Accepted grant claim names are `scope`, `scp`, `permissions`, `roles`, and `role`.

Seed reviewer data for the exact subject claim:

```bash
DATABASE_URL=... python3 scripts/seed_demo_data.py --subject <reviewer-subject> --with-attempts
```

## Hosted Verification

After deployment:

```bash
python3 scripts/verify_public_deployment.py https://<stable-domain>
MCP_AUTH_TOKEN=<reviewer-access-token> python3 scripts/verify_authenticated_mcp.py https://<stable-domain>/mcp
```

The public verifier should pass without `--allow-private-oauth`. The authenticated verifier proves the reviewer token can initialize MCP, list tools/prompts, and render a review prompt.

## Review Failure Triage

| Symptom | Likely cause |
| --- | --- |
| Client gets unauthorized after login | Access token is opaque, signed with unsupported algorithm, wrong issuer, wrong audience, missing JWKS, or missing scopes. |
| Reviewer sees empty data | Demo data was seeded for the wrong subject claim. Decode the reviewer token and reseed with that exact `sub` or configured subject claim. |
| Public verifier fails health auth checks | Deployment still has private OAuth, static bearer auth, or unauthenticated HTTP enabled. |
| App review asks for login help | Reviewer account has MFA, SMS, email challenge, manual approval, or missing consent preconfiguration. |
