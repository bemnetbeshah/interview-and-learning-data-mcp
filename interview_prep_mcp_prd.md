# Interview Prep MCP Server

Product Requirements Document

Owner: Bem  
Status: Public-facing implementation branch
Last updated: June 24, 2026

## 1. Overview

Bem currently uses Claude and ChatGPT voice mode as ad-hoc mock interviewers for technical prep, including AI engineering interviews, coursework like Calc 3, and other study areas. The core limitation is that every conversation starts from zero. The model has no memory of which topics were already covered, how well Bem performed, or what is overdue for review.

This PRD defines a Model Context Protocol (MCP) server that gives Claude and ChatGPT shared, persistent access to a user's study progress. The same server, same tools, and same database are used by both clients, which connect independently and reason over identical state for the authenticated user.

## 2. Problem Statement

- Progress does not persist across sessions. Every new chat requires re-explaining context from scratch.
- There is no way to know which topics are weak versus strong without manually remembering.
- There is no spaced repetition. Topics are not resurfaced at the right interval to cement long-term retention.
- Claude and ChatGPT each have their own context, with no shared source of truth between them.

## 3. Goals

- A single MCP server, hosted once, that both Claude via Custom Connector and ChatGPT via Apps SDK connector can call.
- Support multiple public users without leaking studies, topics, subtopics, attempts, or scheduling state across accounts.
- Track progress hierarchically: Study -> Topic -> Subtopic.
- Log every quiz attempt with a quality score and free-text notes from the grading model.
- Run spaced repetition with the SM-2 algorithm server-side so the LLM does not have to do scheduling math. It just asks what is due and gets an answer.
- Support full CRUD on the hierarchy through tool calls, so new study areas can be added conversationally.

### Non-Goals for v1

- No custom UI or dashboard. Interaction happens entirely through LLM tool calls. A read-only dashboard could be a v2 nice-to-have.
- No automatic topic generation. Bem defines studies, topics, and subtopics himself, with LLM assistance through the create tools.
- No admin console or billing system. Public availability means account isolation and hosted access first.

## 4. Architecture

Both Claude and ChatGPT support MCP natively as remote connectors, which means one server can serve both clients identically. There is no need for a separate OpenAI GPT Actions schema.

### Key Constraint

Both Claude's Custom Connectors and ChatGPT's Apps SDK connect to remote MCP servers over the public internet, not a local machine. The server needs to run on an always-on, publicly reachable host. A laptop will not work unless tunneled, and tunneling is not reliable enough for daily use.

### Components

