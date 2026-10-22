"""
extract.py – Extracts article body text using trafilatura.
Fallback: Item title + description snippet.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests
import trafilatura

logger = logging.getLogger(__name__)

# ── Video sniffing ───────────────────────────────────────────────────────
# og:video is the page's own declared "this is the video for this content" tag —
# a much more reliable signal than scraping for any <video>/<iframe> on the page,
# which would also catch unrelated sidebar/ad players.
_META_TAG_RE = re.compile(r"<meta\s+[^>]*>", re.I)
_OG_VIDEO_PROP_RE = re.compile(r'(?:property|name)\s*=\s*["\']og:video(?::secure_url|:url)?["\']', re.I)
_CONTENT_RE = re.compile(r'content\s*=\s*["\']([^"\']*)["\']', re.I)
_DIRECT_VIDEO_RE = re.compile(r"\.(?:mp4|webm|mov)(?:\?|$)", re.I)
_YT_RE = re.compile(r"(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([\w-]+)")
_VIMEO_RE = re.compile(r"vimeo\.com/(?:video/)?(\d+)")


def _find_og_video(html: str) -> str | None:
    for tag in _META_TAG_RE.findall(html):
        if _OG_VIDEO_PROP_RE.search(tag):
            m = _CONTENT_RE.search(tag)
            if m and m.group(1):
                return m.group(1)
    return None


def _classify_video(raw_url: str | None) -> dict | None:
    if not raw_url:
        return None
    url = raw_url.replace("&amp;", "&")
    m = _YT_RE.search(url)
    if m:
        return {"type": "iframe", "url": f"https://www.youtube.com/embed/{m.group(1)}"}
    m = _VIMEO_RE.search(url)
    if m:
        return {"type": "iframe", "url": f"https://player.vimeo.com/video/{m.group(1)}"}
    if _DIRECT_VIDEO_RE.search(url):
        return {"type": "video", "url": url}
    if url.startswith("http"):
        # ponytail: unknown player, trust the page's own og:video and embed it as-is;
        # a site that blocks cross-origin framing (X-Frame-Options) just won't render
        return {"type": "iframe", "url": url}
    return None


def extract_text(item: dict[str, Any], cfg: dict) -> str:
    """
    Extracts main article text from source URL.
    Returns string capped at cfg['extraction']['max_chars'].
    """
    max_chars: int = cfg["extraction"]["max_chars"]
    timeout: int = cfg["extraction"]["timeout_seconds"]
    url: str = item["url"]

    # Heuristic: Discussion aggregator URLs have no article content to scrape
    # Google News links land on a JS redirect page, not the article
    skip_domains = {"reddit.com", "news.ycombinator.com", "redd.it", "news.google.com"}
    domain = urlparse(url).netloc.lstrip("www.")

    text: str | None = None

    if not any(domain.endswith(d) for d in skip_domains):
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (compatible; DailyBrief/1.0)"},
            )
            resp.raise_for_status()
            text = trafilatura.extract(
                resp.text,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
            )
            item["video"] = _classify_video(_find_og_video(resp.text))
        except Exception as exc:
            logger.debug("trafilatura extraction failed for %s: %s", url, exc)

    if text:
        return text[:max_chars]

    # Graceful fallback: title + description
    fallback = f"{item['title']}\n\n{item.get('description', '')}".strip()
    return fallback[:max_chars]
