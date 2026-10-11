---
title: GitHub Actions Workflow Architecture
type: architecture
updated_at: 2026-10-11
---

# Architecture — Workflow (`.github/workflows/daily.yml`)

## Triggers

- **Scheduled (Cron)**:
  - `0 10 * * *` (07:00 America/Sao_Paulo / 10:00 UTC)
  - `0 23 * * *` (20:00 America/Sao_Paulo / 23:00 UTC)
- **Manual**: `workflow_dispatch` trigger via GitHub UI.

## Permissions

Requires write permissions to repository contents for automated commits:
```yaml
permissions:
  contents: write
```

## Execution Steps

1. **Checkout**: Shallow clone (`fetch-depth: 1`) for fast execution.
2. **Setup Python 3.11**: Enables dependency caching via pip.
3. **Install Requirements**: Installs dependencies specified in `requirements.txt`.
4. **Run Pipeline**: Executes `python src/main.py` with secret environment variables.
5. **Conditional Commit & Push**:
   ```bash
   git config user.name "github-actions[bot]"
   git config user.email "github-actions[bot]@users.noreply.github.com"
   git add docs/
   git diff --cached --quiet || git commit -m "chore: daily digest $(date -u +'%Y-%m-%d')"
   git push
   ```

## Resiliency

If network outages prevent story collection, `src/main.py` outputs an empty `data.json` rather than failing, preserving site availability without corrupting history.
