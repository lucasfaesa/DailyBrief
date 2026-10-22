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

- `#/`: Home feed. Theme tabs live inside the sticky header (one sticky block, so they never slide under it) and wrap onto multiple rows on desktop (a horizontal strip hid tabs there); at ≤640px they form one swipeable row with a right-edge fade, and `revealTab()` scrolls the active/spied tab into view. "★ Favoritos" is the last tab. Tab "Destaques" shows the top 5 highlights overall across all categories (at most 1 item per theme; the most relevant overall is the large lead card) plus the top 4 per theme with a "ver todas" link; a theme tab lists all its items. Every theme always has a tab. While scrolling Destaques, the tab of the theme section under the header gets a `.spy` ring (`updateSpy()`, rAF-throttled scroll listener).
- Items are grouped client-side from `all_items` (`data.themes` is not read); legacy Portuguese theme keys are mapped via `THEME_COMPAT`.
- UI chrome (headers, labels, buttons, dates) is English; AI summaries and article content stay in Brazilian Portuguese (generated that way by `pipeline.py`). Theme accent colors come from `THEMES` in `app.js` via the `--c` CSS variable. Tab order follows the `THEMES` object order, with `national_politics`/`international_politics` placed last (before "★ Favorites").
- `#/item/<id>`: Detail view with an inline video (`item.video`, see below), "AI Summary" (`article_summary`), and community reactions.
- `videoBlock()`: renders `item.video` (`{"type": "video"|"iframe", "url": ...}`, set by `extract.py`/`collect.py`) as a native `<video controls>` or a sandboxed `<iframe>`, styled `.detail-video` (16:9, `var(--radius)`). `null` → nothing rendered.
- Opening a detail view marks the item as read in `localStorage` (`db-read`, last 1000 ids). Cards show read items muted with "✓ Read"; the most recent one gets an accent bar and "Last opened".
- Favorites: "☆ Favorite" in the detail view stores a full copy of the item in `localStorage` (`db-favs`), since `data.json` is replaced every run. Tab "★ Favorites" lists them newest first; the detail view resolves ids from the current data first, then from favorites.
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
      "comments_summary": "...",
      "video": { "type": "video|iframe", "url": "..." } | null
    }
  ]
}
```

## Theming

- Default dark palette defined on `:root` CSS variables.
- Auto-switches to light scheme via `@media (prefers-color-scheme: light)`.
