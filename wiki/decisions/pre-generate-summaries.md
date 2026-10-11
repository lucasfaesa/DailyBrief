---
title: "Decision: Pre-Generate Summaries on Backend"
type: decision
updated_at: 2026-10-11
---

# Decision — Backend Batch Pre-generation

## Context

AI summaries could either be computed on-demand in the client browser or generated in batch upfront on the backend.

## Decision

Pre-generate all article and comment summaries during the backend pipeline run, writing static JSON payloads (`docs/data.json` and `docs/archive/YYYY-MM-DD.json`).

## Justifications

- **Credential Security**: API secrets (`GEMINI_API_KEY`, `GROQ_API_KEY`) stay in GitHub Secrets, never exposed to clients.
- **Predictable API Consumption**: Daily runs execute a fixed batch of requests regardless of how many readers view the site.
- **Instant Client Performance**: The frontend loads static pre-rendered text without client-side inference latency.
- **Offline Availability**: Allows service worker caching of the entire digest for offline PWA reading.

## Relevant Files

- `src/main.py`
- `src/pipeline.py`
- `docs/app.js`
- `docs/data.json`
