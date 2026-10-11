import json

import pytest

from agents.analyst import analyze
from agents.briefing import answer_why, make_briefing
from agents.personas_loader import load_personas
from agents.referee import apply_referee, referee
from common.llm import MockClient, get_client
from common.models import Briefing, DateRecord, DateTurn


@pytest.fixture(scope="module")
def prof():
    c = get_client()
    return {p["id"]: analyze(p, c) for p in load_personas()}


def _record(texts):
    turns = [
        DateTurn(idx=i, speaker="p01" if i % 2 == 0 else "p04", stage="opening", public_text=t, private_note="", chemistry=5)
        for i, t in enumerate(texts)
    ]
    return DateRecord(id="d1", person_a="p01", person_b="p04", turns=turns)


def test_mock_handlers_registered():
    get_client()
    for t in ("analyst", "referee", "briefing", "ask"):
        assert t in MockClient.handlers


def test_referee_flags_injected_unsupported_claim(prof):
    rec = _record([
        "Hi, I'm Maren. I climb most weekends and I love sunrise summits.",  # supported (p01)
        "Nice to meet you. I throw pots on a wheel to unwind.",  # supported (p04 pottery)
        "I've been surfing every winter for ten years, honestly it is my whole personality.",  # p01 never mentions surfing
        "Do you like hiking too?",  # question: not a claim
        "I spend my weekends playing the violin in an orchestra.",  # p01: unsupported
        "I love ceramics and slow Sundays.",  # supported
    ])
    res = referee(rec, prof["p01"], prof["p04"], get_client())
    assert 2 in res.flagged_turns and 4 in res.flagged_turns
    assert 0 not in res.flagged_turns and 1 not in res.flagged_turns and 3 not in res.flagged_turns and 5 not in res.flagged_turns
    assert all(f["type"] == "unsupported_claim" for f in res.flags)
    assert res.faithfulness_a == pytest.approx(1 - 2 / 3, abs=1e-3)  # a spoke turns 0,2,4; two flagged
    assert res.faithfulness_b == 1.0
    apply_referee(rec, res)
    assert rec.flagged_turns == [2, 4] and rec.turns[2].flags[0]["type"] == "unsupported_claim"
    assert rec.faithfulness_a == res.faithfulness_a


def test_referee_clean_transcript(prof):
    rec = _record(["I climb and hike a lot.", "I make pottery and drink coffee."])
    res = referee(rec, prof["p01"], prof["p04"], get_client())
    assert res.flagged_turns == [] and res.faithfulness_a == 1.0 == res.faithfulness_b


def test_referee_ignores_out_of_range_turns(prof):
    class Fake:
        def complete(self, **kw):
            return json.dumps({"flags": [{"turn": 99, "note": "x"}, {"turn": "bad"}, {"turn": 0, "note": "ok"}]})

    res = referee(_record(["hi", "hello"]), prof["p01"], prof["p04"], Fake())
    assert res.flagged_turns == [0]


RANKINGS = [
    {"person_id": "p02", "name": "Idris Brannock", "score": 8.4, "why": "Shared early starts and outdoor training.", "best_moment": "We both hate snoozing"},
    {"person_id": "p10", "name": "Thalia Brightwater", "score": 7.9, "why": "Both love adventure."},
    {"person_id": "p03", "name": "Josie Harland-Pike", "score": 7.1},
    {"person_id": "p08", "name": "Odalys Pemberton", "score": 5.0, "friction": "Little overlap outside work."},
    {"person_id": "p09", "name": "Gideon Marsh-Calloway", "score": 3.2, "friction": "Wanted opposite weekends."},
    {"person_id": "p01", "score": 10},
]


def test_briefing(prof):
    b = make_briefing("p01", RANKINGS, prof["p01"], client=get_client())
    assert isinstance(b, Briefing)
    assert [i["person_id"] for i in b.introduce] == ["p02", "p10", "p03"]
    assert [w["person_id"] for w in b.warn] == ["p09", "p08"]
    assert b.unsure and all(isinstance(u, str) for u in b.unsure)
    assert "p01" not in json.dumps(b.model_dump())


def test_briefing_flags_uncertainty_for_thin_profile(prof):
    b = make_briefing("p25", RANKINGS, prof["p25"], client=get_client())
    assert any("instagram" in u.lower() for u in b.unsure)


def test_answer_why(prof):
    c = get_client()
    a = answer_why("Why did you rank Thalia so high?", "p01", RANKINGS, prof["p01"], client=c)
    assert "Thalia" in a and "#2" in a
    top = answer_why("who is my best match and why?", "p01", RANKINGS, prof["p01"], client=c)
    assert "Idris" in top and "#1" in top
    low = answer_why("why is p09 last", "p01", RANKINGS, prof["p01"], client=c)
    assert "opposite weekends" in low


def test_answer_why_refuses_sensitive(prof):
    a = answer_why("Did you factor in their religion or politics?", "p01", RANKINGS, prof["p01"], client=get_client())
    assert "do not infer" in a
