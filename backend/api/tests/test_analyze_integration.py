"""Integration: the real analyst, fed through the API adapter, must see the ingested source text."""
from agents.personas_loader import load_personas
from api import adapters


def test_adapter_passes_sources_to_real_analyst():
    p = load_personas()[0]
    prof = adapters.analyze_profile(p["linkedin"], p["instagram"], person_id=p["id"])
    assert prof["source_status"] == {"linkedin": "ok", "instagram": "ok"}
    assert prof["hobbies"] or prof["interests"]
