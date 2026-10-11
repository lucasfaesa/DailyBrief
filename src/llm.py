"""
llm.py – Camada de abstração para chamadas a LLMs com fallback automático.

Provedores suportados (em ordem de preferência):
  1. Google Gemini (gemini-2.0-flash)
  2. Groq (llama-3.3-70b-versatile)

Comportamento:
  - Retry com backoff exponencial (max_retries_per_provider tentativas).
  - Circuit breaker: provedor marcado como esgotado após falhas consecutivas.
  - Se todos falharem: retorna None (pipeline lida com o fallback).
  - Loga qual provedor atendeu cada chamada.
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


# ── Estatísticas ──────────────────────────────────────────────────────────

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
        parts = [f"Total: {self.total_calls}", f"Falhas: {self.failures}"]
        for p, n in self.calls_by_provider.items():
            parts.append(f"{p}: {n}")
        return " | ".join(parts)


# ── Provedores ────────────────────────────────────────────────────────────

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
    Interface única para geração de texto com fallback entre provedores.
    Uso: router.generate(prompt) -> str | None
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
                logger.warning("Chave %s não encontrada; provedor '%s' desabilitado.", p_cfg["env_key"], name)
                continue
            if name == "gemini":
                providers.append(GeminiProvider(model, key))
            elif name == "groq":
                providers.append(GroqProvider(model, key))
        return providers

    def generate(self, prompt: str) -> str | None:
        """Chama LLM com fallback. Retorna texto ou None se tudo falhar."""
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
                    logger.debug("✓ [%s] atendeu (tentativa %d)", provider.name, attempt + 1)
                    return result
                except Exception as exc:
                    wait = backoff_base ** (attempt + 1)
                    if provider.is_retryable_error(exc):
                        logger.warning(
                            "⚠ [%s] erro retryable: %s – aguardando %.0fs",
                            provider.name, exc, wait,
                        )
                        time.sleep(wait)
                    else:
                        logger.warning("✗ [%s] erro não retryable: %s", provider.name, exc)
                        self._exhausted.add(provider.name)
                        break

            # Todas as tentativas falharam → circuit breaker
            logger.warning("⛔ [%s] esgotado para esta execução.", provider.name)
            self._exhausted.add(provider.name)

        self.stats.record_failure()
        logger.error("Todos os provedores falharam para este item.")
        return None

    def generate_json(self, prompt: str) -> dict | None:
        """
        Gera JSON válido. Retenta até json_fix_retries vezes se vier inválido.
        Retorna dict ou None.
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
            logger.warning("JSON inválido (tentativa %d/%d): %s…", attempt + 1, max_fix + 1, raw[:120])
        return None

    def print_summary(self) -> None:
        logger.info("=== Resumo LLM: %s ===", self.stats.summary())


# ── Helpers ───────────────────────────────────────────────────────────────

def _try_parse_json(text: str) -> dict | None:
    """Tenta extrair JSON de uma string, mesmo com lixo ao redor."""
    text = text.strip()
    # Remove blocos markdown ```json ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Tenta encontrar o primeiro objeto JSON na string
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None
