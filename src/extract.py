"""
extract.py – Extrai o texto principal de uma URL usando trafilatura.
Fallback: título + descrição do item.
"""
from __future__ import annotations

import logging
from typing import Any

import requests
import trafilatura

logger = logging.getLogger(__name__)


def extract_text(item: dict[str, Any], cfg: dict) -> str:
    """
    Tenta extrair o texto da matéria.
    Retorna string com no máximo `max_chars` caracteres.
    """
    max_chars: int = cfg["extraction"]["max_chars"]
    timeout: int = cfg["extraction"]["timeout_seconds"]
    url: str = item["url"]

    # Heurística: URLs do próprio Reddit ou HN não têm artigo para extrair
    skip_domains = {"reddit.com", "news.ycombinator.com", "redd.it"}
    from urllib.parse import urlparse
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
            logger.debug("trafilatura falhou para %s: %s", url, exc)

    if text:
        return text[:max_chars]

    # Fallback: título + descrição
    fallback = f"{item['title']}\n\n{item.get('description', '')}".strip()
    return fallback[:max_chars]
