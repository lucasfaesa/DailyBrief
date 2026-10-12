---
title: Frontend Architecture
type: architecture
updated_at: 2026-10-11
---

# Architecture — Frontend SPA (`docs/`)

## Stack

Pure HTML5, CSS3, and modern vanilla JavaScript. No bundling, transpilation, or frontend dependencies required.

## File Breakdown

- `docs/index.html`: Base application shell and viewport containers.
- `docs/app.js`: Hash routing, asynchronous data fetching, and DOM rendering.
- `docs/style.css`: Mobile-first styling with native CSS variables and dark mode support.
- `docs/data.json`: Current day's processed news payload.
- `docs/archive/`: Historical daily archives and `index.json` catalog.

## Hash Routing (`app.js`)

- `#/`: Home feed. Theme tabs live inside the sticky header (one sticky block, so they never slide under it) and wrap onto multiple rows (a horizontal scroll strip hid tabs on desktop). Tab "Destaques" shows one highlight per theme (its most relevant item; the most relevant overall is the large lead card) plus the top 4 per theme with a "ver todas" link; a theme tab lists all its items. Every theme always has a tab. While scrolling Destaques, the tab of the theme section under the header gets a `.spy` ring (`updateSpy()`, rAF-throttled scroll listener).
- Items are grouped client-side from `all_items` (`data.themes` is not read); legacy Portuguese theme keys are mapped via `THEME_COMPAT`.
- UI language is pt-BR; theme accent colors come from `THEMES` in `app.js` via the `--c` CSS variable.
- `#/item/<id>`: Detail view with "Resumo por IA" (`article_summary`) and community reactions.
- Opening a detail view marks the item as read in `localStorage` (`db-read`, last 1000 ids). Cards show read items muted with "✓ Lida"; the most recent one gets an accent bar and "Última aberta".
- Favorites: "☆ Favoritar" in the detail view stores a full copy of the item in `localStorage` (`db-favs`), since `data.json` is replaced every run. Tab "★ Favoritos" lists them newest first; the detail view resolves ids from the current data first, then from favorites.
- `#/archive`: Historical edition selector.

## Schema of `data.json`

```json
{
  "generated_at": "ISO-TIMESTAMP",
  "total_items": 42,
  "themes": { "technology": [ {...} ], "ai": [ {...} ] },
  "all_items": [
    {
      "id": "sha1(url)[:12]",
      "url": "https://...",
      "title": "...",
      "source": "...",
      "theme": "...",
      "short_summary": "...",
      "relevance": 4,
      "article_summary": "...",
      "comments_summary": "..."
    }
  ]
}
```

## Theming

- Default dark palette defined on `:root` CSS variables.
- Auto-switches to light scheme via `@media (prefers-color-scheme: light)`.
