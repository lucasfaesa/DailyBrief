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

- `#/`: Home feed with topic filter tabs and collapsible sections.
- `#/item/<id>`: Detailed view displaying article overview and community reactions.
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
