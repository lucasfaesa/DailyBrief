---
title: Wiki Index
type: index
updated_at: 2026-10-11
---

# DailyBrief – Wiki

Catalog of all documentation pages. Start here.

> Before modifying anything, review [[AGENTS.md]] in the project root.

---

## Overview

| Page | Summary |
|------|---------|
| [[overview]] | Purpose, full stack, and end-to-end pipeline flow |
| [[gotchas]] | Known caveats, rate limits, and non-obvious behaviors |
| [[conventions]] | Code patterns, data schemas, and local execution steps |

## Architecture (By Module)

| Page | Primary Source | Summary |
|------|----------------|---------|
| [[architecture/collect]] | `src/collect.py` | News gathering from HN, Reddit, and RSS feeds |
| [[architecture/extract]] | `src/extract.py` | Full-text extraction with trafilatura and fallbacks |
| [[architecture/llm]] | `src/llm.py` | LLM router, circuit breaker, backoff, and JSON parsing |
| [[architecture/pipeline]] | `src/pipeline.py` | Classification prompts, relevance scoring, summaries |
| [[architecture/site]] | `docs/app.js`, `docs/style.css` | SPA hash router, UI rendering, data.json schema |
| [[architecture/pwa]] | `docs/sw.js`, `docs/manifest.json` | Service worker caching, offline capability, install prompt |
| [[architecture/workflow]] | `.github/workflows/daily.yml` | Cron schedules, permissions, automated commits |

## Decisions

| Page | Summary |
|------|---------|
| [[decisions/llm-providers]] | Rationale for Gemini primary with Groq fallback |
| [[decisions/github-pages]] | Rationale for hosting on GitHub Pages from `/docs` |
| [[decisions/pre-generate-summaries]] | Rationale for batch backend pre-generation |
| [[decisions/no-api-key-sources]] | Rationale for using exclusively public/keyless sources |

## Changelog

[[log]] — Append-only chronological history of notable changes.
