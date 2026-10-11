"""
pipeline.py – Orchestrates text extraction, LLM classification, and summarization.

All prompts in English, output strictly in valid JSON format.
"""
from __future__ import annotations

import logging
from typing import Any

from extract import extract_text
from llm import LLMRouter

logger = logging.getLogger(__name__)

ALLOWED_THEMES = [
    "national_politics",
    "international_politics",
    "technology",
    "ai",
    "gaming",
    "anime",
    "science",
    "economy",
    "others",
]

# Legacy theme mapping for backwards compatibility
THEME_COMPAT = {
    "politica_nacional": "national_politics",
    "politica_internacional": "international_politics",
    "tecnologia": "technology",
    "games": "gaming",
    "animes": "anime",
    "ciencia": "science",
    "economia": "economy",
    "outros": "others",
}

# ── Prompts ───────────────────────────────────────────────────────────────

CLASSIFY_PROMPT = """You are an objective, factual news analyst.
Analyze the article text below and return ONLY a valid JSON object (no Markdown code fences, no explanations).

Required fields:
- "theme": Exactly one of the following values: {themes}
- "short_summary": One concise, objective sentence (maximum 120 characters) in English
- "relevance": An integer from 1 to 5 (5 = extremely significant to the general public)

Rules:
- Be strictly factual. Do not hallucinate details absent from the text.
- Do not include opinions or commentary.
- Return ONLY the raw JSON object.

Title: {title}

Text:
{text}
"""

SUMMARY_PROMPT = """You are an objective, factual news editor.
Review the article below and return ONLY a valid JSON object (no Markdown, no introductory text).

Required fields:
- "article_summary": 4 to 6 concise sentences in English outlining the core developments and context.
  Be factual. Do not invent information absent from the text. Do not include editorial opinion.

Title: {title}

Text:
{text}
"""

COMMENTS_PROMPT = """You are an objective community discussion analyst.
Analyze the reader comments below (user opinions, not verified facts) and return ONLY a valid JSON object.

Required fields:
- "comments_summary": 2 to 4 sentences in English synthesizing dominant perspectives, points of agreement, and disagreements.
  Explicitly frame them as user viewpoints. Do not hallucinate viewpoints not found in the comments.

Comments:
{comments}
"""


# ── Processing Helpers ───────────────────────────────────────────────────

def _normalize_theme(raw_theme: str | None) -> str:
    if not raw_theme:
        return "others"
    raw_theme = raw_theme.lower().strip()
    if raw_theme in ALLOWED_THEMES:
        return raw_theme
    return THEME_COMPAT.get(raw_theme, "others")


def _build_classify_prompt(item: dict, text: str) -> str:
    themes_str = ", ".join(ALLOWED_THEMES)
    return CLASSIFY_PROMPT.format(
        themes=themes_str,
        title=item["title"],
        text=text[:4000],
    )


def _build_summary_prompt(item: dict, text: str) -> str:
    return SUMMARY_PROMPT.format(
        title=item["title"],
        text=text[:5000],
    )


def _build_comments_prompt(comments: list[str]) -> str:
    joined = "\n\n---\n\n".join(comments[:30])
    return COMMENTS_PROMPT.format(comments=joined[:4000])


def _validate_classification(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    theme = _normalize_theme(data.get("theme") or data.get("tema"))
    summary = data.get("short_summary") or data.get("resumo_curto")
    relevance = data.get("relevance") or data.get("relevancia")
    return (
        theme in ALLOWED_THEMES
        and isinstance(summary, str)
        and isinstance(relevance, int)
        and 1 <= relevance <= 5
    )


def process_items(items: list[dict], cfg: dict, router: LLMRouter) -> list[dict]:
    """
    For each item:
      1. Extracts full text
      2. Classifies via LLM (theme, short_summary, relevance)
      3. If relevance >= threshold: generates article_summary and comments_summary
    """
    threshold: int = cfg["collection"]["relevance_threshold"]
    max_high: int = cfg["collection"]["max_high_relevance"]
    high_relevance_count = 0

    for idx, item in enumerate(items):
        logger.info("[%d/%d] Processing: %s", idx + 1, len(items), item["title"][:80])

        # 1. Extract text
        text = extract_text(item, cfg)

        # 2. Classify
        classify_data = router.generate_json(_build_classify_prompt(item, text))

        if classify_data and _validate_classification(classify_data):
            theme = _normalize_theme(classify_data.get("theme") or classify_data.get("tema"))
            short_summary = classify_data.get("short_summary") or classify_data.get("resumo_curto")
            relevance = classify_data.get("relevance") or classify_data.get("relevancia")
        else:
            # Fallback values
            logger.warning("  → Classification fallback for: %s", item["title"][:60])
            theme = _normalize_theme(item.get("category_hint", "others"))
            short_summary = item["title"][:120]
            relevance = 1

        item["theme"] = theme
        item["tema"] = theme  # Backwards compatibility
        item["short_summary"] = short_summary
        item["resumo_curto"] = short_summary
        item["relevance"] = relevance
        item["relevancia"] = relevance

        logger.info("  → theme=%s | relevance=%d", theme, relevance)

        # 3. In-depth summaries for high-relevance items
        if relevance >= threshold and high_relevance_count < max_high:
            high_relevance_count += 1

            # Article summary
            summary_data = router.generate_json(_build_summary_prompt(item, text))
            if summary_data:
                article_summary = summary_data.get("article_summary") or summary_data.get("resumo_materia")
                if isinstance(article_summary, str):
                    item["article_summary"] = article_summary
                    item["resumo_materia"] = article_summary

            # Comments summary (optional)
            comments = item.get("comments", [])
            if comments:
                comments_data = router.generate_json(_build_comments_prompt(comments))
                if comments_data:
                    comments_summary = comments_data.get("comments_summary") or comments_data.get("resumo_comentarios")
                    if isinstance(comments_summary, str):
                        item["comments_summary"] = comments_summary
                        item["resumo_comentarios"] = comments_summary

    router.print_summary()
    return items
