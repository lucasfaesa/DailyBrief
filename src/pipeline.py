"""
pipeline.py – Orchestrates text extraction, LLM classification, and summarization.

Prompts in English; summaries in Brazilian Portuguese; output strictly in valid JSON.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from extract import extract_text
from llm import LLMRouter

logger = logging.getLogger(__name__)

ALLOWED_THEMES = [
    "national_politics",
    "international_politics",
    "technology",
    "ai",
    "gaming",
    "steamdeck",
    "game_dev",
    "custom_engines",
    "anime",
    "movies",
    "crypto",
    "science",
    "economy",
    "concursos",
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
    "concursos_es": "concursos",
    "outros": "others",
}

# ── Prompts ───────────────────────────────────────────────────────────────

THEME_GUIDE = """- national_politics: ONLY Brazilian politics — federal/state government, Congress, STF/TSE, elections, parties, public policy, politicians. NOT celebrities, TV, sports, weather, crime or foreign events.
- international_politics: geopolitics, wars, diplomacy, foreign governments and elections.
- technology: software, hardware, internet, gadgets, programming, tech companies.
- ai: artificial intelligence, machine learning, LLMs.
- gaming: video games from the player's side — releases, reviews, trailers, updates, consoles.
- steamdeck: Valve's Steam Deck and its ecosystem — Steam Deck hardware/OLED/successors, SteamOS updates, Proton/Linux gaming compatibility, Deck Verified ratings, games running on the Deck, handheld PC comparisons with the Steam Deck. Generic Steam client updates without Deck/SteamOS changes are NOT steamdeck (relevance 1-2).
- game_dev: game development and the game industry as a business — studio layoffs, closures, hiring, growth, funding, acquisitions, revenue, engines (Unity, Unreal, Godot), dev tools, postmortems, developer working conditions.
- custom_engines: building game/graphics engines from scratch — rendering and graphics programming, engine architecture, low-level performance, GPU APIs (Vulkan, DirectX, Metal), open-source engines like Bevy, Stride, Flax, O3DE. Unity/Unreal/Godot product news stays in game_dev.
- anime: anime, manga, Japanese animation and pop culture.
- movies: films, TV series and streaming — releases, trailers, reviews, box office, studios, festivals, awards. Anime goes to anime; telenovelas and celebrity gossip are not movies.
- crypto: cryptocurrencies, Bitcoin, Ethereum, blockchain, exchanges, stablecoins, crypto regulation and prices.
- science: research, space, health studies, environment science.
- economy: markets, inflation, interest rates, companies' finances, jobs, trade (crypto goes to crypto).
- concursos: public contests (concursos públicos) and simplified selection processes / temporary contracts (processos seletivos simplificados / contratações temporárias / DT) strictly located in the state of Espírito Santo (ES), Brazil. MUST be specifically for Information Technology (TI/TIC, software development, systems analysis, data, cloud, cybersecurity, network/infra, IT support/technician). Any contest outside Espírito Santo (ES) or for NON-IT roles (general administration, high school/nível médio without IT focus, education, pedagogy, teaching, healthcare, medicine, nursing, engineering other than computer/software, agronomy) or generic institutional announcements/tests (like language proficiency exams) must NOT be categorized here and must receive relevance 1.
- others: everything else (sports, weather, crime, lifestyle)."""

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
The reader does NOT want gossip: celebrity personal lives, relationships, influencers, reality shows (BBB, A Fazenda), telenovelas/soap operas and their actors, red carpets, "relembre" nostalgia pieces. Give any such article relevance 1 (it will be dropped), whatever its theme.
Target for 'concursos': The reader is an IT Master's graduate located in Espírito Santo (ES). Keep EXCLUSIVELY opportunities in Espírito Santo (ES) for Information Technology (TI/TIC: software developers, programmers, data analysts/engineers, IT infrastructure, network/database administration, IT support, systems analysis). Give relevance 1 (which DROPS the item entirely) to:
  - ANY contest/selection outside Espírito Santo (ES);
  - ANY contest without IT positions (e.g. general municipal education/pedagogy, general administration, general high school/nível médio, healthcare, civil/sanitary/environmental engineering, agriculture);
  - Generic academic/institutional notices (e.g. language proficiency exams, university calendars).
Rate legitimate IT contests/selection processes in ES (e.g., PRODEST, TJES TI, IFES TI, UFES TI, Banestes TI, city hall IT analyst/technician) with relevance 4 or 5.

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


DEDUP_PROMPT = """You are a news editor removing duplicates from a news digest.
Below is one line per article: id | theme | summary. Find articles that report the SAME specific story/event
(same facts, possibly from different outlets or in different languages). Related-but-different stories
(e.g. two different announcements by the same company) are NOT duplicates.
Return ONLY a JSON object: {{"groups": [["id1", "id2", ...], ...]}} listing only groups with 2+ ids. Return {{"groups": []}} if none.

