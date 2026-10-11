---
title: Progressive Web App Architecture
type: architecture
updated_at: 2026-10-11
---

# Architecture — PWA (`docs/sw.js`, `docs/manifest.json`)

## Web App Manifest (`manifest.json`)

Provides standalone mobile installation properties, theme colors, and icons (`192x192` and `512x512`).

## Service Worker (`sw.js`)

### Cache Versioning

```js
const CACHE_VERSION = 'dailybrief-v1';
```
Increment this identifier whenever updating core assets to bust client caches.

### Routing & Caching Strategies

| Resource Category | Strategy | Behavior |
|-------------------|----------|----------|
| Shell assets (HTML, CSS, JS, icons) | **Cache-first** | Instant offline loading, fetches in background |
| `data.json` & `archive/*.json` | **Network-first** | Prefers fresh network data, falls back to cached payload |

### Lifecycle

- **install**: Calls `self.skipWaiting()` and pre-caches the application shell.
- **activate**: Cleans up older cache versions and claims clients.
- **fetch**: Intercepts requests and applies corresponding strategy.

## Installation Experience

Listens for `beforeinstallprompt` to display the install action button in the header for Chromium browsers.
