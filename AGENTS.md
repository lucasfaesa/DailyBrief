# AGENTS.md — Protocol for AI Agents Working on This Repository

This file defines the rules and protocols that any AI agent (Claude, Gemini, GPT, etc.) must follow when working in this codebase.

---

## 1. Before Editing Any Code

1. Read [`wiki/index.md`](wiki/index.md) to understand the project map.
2. Read the wiki pages relevant to the module you intend to change.
3. If changing LLM/routing logic → read `wiki/architecture/llm.md`.
4. If changing data collection sources → read `wiki/architecture/collect.md`.
5. If modifying frontend/site → read `wiki/architecture/site.md` and `wiki/architecture/pwa.md`.

## 2. After Making Relevant Changes

1. Update the affected wiki pages in `wiki/architecture/` or `wiki/decisions/`.
2. Update the page summary in `wiki/index.md` if the page scope changed.
3. Append a single line to the end of `wiki/log.md` using the format:
   ```
   ## [YYYY-MM-DD] type | brief description
   ```
   Valid types: `feat`, `fix`, `refactor`, `docs`, `config`, `chore`.

## 3. New Architectural Decisions

If you introduce a non-trivial architectural decision (e.g. replacing an LLM provider, altering caching strategies, introducing new data sources), create a new page in `wiki/decisions/` with YAML frontmatter and document it in `wiki/log.md`.

## 4. Contradictions Between Wiki and Code

The code is always the source of truth. If you find a discrepancy:
1. Fix the wiki page so it reflects the actual code.
2. Log the fix in `wiki/log.md`: `## [YYYY-MM-DD] docs | fixed: <description>`.

## 5. Strict Constraints

- Never expose or write secrets, API keys, or access tokens into any file.
- Never invent behaviors in the wiki that do not exist in the code.
- Never remove entries from `wiki/log.md` (it is append-only).
- Do not alter the structure of `data.json` without updating `wiki/architecture/site.md`.
