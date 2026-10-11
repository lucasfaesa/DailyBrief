"""
pipeline.py – Orquestra extração de texto, classificação e resumo via LLM.

Prompts em português do Brasil, resposta apenas em JSON válido.
"""
from __future__ import annotations

import logging
from typing import Any

from extract import extract_text
from llm import LLMRouter

logger = logging.getLogger(__name__)

ALLOWED_THEMES = [
    "politica_nacional",
    "politica_internacional",
    "tecnologia",
    "ia",
    "games",
    "animes",
    "ciencia",
    "economia",
    "outros",
]

# ── Prompts ───────────────────────────────────────────────────────────────

CLASSIFY_PROMPT = """Você é um classificador de notícias factual e imparcial.
Analise o texto abaixo e retorne SOMENTE um JSON (sem markdown, sem explicações).

Campos obrigatórios:
- "tema": um dos seguintes valores EXATOS: {themes}
- "resumo_curto": resumo objetivo em uma frase (máx 120 caracteres) em português do Brasil
- "relevancia": número inteiro de 1 a 5 (5 = muito relevante para o público geral)

Regras:
- Seja factual. Não invente informações que não estão no texto.
- Não inclua opiniões próprias.
- Responda APENAS com o JSON, sem nenhum texto antes ou depois.

Título: {title}

Texto:
{text}
"""

SUMMARY_PROMPT = """Você é um redator de notícias factual e imparcial.
Leia o texto abaixo e retorne SOMENTE um JSON (sem markdown, sem explicações).

Campos obrigatórios:
- "resumo_materia": 4 a 6 frases em português do Brasil descrevendo os principais fatos da matéria.
  Seja factual. Não invente informações que não estão no texto. Não inclua opiniões.

Título: {title}

Texto:
{text}
"""

COMMENTS_PROMPT = """Você é um analista imparcial de discussões online.
Analise os comentários abaixo (opiniões de usuários, não fatos verificados) e retorne SOMENTE um JSON.

Campos obrigatórios:
- "resumo_comentarios": 2 a 4 frases em português do Brasil resumindo os principais pontos de vista,
  concordâncias e discordâncias presentes nos comentários.
  Deixe claro que são opiniões de usuários. Não invente nada que não esteja nos comentários.

Comentários:
{comments}
"""


# ── Funções de processamento ──────────────────────────────────────────────

def _build_classify_prompt(item: dict, text: str) -> str:
    themes_str = ", ".join(ALLOWED_THEMES)
    return CLASSIFY_PROMPT.format(
        themes=themes_str,
        title=item["title"],
        text=text[:4000],
    )


def _build_summary_prompt(item: dict, text: str) -> str:
    return SUMMARY_PROMPT.format(
        title=item["title"],
        text=text[:5000],
    )


def _build_comments_prompt(comments: list[str]) -> str:
    joined = "\n\n---\n\n".join(comments[:30])
    return COMMENTS_PROMPT.format(comments=joined[:4000])


def _validate_classification(data: dict) -> bool:
    return (
        isinstance(data, dict)
        and data.get("tema") in ALLOWED_THEMES
        and isinstance(data.get("resumo_curto"), str)
        and isinstance(data.get("relevancia"), int)
        and 1 <= data["relevancia"] <= 5
    )


def process_items(items: list[dict], cfg: dict, router: LLMRouter) -> list[dict]:
    """
    Para cada item:
      1. Extrai texto
      2. Classifica via LLM (tema, resumo_curto, relevância)
      3. Se relevância >= threshold: gera resumo_materia e resumo_comentarios
    """
    threshold: int = cfg["collection"]["relevance_threshold"]
    max_high: int = cfg["collection"]["max_high_relevance"]
    high_relevance_count = 0

    for idx, item in enumerate(items):
        logger.info("[%d/%d] Processando: %s", idx + 1, len(items), item["title"][:80])

        # 1. Extrai texto
        text = extract_text(item, cfg)

        # 2. Classifica
        classify_data = router.generate_json(_build_classify_prompt(item, text))

        if classify_data and _validate_classification(classify_data):
            item["tema"] = classify_data["tema"]
            item["resumo_curto"] = classify_data["resumo_curto"]
            item["relevancia"] = classify_data["relevancia"]
        else:
            # Fallback: classificação mínima
            logger.warning("  → Fallback de classificação para: %s", item["title"][:60])
            item["tema"] = item.get("category_hint", "outros")
            if item["tema"] not in ALLOWED_THEMES:
                item["tema"] = "outros"
            item["resumo_curto"] = item["title"][:120]
            item["relevancia"] = 1

        logger.info(
            "  → tema=%s | relevância=%d", item["tema"], item["relevancia"]
        )

        # 3. Resumo completo apenas para itens relevantes
        if item["relevancia"] >= threshold and high_relevance_count < max_high:
            high_relevance_count += 1

            # Resumo da matéria
            summary_data = router.generate_json(_build_summary_prompt(item, text))
            if summary_data and isinstance(summary_data.get("resumo_materia"), str):
                item["resumo_materia"] = summary_data["resumo_materia"]

            # Resumo dos comentários (opcional)
            comments = item.get("comments", [])
            if comments:
                comments_data = router.generate_json(_build_comments_prompt(comments))
                if comments_data and isinstance(comments_data.get("resumo_comentarios"), str):
                    item["resumo_comentarios"] = comments_data["resumo_comentarios"]

    router.print_summary()
    return items
