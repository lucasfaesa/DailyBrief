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
- Parsed via `feedparser` with customized `User-Agent`.
- Comments: Fetches `{permalink}.json?limit=100&sort=top` with graceful error handling (`except Exception: pass`).
- Throttles requests with a 500ms delay between subreddits.
- Category hint per subreddit via `category_hint` in `config.yaml` (default `others`).

### RSS Feeds
- Parsed using `feedparser.parse(url)`.
- Applies source-level `category_hint` from `config.yaml`.
- Comments are left empty for standard RSS articles.

## Deduplication

```python
normalized_url = url.split("?")[0].rstrip("/")
```
Preserves the first occurrence discovered. See [[gotchas]] for details on query parameter stripping.
