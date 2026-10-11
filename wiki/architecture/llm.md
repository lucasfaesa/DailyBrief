---
title: LLM & Fallback Layer Architecture
type: architecture
updated_at: 2026-10-11
---

# Architecture — LLM Layer (`src/llm.py`)

## Responsibility

Unified interface providing automated fallback between providers, circuit breaker state management, exponential backoff retries, and resilient JSON parsing.

## Core Components

- **`LLMRouter`**: Main entrypoint exposing `generate(prompt)` and `generate_json(prompt)`.
- **Providers (`GeminiProvider`, `GroqProvider`)**: Plain REST calls via `requests` (no vendor SDKs) requesting JSON output. Gemini uses the `gemini-flash-latest` alias; Groq uses the OpenAI-compatible endpoint. Non-200 responses raise `ProviderError` with the response body, so the CI log shows the real cause.
- **`LLMStats`**: Tracks calls per provider, failed attempts, and JSON re-evaluations.

## Circuit Breaker and Execution Flow

1. Evaluates providers in the sequence defined in `config.yaml`.
2. Skips any provider marked in the `_exhausted` set.
3. Attempts calls up to `max_retries_per_provider` with `rate_limit_pause_seconds` delay:
   - **Success**: Records metrics and returns string response.
   - **Retryable error (HTTP 429/5xx, timeout, connection, malformed response)**: Waits `min(backoff_base ** attempt, 60)` seconds before the next attempt (no wait after the last).
   - **Fatal error (e.g. 404 model not found, invalid key)**: Marks provider as `_exhausted` and skips to next provider.
4. If retries run out: a final 429 (quota gone) marks the provider `_exhausted`; a 5xx ("high demand") only skips it for this request.
5. Gemini providers are named `gemini/<model>`, so `gemini-flash-latest` and `gemini-flash-lite-latest` (separate capacity pools) can be chained before Groq.
6. If all providers fail, returns `None` to let the pipeline handle fallback.

## Robust JSON Extraction (`generate_json`)

1. Retries up to `json_fix_retries + 1` times.
2. In `_try_parse_json(text)`:
   - Strips Markdown code fences (` ```json `).
   - Attempts `json.loads(text)`.
   - On parse error, searches for JSON object blocks via regex (`\{.*\}`).
3. Returns `None` if unparseable, triggering pipeline fallback.

See decision record: [[decisions/llm-providers]].