- **MCP Server:** Python with FastMCP or TypeScript, exposing the tool list defined in [Section 6](#6-mcp-tool-definitions).
- **Database:** Postgres. Supabase fits Bem's existing stack and pgvector familiarity, though SQLite works for local prototyping before deployment.
- **Hosting:** A small always-on service such as Railway, Render, or Fly.io, so the server is reachable 24/7 from both Anthropic's and OpenAI's infrastructure.
- **SM-2 scheduling logic:** Lives in the server code, not in the LLM. The LLM calls a tool and receives a computed result. It never has to calculate intervals itself.
- **Distribution wrappers:** OpenAI app submission and Codex plugin packaging should point at the same hosted MCP server instead of introducing a second API.

### System Flow

```text
Claude (web/desktop/mobile)
  -> Custom Connector (MCP, OAuth)
  -> One hosted MCP server

ChatGPT (web/desktop/mobile)
  -> Apps SDK Connector (MCP, OAuth)
  -> One hosted MCP server

One hosted MCP server
  -> Auth: token subject identifies the current user
  -> Tools: list/create/update studies and topics, log_attempt,
            get_due_subtopics, get_history
  -> Postgres: users/subjects, studies, topics, subtopics, attempts, subtopic_state
```

## 5. Data Model

Hierarchy: User -> Study -> Topic -> Subtopic. Progress is tracked at the subtopic level, since that is the granular unit that gets quizzed and improved on.

Every tool call is scoped by the authenticated token subject. User identity is server-derived from OAuth/bearer auth context, not supplied by the model as a tool argument. This prevents a client from reading another user's data by guessing integer ids.

The `attempts` table is an append-only log for full history and trend views. The `subtopic_state` table is a fast-lookup snapshot of current mastery and the spaced-repetition clock, updated after each logged attempt. Splitting these avoids recomputing the whole history just to answer what is due today.

### `studies`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid / int PK | Primary key |
| `owner_subject` | text | Auth subject that owns this study and all nested rows |
| `name` | text | Example: "AI Engineering Interview", "Calc 3", "Computer Vision" |
| `created_at` | timestamp |  |

### `topics`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid / int PK | Primary key |
| `study_id` | FK -> studies |  |
| `name` | text | Example: "Linear Algebra", "Transformers" |
| `order_index` | int | Display ordering |

### `subtopics`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid / int PK | Primary key |
| `topic_id` | FK -> topics |  |
| `name` | text | Example: "Eigenvalues/Eigenvectors", "Multi-head Attention" |
| `description` | text, nullable | What mastery looks like for this subtopic |

### `attempts`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid / int PK | Primary key |
| `subtopic_id` | FK -> subtopics |  |
| `timestamp` | timestamp |  |
| `score` | int, 1-5 | SM-2 style quality rating. 1 = blackout, 5 = perfect recall |
| `model_notes` | text | Free text describing what was right or wrong, in the grading model's words |
| `question_asked` | text, nullable | Optional context when reviewing history |

### `subtopic_state`

| Field | Type | Notes |
| --- | --- | --- |
| `subtopic_id` | FK -> subtopics (PK) | One row per subtopic |
| `mastery_level` | int, 0-100 | Decaying confidence score |
| `ease_factor` | float | SM-2 ease factor, starts around 2.5 |
| `interval_days` | int | Current spacing interval |
| `next_review_date` | date | Drives `get_due_subtopics` |
| `last_reviewed_at` | timestamp |  |
| `consecutive_correct` | int | Streak counter |

## 6. MCP Tool Definitions

All tools below run on the server. The LLM's job is to decide which tool to call and with what arguments. The LLM does not compute scheduling math or hold state in its own context.

### 6.1 Read / Discovery Tools

| Tool | Description | Key args |
| --- | --- | --- |
| `list_studies` | Returns all studies | None |
| `list_topics` | Returns topics within a study | `study_id` |
| `list_subtopics` | Returns subtopics within a topic, with current `mastery_level` | `topic_id` |
| `get_due_subtopics` | Returns spaced-repetition queue, sorted by overdue-ness; optionally scoped to one study | `study_id?`, `limit?` |
| `get_subtopic_history` | Returns past attempts, scores, and trend for one subtopic | `subtopic_id` |
| `export_my_data` | Returns the authenticated user's full study data export | None |

### 6.2 Write Tool: Core Loop

| Tool | Description | Key args |
| --- | --- | --- |
| `log_attempt` | Records a quiz attempt, runs the SM-2 update on `subtopic_state`, and returns the new interval and `next_review_date` | `subtopic_id`, `score`, `model_notes`, `question_asked?` |

### 6.3 Management Tools: CRUD

| Tool | Description | Key args |
| --- | --- | --- |
| `create_study` | Adds a new study area | `name` |
| `create_topic` | Adds a topic under a study | `study_id`, `name` |
| `create_subtopic` | Adds a subtopic under a topic | `topic_id`, `name`, `description?` |
| `update_subtopic` | Edits a subtopic's name or description | `subtopic_id`, `name?`, `description?` |
| `delete_study` | Soft-deletes a study while preserving history | `id` |
| `delete_topic` | Soft-deletes a topic while preserving history | `id` |
| `delete_subtopic` | Soft-deletes a subtopic while preserving history | `id` |
| `delete_my_data` | Hard-deletes all study data for the authenticated user after explicit confirmation | `confirmation` |

## 7. Spaced Repetition Logic: SM-2

Standard SM-2 is scored on the 1-5 scale Bem confirmed:

- **Score <= 2**: "blackout" to "incorrect, but familiar". Reset `interval_days` to 1 and reset `consecutive_correct` to 0. The subtopic resurfaces almost immediately.
- **Score >= 3**: correct, with varying difficulty. Increment `consecutive_correct`. The interval grows using `ease_factor`: first correct repetition -> 1 day, second -> 6 days, subsequent repetitions -> previous interval * `ease_factor`.
- `ease_factor` adjusts each repetition based on score using the standard SM-2 formula, floored at 1.3 so it never collapses to near-zero spacing.
- `mastery_level` from 0-100 is a simpler, human-readable rollup derived from `consecutive_correct` and recent score trend. It is used for display and sorting, while `ease_factor` and `interval_days` drive actual scheduling.

This logic lives entirely in the `log_attempt` tool's server-side implementation. The LLM never sees or manipulates `ease_factor` directly. It calls `log_attempt` with a score and gets back a plain-language next-review result, such as "next review: in 4 days".

## 8. Example End-to-End Flow

1. Bem opens voice mode in ChatGPT or Claude and says, "let's do interview prep."
2. The model calls `get_due_subtopics()` and gets back entries like "Multi-head Attention" overdue by 2 days and "Eigenvalues" due today.
3. The model quizzes Bem conversationally on those subtopics, with no re-explanation needed.
4. After each answer, the model calls `log_attempt(subtopic_id, score, model_notes)`. The server updates the schedule and returns the next review date.
5. The next session, whether the same day or weeks later and whether in the same app or another app, picks up exactly where it left off because the state lives in the shared server, not either app's chat history.

## 9. Decisions Already Made

- Scoring scale: 1-5 classic SM-2 / Anki-style, confirmed by Bem.
- Hierarchy: Study -> Topic -> Subtopic, with progress tracked at the subtopic level.
- Single server architecture serving both Claude and ChatGPT via their respective native MCP connector support. No separate GPT Actions schema is needed.
- Multi-user isolation lives in the service/database boundary. The MCP tool schemas do not expose `user_id`; the server derives the active owner from auth.
- Railway remains the v1 hosting target because it already has the deployed service, public HTTPS, Docker support, and Postgres.
- Public auth is implemented as external OIDC/JWT bearer-token verification. The existing approval-secret OAuth provider remains for private Developer Mode and invite-only testing.
- OIDC/JWT verification is covered by signed-token tests for issuer, audience, subject, expiry, and required study scopes across common provider claim shapes.
- Public account data rights are exposed through `export_my_data` and confirmation-gated `delete_my_data`.
- Public deployments include per-subject in-memory tool-call rate limiting and a deployment verifier script for public pages, health, and unauthenticated MCP rejection.
- Authenticated hosted MCP sessions can be smoke-tested with `scripts/verify_authenticated_mcp.py` once a reviewer/test bearer token is available.
- The production container includes a `/healthz` Docker healthcheck.
- Reviewer-safe demo data can be seeded idempotently for a chosen auth subject with `scripts/seed_demo_data.py`.
- MCP tools include review-relevant annotations for read-only, destructive, idempotent, and open-world behavior.
- Database initialization is idempotent and records applied schema versions in `schema_migrations` for production auditability.
- Production configuration can be checked before deployment with `scripts/check_production_config.py`.
- Railway build/deploy behavior is pinned in `railway.json` so the Dockerfile builder, `/healthz` platform healthcheck, and restart policy travel with the code.
- OpenAI review metadata can be generated with `scripts/build_submission_packet.py` so app listing fields, reviewer prompts, scopes, and tool-contract notes stay aligned with plugin metadata.
- The registered MCP tool/prompt contract can be snapshotted with `scripts/build_mcp_contract_snapshot.py` for review and version comparison.
- Reviewed MCP contract snapshots can be compared with `scripts/diff_mcp_contract.py` to flag breaking metadata changes before deploy or resubmission.
- Plugin distribution URLs can be checked or updated with `scripts/manage_public_urls.py` when moving from the Railway subdomain to a stable custom domain.
- Public distribution should use the OpenAI app submission flow for ChatGPT/Codex and the repo-local Codex plugin only for development/workspace installs until official public plugin self-publishing is available.

## 10. Open Questions

- Auth provider choice for public launch: the branch can validate OIDC/JWT tokens, but deployment still needs a selected provider such as Supabase Auth, Clerk, Auth0, WorkOS, Cognito, or another proper identity provider.
- Whether `model_notes` should be structured, such as tags for "missed edge case" or "conceptual gap", or stay free text for v1.
- Whether `mastery_level` needs its own decay-over-time logic, separate from review scheduling, for a future progress-dashboard view.
- Whether traffic volume justifies distributed rate limiting beyond the current per-process limiter.
