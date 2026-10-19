---
title: GitHub Actions Workflow Architecture
type: architecture
updated_at: 2026-10-11
---

# Architecture — Workflow (`.github/workflows/daily.yml`)

## Triggers

- **Scheduled (external)**: cron-job.org job `7 7,21 * * *` (timezone America/Sao_Paulo) sends
  `POST https://api.github.com/repos/lucasfaesa/DailyBrief/actions/workflows/daily.yml/dispatches`
  with body `{"ref":"master"}` and a fine-grained PAT (Actions: read/write, this repo only) as `Authorization: Bearer`. Success = HTTP 204.
  GitHub's native `schedule:` was dropped: it ran 3-7h late, pushing the night edition past midnight so the next morning's run overwrote its archive file.
  When the PAT expires the runs silently stop — renew it in cron-job.org.
- **Manual**: `workflow_dispatch` trigger via GitHub UI.

## Permissions

Requires write permissions to repository contents for automated commits:
```yaml
permissions:
  contents: write
```

## Concurrency

`concurrency: daily-digest` (no cancel) queues a dispatch behind a running one, so the two never race on `git push`.

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
