---
title: "Decision: GitHub Pages via /docs Directory"
type: decision
updated_at: 2026-10-11
---

# Decision — GitHub Pages Hosting

## Context

Static frontend assets and daily generated JSON feeds need reliable, zero-maintenance public hosting with automatic deployment.

## Decision

Serve the web client via **GitHub Pages** targeting the `/docs` folder on the `main` branch.

## Justifications

- **Zero Hosting Fees**: Bundled with GitHub repositories at no additional charge.
- **Git Push Deployment**: The Action commits modified files in `docs/`, automatically triggering page deployment within minutes.
- **Simplicity**: Avoids maintaining dedicated deployment branches (`gh-pages`) or third-party hosting accounts (e.g., Vercel, Netlify).

## Relevant Files

- `docs/`
- `.github/workflows/daily.yml`
