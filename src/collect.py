"""
collect.py – Ingests news stories from Hacker News, Reddit, and RSS feeds.
Returns a normalized list of item dictionaries deduplicated by URL.
"""
from __future__ import annotations

import calendar
import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urlparse
import re

import feedparser
import requests

logger = logging.getLogger(__name__)

# ── Types ──────────────────────────────────────────────────────────────────

def make_item(
    url: str,
    title: str,
    source: str,
    published: datetime | None = None,
    comments: list[str] | None = None,
    description: str = "",
    category_hint: str = "others",
) -> dict[str, Any]:
    """Creates a normalized news item."""
    # Stable 12-char ID derived from URL
    item_id = hashlib.sha1(url.encode()).hexdigest()[:12]
    return {
        "id": item_id,
        "url": url,
        "title": title.strip(),
        "source": source,
        "published": published.isoformat() if published else datetime.now(timezone.utc).isoformat(),
        "comments": comments or [],
        "description": description.strip(),
        "category_hint": category_hint,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _http_get(url: str, headers: dict | None = None, timeout: int = 15) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None


def _cutoff(hours: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def _within(ts: float | None, cutoff: datetime) -> bool:
    if ts is None:
        return True  # Missing timestamp → include rather than omit
    return datetime.fromtimestamp(ts, tz=timezone.utc) >= cutoff


# ── Hacker News ────────────────────────────────────────────────────────────

def collect_hn(cfg: dict) -> list[dict]:
    """Collects top stories and root comments from Hacker News."""
    limit: int = cfg["hacker_news"]["top_stories_limit"]
    max_comments: int = cfg["hacker_news"]["max_comments"]
    lookback: int = cfg["collection"]["lookback_hours"]
    cutoff = _cutoff(lookback)

    resp = _http_get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not resp:
        return []

    ids = resp.json()[:limit]
    items: list[dict] = []

    for story_id in ids:
        r = _http_get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        if not r:
            continue
        data = r.json()
        if not data or data.get("type") != "story":
            continue
        if not _within(data.get("time"), cutoff):
            continue

        url = data.get("url", f"https://news.ycombinator.com/item?id={story_id}")
        title = data.get("title", "")
        if not title:
            continue

        # Collect direct child comment texts
        comments: list[str] = []
        for kid_id in (data.get("kids") or [])[:max_comments]:
            kr = _http_get(f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json")
            if not kr:
                continue
            kid = kr.json()
            if kid and kid.get("text"):
                text = kid["text"].replace("<p>", "\n").replace("</p>", "")
                text = re.sub(r"<[^>]+>", "", text)
                comments.append(text.strip())
            time.sleep(0.05)  # Respect API limits

        published = datetime.fromtimestamp(data["time"], tz=timezone.utc) if data.get("time") else None
        items.append(make_item(
            url=url,
            title=title,
            source="Hacker News",
            published=published,
            comments=comments,
            description=f"HN score: {data.get('score', 0)} | {data.get('descendants', 0)} comments",
            category_hint="technology",
        ))

    logger.info("HN: collected %d items", len(items))
    return items


# ── Reddit ─────────────────────────────────────────────────────────────────

def _reddit_wait(resp: requests.Response) -> None:
    """Unauthenticated Reddit allows ~1 request/min; sleeping until the window resets beats a silent 429."""
    if float(resp.headers.get("x-ratelimit-remaining", 1)) < 1:
        time.sleep(float(resp.headers.get("x-ratelimit-reset", 60)) + 1)


def collect_reddit(cfg: dict) -> list[dict]:
    """Collects top posts via Reddit RSS, paced to the unauthenticated rate limit (no comments: each costs a minute)."""
    ua = cfg["reddit"]["user_agent"]
    limit_per: int = cfg["collection"]["max_items_per_source"]
    lookback: int = cfg["collection"]["lookback_hours"]
    cutoff = _cutoff(lookback)
    headers = {"User-Agent": ua}

    items: list[dict] = []

    for sub_cfg in cfg["reddit"]["subreddits"]:
        sub = sub_cfg["name"]
        rss_url = f"https://www.reddit.com/r/{sub}/top/.rss?t=day&limit={limit_per}"
        try:
            resp = requests.get(rss_url, headers=headers, timeout=15)
        except requests.RequestException as exc:
            logger.warning("Reddit r/%s failed: %s", sub, exc)
            continue
        if resp.status_code == 429:
            _reddit_wait(resp)
            resp = requests.get(rss_url, headers=headers, timeout=15)
        _reddit_wait(resp)
        if not resp.ok:
            logger.warning("Reddit r/%s: HTTP %d", sub, resp.status_code)
            continue
        feed = feedparser.parse(resp.content)

        for entry in feed.entries[:limit_per]:
            pub_ts = calendar.timegm(entry.published_parsed) if entry.get("published_parsed") else None
            if not _within(pub_ts, cutoff):
                continue

            link = entry.get("link", "")
            title = entry.get("title", "")
            if not link or not title:
                continue

            published = datetime.fromtimestamp(pub_ts, tz=timezone.utc) if pub_ts else None
            description = entry.get("summary", "")[:500]
            items.append(make_item(
                url=link,
                title=title,
                source=f"Reddit /r/{sub}",
                published=published,
                description=description,
                category_hint=sub_cfg.get("category_hint", "others"),
            ))

    logger.info("Reddit: collected %d items", len(items))
    return items


# ── RSS Feeds ──────────────────────────────────────────────────────────────

def collect_rss(cfg: dict) -> list[dict]:
    """Ingests news entries from configured RSS feeds."""
    limit_per: int = cfg["collection"]["max_items_per_source"]
    default_lookback: int = cfg["collection"]["lookback_hours"]

    items: list[dict] = []

    for feed_cfg in cfg.get("rss_feeds", []):
        name: str = feed_cfg["name"]
        url: str = feed_cfg["url"]
        hint: str = feed_cfg.get("category_hint", "others")
        # Low-frequency blogs (e.g. engine dev) would almost never post inside the default window
        cutoff = _cutoff(feed_cfg.get("lookback_hours", default_lookback))

        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            logger.warning("RSS feed %s failed: %s", name, exc)
            continue

        count = 0
        for entry in feed.entries:
            if count >= limit_per:
                break

            # Atom feeds often carry only <updated>; without it, old posts slipped through as "no date"
            parsed = entry.get("published_parsed") or entry.get("updated_parsed")
            pub_ts = calendar.timegm(parsed) if parsed else None
            if not _within(pub_ts, cutoff):
                continue

            link = entry.get("link", "")
            title = entry.get("title", "")
            if not link or not title:
                continue

            published = datetime.fromtimestamp(pub_ts, tz=timezone.utc) if pub_ts else None
            description = entry.get("summary", entry.get("description", ""))[:500]

            items.append(make_item(
                url=link,
                title=title,
                source=name,
                published=published,
                comments=[],
                description=description,
                category_hint=hint,
            ))
            count += 1

    logger.info("RSS: collected %d items", len(items))
    return items


# ── Deduplication ──────────────────────────────────────────────────────────

def deduplicate(items: list[dict]) -> list[dict]:
    """Removes duplicate URLs and titles (same story re-listed under another URL), retaining first discovered item."""
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        url = item["url"].split("?")[0].rstrip("/")
        title = item["title"].casefold()
        if url not in seen and title not in seen:
            seen.update((url, title))
            result.append(item)
    logger.info("Deduplication result: %d unique items", len(result))
    return result


# ── Entrypoint ─────────────────────────────────────────────────────────────

def collect_all(cfg: dict) -> list[dict]:
    """Collects news across all configured sources."""
    all_items: list[dict] = []

    # Reddit spends most of its time sleeping on the rate limit, so it runs alongside HN/RSS
    with ThreadPoolExecutor(max_workers=1) as pool:
        reddit = pool.submit(collect_reddit, cfg) if cfg["reddit"]["enabled"] else None

        if cfg["hacker_news"]["enabled"]:
            all_items.extend(collect_hn(cfg))

        if reddit:
            all_items.extend(reddit.result())

        all_items.extend(collect_rss(cfg))

    return deduplicate(all_items)
