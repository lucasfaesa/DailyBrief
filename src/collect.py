"""
collect.py – Coleta notícias do Hacker News, Reddit e feeds RSS.
Retorna uma lista de dicts normalizados, deduplicada por URL.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urlparse

import feedparser
import requests

logger = logging.getLogger(__name__)

# ── Tipos ──────────────────────────────────────────────────────────────────

def make_item(
    url: str,
    title: str,
    source: str,
    published: datetime | None = None,
    comments: list[str] | None = None,
    description: str = "",
    category_hint: str = "outros",
) -> dict[str, Any]:
    """Cria um item normalizado."""
    # ID estável baseado na URL
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
        # Preenchido pelo pipeline de LLM:
        "tema": None,
        "resumo_curto": None,
        "relevancia": None,
        "resumo_materia": None,
        "resumo_comentarios": None,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _http_get(url: str, headers: dict | None = None, timeout: int = 15) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as exc:
        logger.warning("GET %s falhou: %s", url, exc)
        return None


def _cutoff(hours: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def _within(ts: float | None, cutoff: datetime) -> bool:
    if ts is None:
        return True  # sem data → incluir (melhor ter a mais do que perder)
    return datetime.fromtimestamp(ts, tz=timezone.utc) >= cutoff


# ── Hacker News ────────────────────────────────────────────────────────────

def collect_hn(cfg: dict) -> list[dict]:
    """Coleta os top stories do Hacker News."""
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

        # Comentários: apenas texto plano dos filhos diretos
        comments: list[str] = []
        for kid_id in (data.get("kids") or [])[:max_comments]:
            kr = _http_get(f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json")
            if not kr:
                continue
            kid = kr.json()
            if kid and kid.get("text"):
                # Remove tags HTML simples
                text = kid["text"].replace("<p>", "\n").replace("</p>", "")
                import re
                text = re.sub(r"<[^>]+>", "", text)
                comments.append(text.strip())
            time.sleep(0.05)  # respeita a API

        published = datetime.fromtimestamp(data["time"], tz=timezone.utc) if data.get("time") else None
        items.append(make_item(
            url=url,
            title=title,
            source="Hacker News",
            published=published,
            comments=comments,
            description=f"HN score: {data.get('score', 0)} | {data.get('descendants', 0)} comentários",
            category_hint="tecnologia",
        ))

    logger.info("HN: %d itens coletados", len(items))
    return items


# ── Reddit ─────────────────────────────────────────────────────────────────

def collect_reddit(cfg: dict) -> list[dict]:
    """Coleta posts do Reddit via RSS e tenta buscar comentários via JSON."""
    if not cfg["reddit"]["enabled"]:
        return []

    ua = cfg["reddit"]["user_agent"]
    max_comments: int = cfg["reddit"]["max_comments"]
    limit_per: int = cfg["collection"]["max_items_per_source"]
    lookback: int = cfg["collection"]["lookback_hours"]
    cutoff = _cutoff(lookback)
    headers = {"User-Agent": ua}

    items: list[dict] = []

    for sub_cfg in cfg["reddit"]["subreddits"]:
        sub = sub_cfg["name"]
        rss_url = f"https://www.reddit.com/r/{sub}/top/.rss?t=day&limit={limit_per}"
        feed = feedparser.parse(rss_url, request_headers=headers)

        for entry in feed.entries[:limit_per]:
            pub_ts = time.mktime(entry.published_parsed) if entry.get("published_parsed") else None
            if not _within(pub_ts, cutoff):
                continue

            link = entry.get("link", "")
            title = entry.get("title", "")
            if not link or not title:
                continue

            published = datetime.fromtimestamp(pub_ts, tz=timezone.utc) if pub_ts else None

            # Tenta buscar comentários via JSON
            comments: list[str] = []
            try:
                json_url = link.rstrip("/") + ".json?limit=100&sort=top"
                jr = _http_get(json_url, headers=headers, timeout=10)
                if jr:
                    jdata = jr.json()
                    comment_listing = jdata[1]["data"]["children"] if len(jdata) > 1 else []
                    for c in comment_listing[:max_comments]:
                        body = c.get("data", {}).get("body", "")
                        if body and body not in ("[deleted]", "[removed]"):
                            comments.append(body.strip())
            except Exception:
                pass  # comentários são opcionais

            description = entry.get("summary", "")[:500]
            items.append(make_item(
                url=link,
                title=title,
                source=f"Reddit /r/{sub}",
                published=published,
                comments=comments,
                description=description,
                category_hint="outros",
            ))

        time.sleep(0.5)  # respeita rate limit do Reddit

    logger.info("Reddit: %d itens coletados", len(items))
    return items


# ── RSS Feeds ──────────────────────────────────────────────────────────────

def collect_rss(cfg: dict) -> list[dict]:
    """Coleta itens de feeds RSS configurados."""
    limit_per: int = cfg["collection"]["max_items_per_source"]
    lookback: int = cfg["collection"]["lookback_hours"]
    cutoff = _cutoff(lookback)

    items: list[dict] = []

    for feed_cfg in cfg.get("rss_feeds", []):
        name: str = feed_cfg["name"]
        url: str = feed_cfg["url"]
        hint: str = feed_cfg.get("category_hint", "outros")

        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            logger.warning("RSS %s falhou: %s", name, exc)
            continue

        count = 0
        for entry in feed.entries:
            if count >= limit_per:
                break

            pub_ts = time.mktime(entry.published_parsed) if entry.get("published_parsed") else None
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

    logger.info("RSS: %d itens coletados", len(items))
    return items


# ── Deduplicação ───────────────────────────────────────────────────────────

def deduplicate(items: list[dict]) -> list[dict]:
    """Remove itens com URLs duplicadas, mantendo o primeiro encontrado."""
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        url = item["url"].split("?")[0].rstrip("/")  # normaliza URL
        if url not in seen:
            seen.add(url)
            result.append(item)
    logger.info("Após deduplicação: %d itens únicos", len(result))
    return result


# ── Ponto de entrada ───────────────────────────────────────────────────────

def collect_all(cfg: dict) -> list[dict]:
    """Coleta todas as fontes e retorna lista deduplicada."""
    all_items: list[dict] = []

    if cfg["hacker_news"]["enabled"]:
        all_items.extend(collect_hn(cfg))

    if cfg["reddit"]["enabled"]:
        all_items.extend(collect_reddit(cfg))

    all_items.extend(collect_rss(cfg))

    return deduplicate(all_items)
