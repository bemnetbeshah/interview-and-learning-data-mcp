# Portable Agent Entry Point

The authoritative agent instructions live in [AGENTS.md](./AGENTS.md).

## Project Summary

This project defines a personal Interview Prep MCP server that gives Claude and ChatGPT shared, persistent access to Bem's study progress. The working product source of truth is [interview_prep_mcp_prd.md](./interview_prep_mcp_prd.md); the `.docx` file is the original draft.

## Getting Started

1. Read [AGENTS.md](./AGENTS.md).
2. Read [interview_prep_mcp_prd.md](./interview_prep_mcp_prd.md) before making product or implementation decisions.
3. Keep the Markdown PRD updated as the working version.

## Critical Conventions

- Use the hierarchy Study -> Topic -> Subtopic.
- Progress is tracked at the subtopic level.
- The server owns SM-2 scheduling logic; LLM clients call tools and do not compute review intervals themselves.
- Keep [index.md](./index.md) current when files are added, removed, or renamed.
