---
title: Change Log
type: log
updated_at: 2026-10-11
---

# Log — DailyBrief

Chronological, append-only log. Never delete historical entries.
Format: `## [YYYY-MM-DD] type | description`

---

## [2026-10-11] feat | initial project setup

Complete pipeline created: automated collection (HN + Reddit + RSS), extraction (trafilatura), resilient LLM layer with circuit breaker fallback (Gemini → Groq), mobile PWA site (vanilla HTML/CSS/JS), GitHub Actions workflow with dual daily cron.

## [2026-10-11] config | added second daily run

Workflow updated to run twice daily: 07:00 and 20:00 America/Sao_Paulo (10:00 and 23:00 UTC) via `.github/workflows/daily.yml`.

## [2026-10-11] chore | purged README.md from git history

Removed README.md and rewritten git tree using `git filter-repo --path README.md --invert-paths`.

## [2026-10-11] docs | project wiki created

Generated 18 wiki documentation pages: index, log, overview, gotchas, conventions, 7 architecture modules, 4 architectural decisions, AGENTS.md, and CLAUDE.md.

## [2026-10-11] refactor | converted codebase and documentation to English

Translated all documentation, wiki pages, code docstrings/comments, pipeline prompts, and frontend text to English.
