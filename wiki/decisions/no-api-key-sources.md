---
title: "Decision: Ingest Only API-Key-Free Sources"
type: decision
updated_at: 2026-10-11
---

# Decision — Keyless Data Sources

## Context

Aggregating diverse news and community reactions requires access to reliable feeds and discussion threads without operational friction.

## Decision

Rely exclusively on open sources that require no developer tokens:
1. **Hacker News**: Public Firebase REST API (`hacker-news.firebaseio.com`).
2. **Reddit**: Public RSS feeds (`/r/<sub>/top/.rss?t=day`) and unauthenticated JSON comment endpoints with descriptive User-Agent headers.
3. **News Feeds**: Standard public RSS/Atom feeds (BBC, Reuters, TechCrunch, etc.).

## Justifications

- **Zero Setup Friction**: Users can fork and run the project immediately by configuring only their LLM keys.
- **Lower Operational Overhead**: Eliminates API token rotations, developer registration portals, or rate tier billing for news aggregators.

## Relevant Files

- `src/collect.py`
- `config.yaml`
