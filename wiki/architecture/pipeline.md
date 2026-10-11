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

1. Extracts body text using `extract_text()`.
2. Invokes `CLASSIFY_PROMPT`:
   - Returns JSON: `{"theme": "...", "short_summary": "...", "relevance": 1-5}`.
   - Validated via `_validate_classification()`.
   - On parse failure, falls back to `category_hint` or `others`, title snippet, and relevance 1.
3. If `relevance >= threshold` (default: 4) up to `max_high_relevance` (default: 30):
   - Generates full summary (`resumo_materia` / `article_summary`) via `SUMMARY_PROMPT`.
   - If comments exist, generates discussion overview (`resumo_comentarios` / `comments_summary`) via `COMMENTS_PROMPT`.

## Prompt Schemas

- **Classification**: Factual, single-sentence summary (<= 120 chars), relevance scale 1–5.
- **Article Summary**: 4–6 factual sentences detailing core story developments.
- **Comments Summary**: 2–4 sentences characterizing community consensus and debate, explicitly framed as user opinions.

## Supported Themes (`ALLOWED_THEMES`)

`national_politics`, `international_politics`, `technology`, `ai`, `gaming`, `anime`, `science`, `economy`, `others`

See related docs: [[architecture/llm]] and [[architecture/extract]].
