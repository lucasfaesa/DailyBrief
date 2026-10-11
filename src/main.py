"""
main.py – Ponto de entrada do pipeline DailyBrief.

Fluxo:
  1. Carregar config.yaml
  2. Coletar notícias (HN + Reddit + RSS)
  3. Processar via LLM (classificar + resumir)
  4. Salvar docs/data.json e docs/archive/YYYY-MM-DD.json
  5. Commit automático pelo GitHub Actions
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

# Garante que o diretório src/ está no path
sys.path.insert(0, str(Path(__file__).parent))

from collect import collect_all
from llm import LLMRouter
from pipeline import process_items

# ── Logging ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


# ── Helpers ───────────────────────────────────────────────────────────────

def load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def group_by_theme(items: list[dict]) -> dict[str, list[dict]]:
    """Agrupa itens por tema, ordenados por relevância decrescente."""
    grouped: dict[str, list[dict]] = {}
    for item in items:
        tema = item.get("tema") or "outros"
        grouped.setdefault(tema, []).append(item)
    # Ordena cada grupo por relevância
    for tema in grouped:
        grouped[tema].sort(key=lambda x: x.get("relevancia") or 0, reverse=True)
    return grouped


def build_output(items: list[dict], generated_at: str) -> dict:
    """Monta o objeto data.json."""
    grouped = group_by_theme(items)
    # Remove campos internos (comments brutos) para não inflar o JSON
    clean_items = []
    for item in items:
        clean = {k: v for k, v in item.items() if k != "comments"}
        clean_items.append(clean)

    clean_grouped: dict[str, list[dict]] = {}
    for tema, tema_items in grouped.items():
        clean_grouped[tema] = [{k: v for k, v in i.items() if k != "comments"} for i in tema_items]

    return {
        "generated_at": generated_at,
        "total_items": len(items),
        "themes": clean_grouped,
        "all_items": clean_items,
    }


def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Salvo: %s", path)


def update_archive_index(archive_dir: Path) -> None:
    """Mantém docs/archive/index.json com lista de datas disponíveis."""
    index_path = archive_dir / "index.json"

    dates: list[dict] = []
    for jf in sorted(archive_dir.glob("[0-9][0-9][0-9][0-9]-*.json")):
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
            dates.append({
                "date": jf.stem,
                "total_items": data.get("total_items", 0),
                "generated_at": data.get("generated_at", ""),
            })
        except Exception:
            pass

    save_json({"dates": dates}, index_path)


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config.yaml"
    docs_dir = repo_root / "docs"

    logger.info("=== DailyBrief Pipeline iniciado ===")

    # 1. Config
    cfg = load_config(config_path)

    # 2. Coleta
    logger.info("--- Etapa 1: Coleta ---")
    items = collect_all(cfg)
    logger.info("Total coletado: %d itens", len(items))

    if not items:
        logger.warning("Nenhum item coletado. Abortando.")
        # Publica data.json vazio para não quebrar o site
        generated_at = datetime.now(timezone.utc).isoformat()
        output = build_output([], generated_at)
        save_json(output, docs_dir / "data.json")
        return

    # 3. LLM
    logger.info("--- Etapa 2: Processamento LLM ---")
    router = LLMRouter(cfg)
    items = process_items(items, cfg, router)

    # 4. Saída
    logger.info("--- Etapa 3: Salvando saídas ---")
    # Usa horário de São Paulo para o nome do arquivo de arquivo
    sp_offset = timedelta(hours=-3)
    now_sp = datetime.now(timezone.utc).astimezone(timezone(sp_offset))
    date_str = now_sp.strftime("%Y-%m-%d")
    generated_at = datetime.now(timezone.utc).isoformat()

    output = build_output(items, generated_at)

    # data.json (atual)
    save_json(output, docs_dir / "data.json")

    # Archive
    archive_path = docs_dir / "archive" / f"{date_str}.json"
    save_json(output, archive_path)

    # Atualiza índice de arquivos
    update_archive_index(docs_dir / "archive")

    logger.info("=== Pipeline concluído: %d itens processados ===", len(items))


if __name__ == "__main__":
    main()
