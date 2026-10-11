"""Seed synthetic personas into the pool.  Usage (from backend/):  python -m db.seed [--demo path] [--personas dir]

Preferred source is data/demo/demo.json (DemoBundle: people+profiles+dates+briefings), which needs no LLM.
Fallback: data/personas/*.json fixtures run through ingestion+analysis. All seeded people are flagged synthetic.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .store import get_store

ROOT = next((b for b in Path(__file__).resolve().parents[1:3] if (b / "data").is_dir()), Path("."))
log = logging.getLogger("seed")


def seed_from_demo(path: Path) -> int:
    from common.models import DemoBundle

    store = get_store()
    bundle = DemoBundle.model_validate_json(path.read_text(encoding="utf-8"))
    for p in bundle.people:
        store.upsert_synthetic_person(person_id=p.id, display_name=p.display_name)
        if p.profile:
            store.save_profile(p.id, p.profile.model_dump(mode="json"))
    for d in bundle.dates:
        store.save_date(d.model_dump(mode="json"))
    for pid, b in bundle.briefings.items():
        store.save_briefing(pid, b.model_dump(mode="json"))
    return len(bundle.people)


def seed_from_personas(directory: Path) -> int:
    from api import adapters

    store = get_store()
    n = 0
    for f in sorted(directory.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                continue
            pid = str(d.get("id") or f.stem)
            store.upsert_synthetic_person(person_id=pid, display_name=str(d.get("display_name") or d.get("name") or pid))
            li = d.get("linkedin") if "linkedin" in d else d.get("linkedin_data")
            ig = d.get("instagram") if "instagram" in d else d.get("instagram_data")
            store.save_profile(pid, adapters.analyze_profile(li, ig, person_id=pid))
            n += 1
        except Exception:
            log.exception("seeding %s failed", f)
    return n


def seed(demo: Path | None = None, personas: Path | None = None) -> int:
    demo = demo or ROOT / "data" / "demo" / "demo.json"
    personas = personas or ROOT / "data" / "personas"
    if demo.exists():
        return seed_from_demo(demo)
    if personas.exists():
        return seed_from_personas(personas)
    log.warning("nothing to seed: %s and %s are missing", demo, personas)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", type=Path)
    ap.add_argument("--personas", type=Path)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(f"seeded {seed(a.demo, a.personas)} people")
