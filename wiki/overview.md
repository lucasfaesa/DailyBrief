---
title: Project Overview
type: overview
updated_at: 2026-10-11
---

# DailyBrief — Overview

## Purpose

A 100% automated, cloud-hosted news digest system that:
1. Gathers news and discussions across the last 24 hours from diverse sources.
2. Extracts article bodies using DOM-less heuristics.
3. Categorizes, scores relevance, and generates structured summaries via LLMs.
4. Deploys an offline-ready mobile web app via GitHub Pages.

Runs entirely serverless within GitHub Actions without requiring any local hardware.

## Technology Stack

| Layer | Technology |
|-------|------------|
| CI/CD | GitHub Actions (cron + `workflow_dispatch`) |
| Runtime | Python 3.11 |
| Data Ingestion | `requests`, `feedparser` |
| Text Extraction | `trafilatura` |
| Configuration | `config.yaml` (`pyyaml`) |
| Primary LLM | Google Gemini (`gemini-2.0-flash`) via `google-generativeai` |
| Fallback LLM | Groq (`llama-3.3-70b-versatile`) via `groq` |
| Web Application | Vanilla HTML5 / CSS3 / ES Modules (zero build step) |
| Hosting | GitHub Pages (served from `/docs`) |
| PWA Support | Service Worker (`sw.js`) + Web App Manifest |

## End-to-End Pipeline

```
GitHub Actions (Cron at 10:00 & 23:00 UTC)
    │
    ├─ src/main.py
    │       ├─ collect_all()          ← src/collect.py
    │       │     ├─ HN Firebase REST API
    │       │     ├─ Reddit RSS + .json comment threads
    │       │     └─ Curated RSS feeds
    │       │
    │       ├─ process_items()        ← src/pipeline.py
    │       │     ├─ extract_text()   ← src/extract.py (trafilatura)
    │       │     ├─ LLMRouter.generate_json()  ← src/llm.py
    │       │     │     └─ Gemini → Groq circuit breaker fallback
    │       │     ├─ Classify (theme, short_summary, relevance: 1-5)
    │       │     └─ If relevance >= 4: article summary + comments breakdown
    │       │
    │       └─ Persist docs/data.json
    │                  docs/archive/YYYY-MM-DD.json
    │                  docs/archive/index.json
    │
    └─ git commit & git push (docs/ only)
           │
           └─ GitHub Pages serves docs/
```

## Related Pages

- [[architecture/collect]] — Collection protocols
- [[architecture/llm]] — LLM routing and resilience
- [[architecture/pipeline]] — Prompts and scoring logic
- [[architecture/site]] — Frontend architecture
