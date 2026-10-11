"""
extract.py – Extracts article body text using trafilatura.
Fallback: Item title + description snippet.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import requests
import trafilatura

logger = logging.getLogger(__name__)


def extract_text(item: dict[str, Any], cfg: dict) -> str:
    """
    Extracts main article text from source URL.
    Returns string capped at cfg['extraction']['max_chars'].
    """
    max_chars: int = cfg["extraction"]["max_chars"]
    timeout: int = cfg["extraction"]["timeout_seconds"]
    url: str = item["url"]

    # Heuristic: Discussion aggregator URLs have no article content to scrape
    skip_domains = {"reddit.com", "news.ycombinator.com", "redd.it"}
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
        except Exception as exc:
            logger.debug("trafilatura extraction failed for %s: %s", url, exc)

    if text:
        return text[:max_chars]

    # Graceful fallback: title + description
    fallback = f"{item['title']}\n\n{item.get('description', '')}".strip()
    return fallback[:max_chars]
