---
title: Conventions and Local Setup
type: conventions
updated_at: 2026-10-11
---

# Conventions — DailyBrief

## Code Patterns

- **Explicit Config Propagation**: `cfg: dict` (parsed from `config.yaml`) is passed explicitly down the stack starting from `main.py`.
- **Stable IDs**: `id = hashlib.sha1(url.encode()).hexdigest()[:12]`, used for client hash routing `#/item/<id>`.
- **Output Sanitization**: Raw `comments` arrays are stripped from `docs/data.json` to keep payload sizes lean.
- **Allowed Themes**: Hardcoded list in `src/pipeline.py` (`ALLOWED_THEMES`). Unrecognized themes fallback to `others`.

## Running Locally

```bash
cd news-digest/

# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API keys (at least one is required)
export GEMINI_API_KEY="your-gemini-key"
export GROQ_API_KEY="your-groq-key"

# 3. Execute pipeline
python src/main.py

# 4. Preview frontend locally
python -m http.server 8000 --directory docs/
```

## How to Extend

- **Add an RSS feed**: Add an entry under `rss_feeds` in `config.yaml` (`name`, `url`, and `category_hint`).
- **Add a new LLM provider**:
  1. Subclass provider interface in `src/llm.py` with `generate(prompt)` and `is_retryable_error(exc)`.
  2. Instantiate in `_build_providers()` inside `LLMRouter`.
  3. Declare in `config.yaml` under `llm.providers`.
  4. Document in [[decisions/llm-providers]] and log in [[log]].
