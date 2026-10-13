---
title: Change Log
type: log
updated_at: 2026-10-11
---

# Log — DailyBrief

Chronological, append-only log. Never delete historical entries.
Format: `## [YYYY-MM-DD] type | description`

---

## [2026-10-11] feat | initial project setup

Complete pipeline created: automated collection (HN + Reddit + RSS), extraction (trafilatura), resilient LLM layer with circuit breaker fallback (Gemini → Groq), mobile PWA site (vanilla HTML/CSS/JS), GitHub Actions workflow with dual daily cron.

## [2026-10-11] config | added second daily run

Workflow updated to run twice daily: 07:00 and 20:00 America/Sao_Paulo (10:00 and 23:00 UTC) via `.github/workflows/daily.yml`.

## [2026-10-11] chore | purged README.md from git history

Removed README.md and rewritten git tree using `git filter-repo --path README.md --invert-paths`.

## [2026-10-11] docs | project wiki created

Generated 18 wiki documentation pages: index, log, overview, gotchas, conventions, 7 architecture modules, 4 architectural decisions, AGENTS.md, and CLAUDE.md.

## [2026-10-11] refactor | converted codebase and documentation to English

Translated all documentation, wiki pages, code docstrings/comments, pipeline prompts, and frontend text to English.

## [2026-10-11] fix | LLM providers switched to plain REST (gemini-flash-latest, Groq OpenAI endpoint); retired gemini-2.0-flash and groq-SDK/httpx crash made every item fall back
## [2026-10-11] feat | batched classify+summarize in pt-BR, strict theme guide, min_relevance filter, politics-only BR feeds, anime/gaming/economy feeds, per-subreddit hints
## [2026-10-11] feat | frontend redesign: tabs inside sticky header, Destaques view, per-theme colors, pt-BR UI, AI summary in detail view; SW cache v2
## [2026-10-11] fix | 503 no longer disables a provider for the whole run; backoff capped at 60s; added gemini-flash-lite fallback; Groq model → openai/gpt-oss-120b (llama-3.3-70b removed); dedupe by title too
## [2026-10-11] fix | theme tabs wrap instead of horizontal scroll (Animes/Geral were hidden on desktop); SW cache v3
## [2026-10-11] feat | new "DB" serif monogram app icon; source docs/icons/icon.svg (PNGs rendered with headless Chrome); removed src/generate_icons.py; SW cache v4
## [2026-10-11] feat | Destaques: one highlight card per theme instead of global top-5
## [2026-10-11] feat | new game_dev theme (industry: layoffs, growth, studios, engines) with Game Developer, GamesIndustry.biz, 80.lv, PocketGamer.biz, Game World Observer, Unity/Unreal/Godot feeds and r/gamedev; AI feeds (Simon Willison, The Decoder, Latent Space, Hugging Face, OpenAI, Google AI, Import AI, r/LocalLLaMA, r/MachineLearning); Guardian, Al Jazeera, Lobsters; CNBC → Folha Mercado; dropped r/programming, r/brdev; SW cache v6
## [2026-10-11] perf | flash-lite first (Flash: 30s-3min per batch, quota gone after 5 calls), LLM HTTP timeout 120→60s, parallel text extraction (8 workers)
## [2026-10-11] feat | favicon (favicon.svg + 32px PNG fallback); SW cache v7
## [2026-10-12] feat | new themes custom_engines (graphics/engine blogs, 7-day window, r/gameenginedevs, r/GraphicsProgramming), movies (Variety, Deadline, IndieWire, /Film, Pipoca Moderna, r/movies), crypto (CoinDesk, Cointelegraph, Decrypt, The Block, Livecoins, Portal do Bitcoin, r/CryptoCurrency); per-feed lookback_hours; RSS date falls back to <updated>; SW cache v8
## [2026-10-12] feat | read tracking: opened items muted with "✓ Lida", last opened highlighted (localStorage db-read); SW cache v9
## [2026-10-12] feat | per-device favorites (localStorage db-favs, full item copies so they survive new runs) with ★ Favoritos tab; SW cache v10
## [2026-10-12] feat | scroll spy: on Destaques the tab of the section in view is highlighted; SW cache v11
## [2026-10-12] feat | gossip filter: prompt forces relevance 1 (dropped) for celebrity gossip, reality shows and telenovelas
## [2026-10-12] fix | workflow: pull --rebase before push (concurrent pushes lost editions), concurrency group, São Paulo date in commit message, checkout@v5/setup-python@v6; docs: fixed cron times in workflow.md
## [2026-10-12] feat | mobile tabs: single swipeable row (header 5 rows → 1), auto-scroll to active/spied tab; Favoritos moved to last tab; SW cache v12
## [2026-10-12] feat | new concursos theme for ES (IT and high school level) with Folha Vitória, Concursos no Brasil, TJES, IFES and UFES feeds; SW cache v13
