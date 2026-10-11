"""
llm.py – Abstraction layer for LLM requests with automated provider fallback.

Supported providers (in precedence order):
  1. Google Gemini (gemini-2.0-flash)
  2. Groq (llama-3.3-70b-versatile)

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
from dataclasses import dataclass, field
from typing import Any

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

class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    def generate(self, prompt: str) -> str:
        client = self._get_client()
        response = client.generate_content(prompt)
        return response.text

    def is_retryable_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(k in msg for k in ("429", "quota", "rate", "500", "503", "unavailable"))


class GroqProvider:
    name = "groq"

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def generate(self, prompt: str) -> str:
        client = self._get_client()
        completion = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return completion.choices[0].message.content

    def is_retryable_error(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(k in msg for k in ("429", "quota", "rate", "500", "503", "unavailable"))


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

            for attempt in range(max_retries):
                try:
                    time.sleep(rate_pause)
                    result = provider.generate(prompt)
                    self.stats.record(provider.name)
                    logger.debug("✓ [%s] resolved request (attempt %d)", provider.name, attempt + 1)
                    return result
                except Exception as exc:
                    wait = backoff_base ** (attempt + 1)
                    if provider.is_retryable_error(exc):
                        logger.warning(
                            "⚠ [%s] retryable error: %s – waiting %.0fs",
                            provider.name, exc, wait,
                        )
                        time.sleep(wait)
                    else:
                        logger.warning("✗ [%s] fatal/non-retryable error: %s", provider.name, exc)
                        self._exhausted.add(provider.name)
                        break

            # Mark provider as exhausted for the remainder of this run
            logger.warning("⛔ [%s] exhausted for this execution session.", provider.name)
            self._exhausted.add(provider.name)

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
