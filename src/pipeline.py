"""
pipeline.py – Orchestrates text extraction, LLM classification, and summarization.

Prompts in English; summaries in Brazilian Portuguese; output strictly in valid JSON.
"""
from __future__ import annotations

import logging
from extract import extract_text
from llm import LLMRouter

logger = logging.getLogger(__name__)

ALLOWED_THEMES = [
    "national_politics",
    "international_politics",
    "technology",
    "ai",
    "gaming",
    "game_dev",
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

THEME_GUIDE = """- national_politics: ONLY Brazilian politics — federal/state government, Congress, STF/TSE, elections, parties, public policy, politicians. NOT celebrities, TV, sports, weather, crime or foreign events.
- international_politics: geopolitics, wars, diplomacy, foreign governments and elections.
- technology: software, hardware, internet, gadgets, programming, tech companies.
- ai: artificial intelligence, machine learning, LLMs.
- gaming: video games from the player's side — releases, reviews, trailers, updates, consoles.
- game_dev: game development and the game industry as a business — studio layoffs, closures, hiring, growth, funding, acquisitions, revenue, engines (Unity, Unreal, Godot), dev tools, postmortems, developer working conditions.
- anime: anime, manga, Japanese animation and pop culture.
- science: research, space, health studies, environment science.
- economy: markets, inflation, interest rates, companies' finances, jobs, trade.
- others: everything else (entertainment, celebrities, TV, sports, weather, crime, lifestyle)."""

BATCH_PROMPT = """You are an objective news editor for a Brazilian reader.
Classify and summarize EACH article below. Return ONLY a JSON object: {{"items": [...]}} with one entry per article:
- "id": the article id, unchanged
- "theme": exactly one of: {themes}
- "relevance": integer 1-5 (5 = major news for the general public; 1 = trivial, promotional or clickbait)
- "short_summary": one sentence, max 140 characters, in Brazilian Portuguese
- "summary": 3 to 5 sentences in Brazilian Portuguese with the key facts and context

Theme definitions (follow strictly, the source hint can be wrong):
{guide}

Rules: be strictly factual, use only the given text, no opinions. If the text is only a title, keep the summary short.

{articles}
"""

COMMENTS_PROMPT = """You are an objective community discussion analyst.
Analyze the reader comments below (user opinions, not verified facts) and return ONLY a valid JSON object.

Required fields:
- "comments_summary": 2 to 4 sentences in Brazilian Portuguese synthesizing dominant perspectives, points of agreement, and disagreements.
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


def _build_batch_prompt(batch: list[tuple[dict, str]], text_chars: int) -> str:
    articles = "\n\n".join(
        f"=== id: {item['id']} | source: {item['source']} | hint: {item.get('category_hint')}\n"
        f"Title: {item['title']}\n{text[:text_chars]}"
        for item, text in batch
    )
    return BATCH_PROMPT.format(themes=", ".join(ALLOWED_THEMES), guide=THEME_GUIDE, articles=articles)


def _build_comments_prompt(comments: list[str]) -> str:
    joined = "\n\n---\n\n".join(comments[:30])
    return COMMENTS_PROMPT.format(comments=joined[:4000])


def _apply_result(item: dict, res: dict | None) -> None:
    relevance = res.get("relevance") if res else None
    if not isinstance(relevance, int) or not 1 <= relevance <= 5:
        logger.warning("  → Classification fallback for: %s", item["title"][:60])
        item["theme"] = _normalize_theme(item.get("category_hint"))
        item["short_summary"] = item["title"][:140]
        item["relevance"] = 2  # ponytail: unknown, not trivial — keeps it visible but below classified news
        return
    item["theme"] = _normalize_theme(res.get("theme"))
    item["relevance"] = relevance
    item["short_summary"] = res.get("short_summary") or item["title"][:140]
    if isinstance(res.get("summary"), str):
        item["article_summary"] = res["summary"]


def process_items(items: list[dict], cfg: dict, router: LLMRouter) -> list[dict]:
    """
    1. Extracts full text for every item
    2. Classifies + summarizes in batches (one LLM call per batch_size items)
    3. Summarizes comments for high-relevance items
    4. Drops items below min_relevance
    """
    col = cfg["collection"]
    batch_size: int = col["batch_size"]
    text_chars: int = col["batch_text_chars"]

    texts = []
    for idx, item in enumerate(items):
        logger.info("[%d/%d] Extracting: %s", idx + 1, len(items), item["title"][:80])
        texts.append(extract_text(item, cfg))

    for start in range(0, len(items), batch_size):
        batch = list(zip(items[start:start + batch_size], texts[start:start + batch_size]))
        logger.info("Classifying batch %d-%d", start + 1, start + len(batch))
        data = router.generate_json(_build_batch_prompt(batch, text_chars))
        results = data.get("items") if isinstance(data, dict) else None
        by_id = {r.get("id"): r for r in results if isinstance(r, dict)} if isinstance(results, list) else {}
        for item, _ in batch:
            _apply_result(item, by_id.get(item["id"]))

    high = sorted(
        (i for i in items if i["relevance"] >= col["relevance_threshold"] and i.get("comments")),
        key=lambda i: i["relevance"], reverse=True,
    )[:col["max_high_relevance"]]
    for item in high:
        comments_data = router.generate_json(_build_comments_prompt(item["comments"]))
        if comments_data and isinstance(comments_data.get("comments_summary"), str):
            item["comments_summary"] = comments_data["comments_summary"]

    kept = [i for i in items if i["relevance"] >= col["min_relevance"]]
    logger.info("Kept %d/%d items (min_relevance=%d)", len(kept), len(items), col["min_relevance"])
    router.print_summary()
    return kept
