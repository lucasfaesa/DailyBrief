"""
llm.py – Abstraction layer for LLM requests with automated provider fallback.

Supported providers (in precedence order):
  1. Google Gemini (REST generateContent)
  2. Groq (OpenAI-compatible REST)

Behavior:
  - Retry with exponential backoff (max_retries_per_provider attempts).
  - Circuit breaker: provider marked exhausted after repeated consecutive errors.
  - If all fail: returns None (pipeline triggers graceful fallback).
  - Logs provider handling each request and prints summary metrics.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

import requests
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Statistics ────────────────────────────────────────────────────────────

@dataclass
class LLMStats:
    total_calls: int = 0
    calls_by_provider: dict[str, int] = field(default_factory=dict)
    failures: int = 0
    json_retries: int = 0

    def record(self, provider: str) -> None:
        self.total_calls += 1
        self.calls_by_provider[provider] = self.calls_by_provider.get(provider, 0) + 1

    def record_failure(self) -> None:
        self.failures += 1

    def summary(self) -> str:
        parts = [f"Total: {self.total_calls}", f"Failures: {self.failures}"]
        for p, n in self.calls_by_provider.items():
            parts.append(f"{p}: {n}")
        return " | ".join(parts)


# ── Providers ─────────────────────────────────────────────────────────────
# ponytail: plain REST via requests; the vendor SDKs broke us twice (retired model, httpx incompatibility).

class ProviderError(Exception):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status


def _post(url: str, headers: dict, payload: dict) -> dict:
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise ProviderError(resp.status_code, resp.text)
    return resp.json()


class GeminiProvider:
    def __init__(self, model: str, api_key: str) -> None:
        self.name = f"gemini/{model}"  # several Gemini models can be chained; each has its own capacity pool
        self.model = model
        self.api_key = api_key

    def generate(self, prompt: str) -> str:
        data = _post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {"x-goog-api-key": self.api_key},
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
            },
        )
        return data["candidates"][0]["content"]["parts"][0]["text"]


class GroqProvider:
    name = "groq"

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key

    def generate(self, prompt: str) -> str:
        data = _post(
            "https://api.groq.com/openai/v1/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )
        return data["choices"][0]["message"]["content"]


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ProviderError):
        return exc.status == 429 or exc.status >= 500
    return isinstance(exc, (requests.Timeout, requests.ConnectionError, KeyError, IndexError))


# ── LLMRouter ─────────────────────────────────────────────────────────────

class LLMRouter:
    """
    Unified interface for text generation with multi-provider fallback.
    Usage: router.generate(prompt) -> str | None
    """

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg["llm"]
        self.stats = LLMStats()
        self._exhausted: set[str] = set()
        self._providers = self._build_providers()

    def _build_providers(self) -> list:
        providers = []
        for p_cfg in self.cfg["providers"]:
            name = p_cfg["name"]
            model = p_cfg["model"]
            key = os.environ.get(p_cfg["env_key"], "")
            if not key:
                logger.warning("Secret %s not found; provider '%s' disabled.", p_cfg["env_key"], name)
                continue
            if name == "gemini":
                providers.append(GeminiProvider(model, key))
            elif name == "groq":
                providers.append(GroqProvider(model, key))
        return providers

    def generate(self, prompt: str) -> str | None:
        """Invokes LLM with automated fallback. Returns text or None if all fail."""
        rate_pause = self.cfg["rate_limit_pause_seconds"]
        max_retries = self.cfg["max_retries_per_provider"]
        backoff_base = self.cfg["backoff_base_seconds"]

        for provider in self._providers:
            if provider.name in self._exhausted:
                continue

            last_exc: Exception | None = None
            for attempt in range(max_retries):
                if attempt:
                    wait = min(backoff_base ** attempt, 60)
                    logger.warning("⚠ [%s] retryable error: %s – waiting %.0fs", provider.name, last_exc, wait)
                    time.sleep(wait)
                try:
                    time.sleep(rate_pause)
                    result = provider.generate(prompt)
                    self.stats.record(provider.name)
                    logger.debug("✓ [%s] resolved request (attempt %d)", provider.name, attempt + 1)
                    return result
                except Exception as exc:
                    last_exc = exc
                    if not _is_retryable(exc):
                        logger.warning("✗ [%s] fatal/non-retryable error: %s", provider.name, exc)
                        self._exhausted.add(provider.name)
                        break
            else:
                # 503 "high demand" is transient: skip this provider for this request only.
                # A persistent 429 means quota is gone: stop wasting backoff on it for the rest of the run.
                if isinstance(last_exc, ProviderError) and last_exc.status == 429:
                    logger.warning("⛔ [%s] quota exhausted for this execution session.", provider.name)
                    self._exhausted.add(provider.name)
                else:
                    logger.warning("↷ [%s] gave up on this request: %s", provider.name, last_exc)

        self.stats.record_failure()
        logger.error("All LLM providers failed for this request.")
        return None

    def generate_json(self, prompt: str) -> dict | None:
        """
        Generates valid JSON. Retries up to json_fix_retries times on parse error.
        Returns dict or None.
        """
        max_fix = self.cfg["json_fix_retries"]
        for attempt in range(max_fix + 1):
            raw = self.generate(prompt)
            if raw is None:
                return None
            parsed = _try_parse_json(raw)
            if parsed is not None:
                return parsed
            self.stats.json_retries += 1
            logger.warning("Invalid JSON response (attempt %d/%d): %s…", attempt + 1, max_fix + 1, raw[:120])
        return None

    def print_summary(self) -> None:
        logger.info("=== LLM Summary: %s ===", self.stats.summary())


# ── Helpers ───────────────────────────────────────────────────────────────

def _try_parse_json(text: str) -> dict | None:
    """Attempts extracting and parsing JSON from LLM response text."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None
