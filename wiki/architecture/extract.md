---
title: Text Extraction Module
type: architecture
updated_at: 2026-10-11
---

# Architecture — Extraction (`src/extract.py`)

## Responsibility

Extract article body text (up to `max_chars`) from URLs, falling back cleanly when web scraping fails.

## Signature

```python
extract_text(item: dict, cfg: dict) -> str
```

## Logic

```
Item URL
    │
    ├─ Is host in skip_domains?
    │     {"reddit.com", "news.ycombinator.com", "redd.it"}
    │     └─ Yes → Jump directly to title + description fallback
    │
    ├─ HTTP GET with timeout extraction.timeout_seconds
    │     User-Agent: "Mozilla/5.0 (compatible; DailyBrief/1.0)"
    │
    ├─ trafilatura.extract(html,
    │       include_comments=False,
    │       include_tables=False,
    │       no_fallback=False)
    │
    ├─ Body found? → Return text[:max_chars]
    │
    └─ Fallback: "{title}\n\n{description}"[:max_chars]
```

## Configuration

```yaml
extraction:
  max_chars: 6000
  timeout_seconds: 15
```

## Context Boundaries

Prompts enforce tighter length limits on extracted text:
- Classification prompt: `text[:4000]`
- Detailed summary prompt: `text[:5000]`

## Video Sniffing

Alongside the body-text GET (same request, non-skip-domain items only), `_find_og_video()` reads the page's `og:video`/`og:video:url`/`og:video:secure_url` meta tag and `_classify_video()` turns it into `item["video"]`:
- Direct `.mp4`/`.webm`/`.mov` URL → `{"type": "video", "url": ...}`.
- YouTube/Vimeo URL → converted to an embed URL, `{"type": "iframe", "url": ...}`.
- Any other `og:video` URL → embedded as-is (`iframe`); a site that blocks cross-origin framing just renders blank.
- No `og:video` tag → `video: null`.

Deliberately uses only `og:video` (the page's own declared video for the content), not a scrape of every `<video>`/`<iframe>` on the page — that would also catch unrelated sidebar/ad players. Reddit items skip this path entirely (reddit.com is a skip-domain) and keep the `video` field `_reddit_video()` set in [[architecture/collect]].
