import pytest
from fastapi.testclient import TestClient

from api import adapters, jobs, pipeline
from api.main import app
from api.ratelimit import limiter
from common.models import DateRecord, DateTurn, Profile, Rubric, Trait, Persona, PersonaGap, IdentityMatch
from db import store as store_mod


def make_profile(**kw) -> dict:
    t = Trait(value="v", evidence="e", confidence=0.5)
    p = Profile(summary="s", communication_style=t, humor=t, energy=t,
                linkedin_persona=Persona(summary="l"), instagram_persona=Persona(summary="i"),
                persona_gap=PersonaGap(score=0.1, description="d"), identity_match=IdentityMatch(score=0.9, reason="r"),
                source_status={"linkedin": "ok", "instagram": "ok"})
    return p.model_dump(mode="json")


def rub(x: float) -> Rubric:
    return Rubric(interest_overlap=x, values_alignment=x, communication_chemistry=x, lifestyle_fit=x,
                  growth_potential=x, would_meet_again=x >= 5, verdict="ok")


def fake_run_date(profile_a, profile_b, ids, kind="standard", on_event=None, names=None, date_id=None):
    a, b = ids
    rec = DateRecord(id=date_id or f"{a}__{b}", person_a=a, person_b=b, kind=kind, status="running")
    if on_event:
        on_event({"event": "turn", "data": {"event_start": True, "date_id": rec.id}})
    for i in range(3):
        t = DateTurn(idx=i, speaker=a if i % 2 == 0 else b, stage="opening", public_text=f"hello {i}",
                     private_note="n", chemistry=4 + i)
        rec.turns.append(t)
        if on_event:
            on_event({"event": "turn", "data": t.model_dump()})
            on_event({"event": "chemistry", "data": {"idx": i, "speaker": t.speaker, "chemistry": t.chemistry}})
    rec.score_a, rec.score_b = rub(8), rub(6)
    rec.status = "done"
    if on_event:
        on_event({"event": "done", "data": {"date_id": rec.id, "status": "done"}})
    return rec


@pytest.fixture
def mem():
    s = store_mod.MemoryStore()
    store_mod.set_store(s)
    limiter.reset()
    jobs.reset()
    jobs.set_mode("inline")
    pipeline._buses.clear()
    yield s
    store_mod.set_store(None)
    jobs.set_mode(None)


@pytest.fixture
def client(mem, monkeypatch):
    calls = {"ingest": 0}

    def ingest(person_id, li, ig):
        calls["ingest"] += 1
        return {"linkedin": ({"headline": "h"}, "ok"), "instagram": ({"bio": "b"}, "thin")}

    monkeypatch.setattr(adapters, "ingest", ingest)
    monkeypatch.setattr(adapters, "analyze_profile", lambda li, ig, person_id="": make_profile())
    monkeypatch.setattr(adapters, "run_date", fake_run_date)
    monkeypatch.setattr(adapters, "referee", lambda rec, a, b: rec)
    c = TestClient(app)
    c.calls = calls
    return c


GOOD = {"linkedin_url": "https://www.linkedin.com/in/jane-doe", "instagram_url": "https://www.instagram.com/jane.doe",
        "consent": True}
