---
title: GitHub Actions Workflow Architecture
type: architecture
updated_at: 2026-10-11
---

# Architecture — Workflow (`.github/workflows/daily.yml`)

## Triggers

- **Scheduled (Cron)**:
  - `7 10 * * *` (07:07 America/Sao_Paulo / 10:07 UTC)
  - `7 0 * * *` (21:07 America/Sao_Paulo / 00:07 UTC next day)
- **Manual**: `workflow_dispatch` trigger via GitHub UI.

## Permissions

Requires write permissions to repository contents for automated commits:
```yaml
permissions:
  contents: write
```

## Concurrency

`concurrency: daily-digest` (no cancel) queues a manual dispatch behind a running scheduled run, so the two never race on `git push`.

## Execution Steps

1. **Checkout**: Shallow clone (`fetch-depth: 1`) for fast execution.
2. **Setup Python 3.11** (`actions/setup-python@v6`; checkout is `@v5`, both Node 24): Enables dependency caching via pip.
3. **Install Requirements**: Installs dependencies specified in `requirements.txt`.
4. **Run Pipeline**: Executes `python src/main.py` with secret environment variables.
5. **Conditional Commit & Push**:
   ```bash
   git config user.name "github-actions[bot]"
   git config user.email "github-actions[bot]@users.noreply.github.com"
   git add docs/
   git diff --cached --quiet || git commit -m "chore: daily digest $(TZ=America/Sao_Paulo date +'%Y-%m-%d')"
   git pull --rebase   # commits pushed during the run would otherwise reject the push
   git push
   ```

## Resiliency

If network outages prevent story collection, `src/main.py` outputs an empty `data.json` rather than failing, preserving site availability without corrupting history.
