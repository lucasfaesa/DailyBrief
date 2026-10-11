"""
main.py – Main orchestrator for the DailyBrief pipeline.

Execution flow:
  1. Load config.yaml
  2. Collect news items (Hacker News + Reddit + RSS)
  3. Process through LLM (classify + summarize)
  4. Write docs/data.json and docs/archive/YYYY-MM-DD.json
  5. Automatic git commit handled by GitHub Actions
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from collect import collect_all
from llm import LLMRouter
from pipeline import process_items

# ── Logging Setup ─────────────────────────────────────────────────────────

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
    """Groups items by theme, ordered by relevance descending."""
    grouped: dict[str, list[dict]] = {}
    for item in items:
        theme = item.get("theme") or item.get("tema") or "others"
        grouped.setdefault(theme, []).append(item)
    for theme in grouped:
        grouped[theme].sort(
            key=lambda x: x.get("relevance") or x.get("relevancia") or 0,
            reverse=True,
        )
    return grouped


def build_output(items: list[dict], generated_at: str) -> dict:
    """Constructs the data.json payload."""
    grouped = group_by_theme(items)
    # Strip raw comment strings to keep output lean
    clean_items = []
    for item in items:
        clean = {k: v for k, v in item.items() if k != "comments"}
        clean_items.append(clean)

    clean_grouped: dict[str, list[dict]] = {}
    for theme, theme_items in grouped.items():
        clean_grouped[theme] = [{k: v for k, v in i.items() if k != "comments"} for i in theme_items]

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
    logger.info("Saved: %s", path)


def update_archive_index(archive_dir: Path) -> None:
    """Maintains docs/archive/index.json with list of available dates."""
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


# ── Main Entrypoint ───────────────────────────────────────────────────────

def main() -> None:
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "config.yaml"
    docs_dir = repo_root / "docs"

    logger.info("=== DailyBrief Pipeline Started ===")

    # 1. Config
    cfg = load_config(config_path)

    # 2. Ingestion
    logger.info("--- Step 1: News Collection ---")
    items = collect_all(cfg)
    logger.info("Total items gathered: %d", len(items))

    if not items:
        logger.warning("No items collected. Writing empty payload.")
        generated_at = datetime.now(timezone.utc).isoformat()
        output = build_output([], generated_at)
        save_json(output, docs_dir / "data.json")
        return

    # 3. LLM Pipeline
    logger.info("--- Step 2: LLM Classification & Summaries ---")
    router = LLMRouter(cfg)
    items = process_items(items, cfg, router)

    # 4. Persistence
    logger.info("--- Step 3: Writing Output Payloads ---")
    sp_offset = timedelta(hours=-3)
    now_sp = datetime.now(timezone.utc).astimezone(timezone(sp_offset))
    date_str = now_sp.strftime("%Y-%m-%d")
    generated_at = datetime.now(timezone.utc).isoformat()

    output = build_output(items, generated_at)

    # Active daily feed
    save_json(output, docs_dir / "data.json")

    # Historical archive
    archive_path = docs_dir / "archive" / f"{date_str}.json"
    save_json(output, archive_path)

    # Archive index catalog
    update_archive_index(docs_dir / "archive")

    logger.info("=== Pipeline Completed: %d items processed ===", len(items))


if __name__ == "__main__":
    main()