{lines}
"""


# ── Processing Helpers ───────────────────────────────────────────────────

# Keywords that confirm an IT role in a 'concursos' item.
# Short keywords use regex word boundaries (\b) to avoid false matches inside
# longer Portuguese words (e.g. "seletivo" contains "ti", "tecnologia" has no "ti"
# but we still guard against surprises).
# Long unambiguous phrases use plain substring matching.
import re as _re

_IT_WORD_BOUNDARY_KWS = [
    r"\bti\b", r"\btic\b", r"\bt\.i\.\b", r"\bt\.i\.c\.\b",
    r"\binformática\b", r"\binformatica\b",
    r"\bsoftware\b", r"\bhardware\b",
    r"\bcloud\b",
    r"\bcibersegurança\b", r"\bcybersecurity\b",
    r"\bprodest\b",
]

_IT_PHRASE_KWS = [
    "tecnologia da informação", "tecnologia de informação",
    "ciência da computação", "ciencias da computacao", "ciência de computação",
    "sistemas de informação",
    "análise de sistemas", "analise de sistemas",
    "engenharia de software",
    "engenharia da computação", "engenharia de computação",
    "desenvolvedor", "programador", "programação", "programacao",
    "banco de dados", "database",
    "infraestrutura de ti", "redes de computadores", "redes de dados",
    "suporte técnico de ti", "suporte tecnico de ti", "suporte de ti",
    "segurança da informação", "segurança cibernética",
    "analista de sistemas",
    "técnico de ti", "técnico em ti",
    "técnico em informática", "tecnico em informatica",
    "banestes ti",
]

_IT_WB_PATTERN = _re.compile("|".join(_IT_WORD_BOUNDARY_KWS), _re.IGNORECASE)


def _is_it_concurso(item: dict) -> bool:
    """Return True only if a 'concursos' item is clearly IT-related.

    Acts as a deterministic safety net after LLM classification, preventing
    non-IT contests from passing through when the LLM ignores the drop rule.
    Uses word-boundary regex for short keywords and plain substring for phrases.
    """
    text = " ".join(filter(None, [
        item.get("title", ""),
        item.get("short_summary", ""),
        item.get("article_summary", ""),
        item.get("description", ""),
    ])).lower()
    if _IT_WB_PATTERN.search(text):
        return True
    return any(kw in text for kw in _IT_PHRASE_KWS)



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


def _drop_duplicates(items: list[dict], router: LLMRouter) -> list[dict]:
    """Collapses same-story items from different outlets/languages (URL/title dedup misses those).

    short_summary is always Portuguese, so comparing it catches EN/PT pairs too.
    """
    lines = "\n".join(f"{i['id']} | {i['theme']} | {i['short_summary']}" for i in items)
    data = router.generate_json(DEDUP_PROMPT.format(lines=lines))
    groups = data.get("groups") if isinstance(data, dict) else None
    if not isinstance(groups, list):
        logger.warning("Dedup skipped: no valid LLM answer")
        return items
    by_id = {i["id"]: i for i in items}
    drop: set[str] = set()
    for group in groups:
        members = [by_id[g] for g in group if isinstance(g, str) and g in by_id] if isinstance(group, list) else []
        # Keep the best-rated copy, preferring one with a full summary and reader comments
        members.sort(key=lambda i: (i["relevance"], "article_summary" in i, len(i.get("comments") or [])), reverse=True)
        for dup in members[1:]:
            logger.info("  → Duplicate dropped: %s (kept: %s)", dup["title"][:60], members[0]["title"][:60])
            drop.add(dup["id"])
    return [i for i in items if i["id"] not in drop]


def _cap_per_theme(items: list[dict], cap: int) -> list[dict]:
    """Keeps the `cap` best items of each theme: highest relevance first, newest breaks ties."""
    ranked = sorted(items, key=lambda i: (i["relevance"], i.get("published") or ""), reverse=True)
    per_theme: dict[str, int] = {}
    kept_ids: set[str] = set()
    for item in ranked:
        if per_theme.get(item["theme"], 0) < cap:
            per_theme[item["theme"]] = per_theme.get(item["theme"], 0) + 1
            kept_ids.add(item["id"])
    logger.info("Theme cap kept %d/%d items (max %d per theme)", len(kept_ids), len(items), cap)
    return [i for i in items if i["id"] in kept_ids]


def process_items(items: list[dict], cfg: dict, router: LLMRouter) -> list[dict]:
    """
    1. Extracts full text for every item
    2. Classifies + summarizes in batches (one LLM call per batch_size items)
    3. Summarizes comments for high-relevance items
    4. Drops items below min_relevance
    5. Drops same-story duplicates (one LLM call)
    6. Keeps at most max_items_per_theme per theme
    """
    col = cfg["collection"]
    batch_size: int = col["batch_size"]
    text_chars: int = col["batch_text_chars"]

    # Network-bound: fetching sites one by one took ~2.5 min per run
    logger.info("Extracting text for %d items", len(items))
    with ThreadPoolExecutor(max_workers=8) as pool:
        texts = list(pool.map(lambda item: extract_text(item, cfg), items))

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

    # Safety net: drop any 'concursos' item that contains no IT keywords,
    # in case the LLM ignored the relevance-1 drop instruction.
    for item in items:
        if item.get("theme") == "concursos" and not _is_it_concurso(item):
            logger.warning(
                "  → [concursos guard] Non-IT item force-dropped: %s", item["title"][:80]
            )
            item["relevance"] = 1

    kept = [i for i in items if i["relevance"] >= col["min_relevance"]]
    logger.info("Kept %d/%d items (min_relevance=%d)", len(kept), len(items), col["min_relevance"])
    kept = _drop_duplicates(kept, router)
    kept = _cap_per_theme(kept, col["max_items_per_theme"])
    router.print_summary()
    return kept
