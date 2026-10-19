---
title: Pipeline & Prompt Architecture
type: architecture
updated_at: 2026-10-11
---

# Architecture — Pipeline (`src/pipeline.py`)

## Responsibility

Extract article content, classify items via LLM prompts, assign relevance scores (1–5), and generate structured summaries and comment sentiment breakdowns for top items.

## Entry Point

```python
process_items(items: list[dict], cfg: dict, router: LLMRouter) -> list[dict]
```

Enriches items in-place and returns the list.

## Processing Steps

1. Extracts body text for every item using `extract_text()`, 8 sites in parallel (`ThreadPoolExecutor`).
2. Sends items in batches of `batch_size` (default 10, `batch_text_chars` of text each) to `BATCH_PROMPT`:
   - Returns JSON: `{"items": [{"id", "theme", "relevance", "short_summary", "summary"}]}`; results are matched back by `id`.
   - `THEME_GUIDE` defines each theme strictly (e.g. `national_politics` = Brazilian politics only; celebrities/sports/weather go to `others`).
   - `summary` is stored as `article_summary` for every classified item.
   - Missing/invalid result → fallback to `category_hint`, title snippet, relevance 2.
3. Up to `max_high_relevance` items with `relevance >= relevance_threshold` and comments get `comments_summary` via `COMMENTS_PROMPT`.
4. Items with `relevance < min_relevance` (default 2: trivial/clickbait) are dropped. The prompt forces relevance 1 for gossip (celebrity lives, reality shows, telenovelas) and for non-IT contests/processes outside or inside ES, so those are dropped too.
5. **Same-story dedup** (`_drop_duplicates`, runs last, after the concursos guard and relevance drop): one `DEDUP_PROMPT` call with `id | theme | short_summary` of every kept item returns groups of ids covering the same story (different outlets or EN/PT pairs; `short_summary` is always Portuguese so languages line up). Per group the item with the highest relevance (then full summary, then comments) is kept. Invalid/failed LLM answer → dedup skipped. URL/exact-title dedup still happens earlier in `collect.deduplicate()`.
6. **Deterministic `concursos` guard** (`_is_it_concurso`): after LLM classification, any item in the `concursos` theme that contains no IT-related keywords (word-boundary regex for short tokens like `\bti\b`, `\binformática\b`, `\bsoftware\b`; substring match for longer phrases like "tecnologia da informação", "analista de sistemas") has its relevance forced to 1 and is dropped. This is a hard safety net in case the LLM ignores the non-IT drop instruction.

## Prompt Schemas

- Prompts are in English; all summaries are written in Brazilian Portuguese.
- **Batch**: theme, relevance 1–5, one-sentence summary (<= 140 chars), 3–5 sentence summary.
- **Comments Summary**: 2–4 sentences characterizing community consensus and debate, explicitly framed as user opinions.

Batching keeps a run at roughly `items / batch_size` + `max_high_relevance` LLM calls, within free-tier quotas.

Self-check: `python src/test_pipeline.py`.

## Supported Themes (`ALLOWED_THEMES`)

`national_politics`, `international_politics`, `technology`, `ai`, `concursos`, `gaming`, `game_dev`, `custom_engines`, `anime`, `movies`, `crypto`, `science`, `economy`, `others`

- `concursos`: public contests (concursos públicos) and selective processes (PSS/DT) located in Espírito Santo (ES), filtered strictly for IT (TI/TIC) or general high school level (nível médio). Out-of-state contests and non-IT specific degree contests receive relevance 1 (dropped).
- `gaming` is the player's side (releases, reviews); `game_dev` is development and the industry as a business (layoffs, closures, funding, engines).

See related docs: [[architecture/llm]] and [[architecture/extract]].
