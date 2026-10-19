---
title: Ingestion Module Architecture
type: architecture
updated_at: 2026-10-11
---

# Architecture — Ingestion (`src/collect.py`)

## Responsibility

Collect raw stories from configured sources, normalize them into a uniform schema, and deduplicate by URL.

## Entry Point

```python
collect_all(cfg: dict) -> list[dict]
```

Orchestrates feeds in order: Hacker News → Reddit → RSS, returning a deduplicated item list.

## Sources

### Hacker News
- Endpoint: `https://hacker-news.firebaseio.com/v0/topstories.json`
- Fetches top `top_stories_limit` story IDs (default: 30).
- Retrieves story metadata via `/item/{id}.json`. Non-story items are ignored.
- Comments: Root comments from `data["kids"]` (depth 1) up to `max_comments`. Includes 50ms pause per request.
- Strips HTML tags via regex. Category hint defaults to `technology`.

### Reddit
- Endpoint: `https://www.reddit.com/r/{sub}/top/.rss?t=day&limit={N}`
- Fetched with `requests` (custom `User-Agent`), parsed via `feedparser`.
- Unauthenticated Reddit allows ~1 request/min per IP. `_reddit_wait()` sleeps until `x-ratelimit-reset` whenever `x-ratelimit-remaining` hits 0, and a 429 is retried once after that wait. Each subreddit therefore costs ~1 min; `collect_all()` runs Reddit in a background thread alongside HN and RSS.
- No comments: each comment fetch would cost another minute of rate limit. (Before 2026-10-19 only the first subreddit ever got through; the rest got silent 429s.)
- Category hint per subreddit via `category_hint` in `config.yaml` (default `others`).

### RSS Feeds
- Parsed using `feedparser.parse(url)`.
- Applies source-level `category_hint` from `config.yaml`.
- Optional per-feed `lookback_hours` overrides the global window (e.g. custom-engine blogs and Espírito Santo concursos feeds use 168h because new entries appear periodically).
- Entry date: `published_parsed`, falling back to `updated_parsed` (Atom feeds often only have `<updated>`).
- Comments are left empty for standard RSS articles.

## Deduplication

```python
normalized_url = url.split("?")[0].rstrip("/")
```
Preserves the first occurrence discovered. See [[gotchas]] for details on query parameter stripping.
