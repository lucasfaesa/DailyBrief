---
title: Gotchas and Caveats
type: gotchas
updated_at: 2026-10-11
---

# Gotchas — DailyBrief

Known issues, subtle operational behaviors, and non-obvious code paths.

---

## 1. Undated Items Are Always Included

In `src/collect.py` (`_within()`), if `ts is None`, it returns `True`.
Rationale: Better to include undated items than drop real stories.
Caveat: Broken feeds lacking publication timestamps may persist across runs.

## 2. `flair_filter` Config Is Unimplemented

`config.yaml` provides `flair_filter: null` per subreddit, but `collect_reddit()` does not filter by flair. Filtering requires custom logic in the feed reader loop.

## 3. `git filter-repo` Removes the `origin` Remote

Running `git filter-repo` deletes git remotes by default for safety. You must re-add origin manually:
```bash
git remote add origin <url>
```

## 4. Raw `comments` Are Stripped from `data.json`

In `src/main.py` (`build_output()`), raw comment strings are omitted before writing `docs/data.json`. Only LLM-generated summaries (`resumo_comentarios` / `comments_summary`) are exposed.

## 5. URL Deduplication Trims Query Parameters

`deduplicate()` normalizes URLs via `url.split("?")[0].rstrip("/")`. Sites using query strings for article IDs might experience collisions.

## 6. HN Comments Only Fetch Direct Children

`collect_hn()` queries only root comment IDs under `data["kids"]` (depth 1). Nested replies are omitted.

## 7. Reddit Rate Limit (~1 request/min)

Unauthenticated Reddit allows about one request per minute per IP. `collect_reddit()` paces itself on the `x-ratelimit-*` headers, so every subreddit in `config.yaml` adds ~1 min to the run, and Reddit comments are not fetched. OAuth apps now need Reddit's approval.

## 8. Provider Circuit Breaker Is Per-Execution

`_exhausted` in `src/llm.py` is in-memory only. Every GitHub Actions run starts with clean provider state.

## 9. Service Worker Cache Version

`sw.js` hardcodes `CACHE_VERSION = 'dailybrief-v1'`. Update this string whenever editing shell files to invalidate browser caches.
