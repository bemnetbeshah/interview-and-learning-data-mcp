---
name: interview-prep
description: Use when a user wants to manage study areas, quiz on due subtopics, log interview prep attempts, or review spaced-repetition progress through the Interview Prep MCP server.
---

# Interview Prep MCP

Use the bundled `interview_prep` MCP server as the source of truth for study progress. Do not keep durable study state only in chat.

## Workflow

1. Call `get_due_subtopics` before starting a review session unless the user asks for a specific study or topic.
2. Quiz the user conversationally on one due subtopic at a time.
3. After the user answers, choose a 1-5 SM-2 score and call `log_attempt` with concise grading notes and the question asked.
4. Use `get_subtopic_history` before making claims about long-term progress or repeated weak spots.
5. When the user wants to add material, read the current hierarchy first with `list_studies`, `list_topics`, or `list_subtopics` so you do not create obvious duplicates.
6. Use `create_study`, `create_topic`, `create_subtopic`, and `update_subtopic` only for changes the user requested or approved.
7. Use `delete_study`, `delete_topic`, and `delete_subtopic` for hierarchy cleanup. These are soft deletes: the active item disappears, but history is preserved.
8. Use `export_my_data` when the user asks to export or inspect all stored account data.
9. Use `delete_my_data` only after the user explicitly asks to delete all stored study data and confirms the exact phrase `DELETE MY STUDY DATA`.

## Safety And Data Handling

- Do not ask for, invent, or pass a user id. The hosted MCP server derives identity from auth.
- Do not expose auth subjects, access tokens, OAuth records, secrets, request ids, or internal diagnostics in routine responses.
- Do not store passwords, API keys, regulated medical records, financial account data, or other high-risk sensitive information as study content.
- Do not call `log_attempt` before the user has answered the quiz question.
- If a tool says an id was not found, treat it as unavailable for this authenticated account; do not guess alternate ids.
- For account deletion, explain the consequence first and wait for the exact confirmation phrase before calling `delete_my_data`.

## Scoring

- `1`: blackout or no usable recall.
- `2`: incorrect, but some familiarity.
- `3`: correct with effort or meaningful gaps.
- `4`: mostly correct with minor issues.
- `5`: fluent, complete recall.

## Useful Tool Routing

- Due review: `get_due_subtopics` -> quiz -> `log_attempt`.
- Specific progress: `list_studies` -> `list_topics` -> `list_subtopics` -> `get_subtopic_history`.
- New plan: inspect existing hierarchy, propose a concise structure, then create only approved studies/topics/subtopics.
- Export or deletion request: route through `export_my_data` or confirmation-gated `delete_my_data`.
