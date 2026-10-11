import json

import pytest

from agents.analyst import CLAIM_FIELDS, analyze, apply_sensitive_filter, filter_sensitive
from agents.lexicon import sensitive_categories
from agents.personas_loader import load_personas, source_text
from common.llm import get_client
from common.models import Claim, IdentityMatch, Persona, PersonaGap, Profile, Trait


@pytest.fixture(scope="module")
def personas():
    return load_personas()


@pytest.fixture(scope="module")
def profiles(personas):
    c = get_client()
    return {p["id"]: analyze(p, c) for p in personas}


def test_25_synthetic_labelled_personas(personas):
    assert len(personas) == 25
    assert [p["id"] for p in personas] == [f"p{i:02d}" for i in range(1, 26)]
    for p in personas:
        assert p["synthetic"] is True and "SYNTHETIC" in p["label"]
        assert not sensitive_categories(source_text(p, "linkedin") + source_text(p, "instagram"))


def _all_claims(p: Profile):
    for f in CLAIM_FIELDS:
        for c in getattr(p, f):
            yield f, c, c.source
    for f in ("communication_style", "humor", "energy"):
        yield f, getattr(p, f), None


def test_every_claim_has_literal_evidence_and_confidence(personas, profiles):
    for fx in personas:
        prof = profiles[fx["id"]]
        texts = {s: source_text(fx, s) for s in ("linkedin", "instagram")}
        n = 0
        for f, c, src in _all_claims(prof):
            assert c.evidence.strip(), (fx["id"], f, c.value)
            pool = texts[src] if src else texts["linkedin"] + "\n" + texts["instagram"]
            assert c.evidence in pool, (fx["id"], f, c.value, c.evidence)
            assert 0 <= c.confidence <= 1
            n += 1
        assert n >= 5
        for key, per in (("linkedin", prof.linkedin_persona), ("instagram", prof.instagram_persona)):
            for e in per.evidence:
                assert e in texts[key]
        assert 0 <= prof.persona_gap.score <= 1 and 0 <= prof.identity_match.score <= 1


def test_profiles_differ_and_gap_variation(profiles):
    assert len({json.dumps([c.value for c in p.hobbies]) for p in profiles.values()}) > 10
    gaps = {k: p.persona_gap.score for k, p in profiles.items()}
    for big in ("p09", "p21", "p22", "p24"):
        assert gaps[big] >= 0.7, gaps
    assert gaps["p01"] < 0.6 and gaps["p01"] < gaps["p22"]


def test_thin_sources(profiles):
    assert profiles["p25"].source_status["instagram"] == "thin"
    assert profiles["p19"].source_status["instagram"] == "thin"
    assert profiles["p01"].source_status == {"linkedin": "ok", "instagram": "ok"}
    assert profiles["p25"].persona_gap.score <= 0.25


def test_no_sensitive_content_in_any_profile(profiles):
    for p in profiles.values():
        assert not sensitive_categories(json.dumps(p.model_dump()))


def test_source_not_readable():
    fx = {"id": "x", "display_name": "X Y",
          "linkedin": {"headline": "Plumber who likes climbing and hiking outdoors every weekend",
                       "about": "I climb a lot and hike. Looking for someone who loves the outdoors.", "location": "Leeds"},
          "instagram": None}
    p = analyze(fx, get_client())
    assert p.source_status["instagram"] == "not_readable"
    assert all(c.source == "linkedin" for _, c, s in _all_claims(p) if s)
    assert p.identity_match.score < 0.5 and "LOW" in p.identity_match.reason


class FakeClient:
    """Returns a hostile/sloppy model output to exercise validation."""

    def __init__(self, raw):
        self.raw = raw

    def complete(self, **kw):
        return json.dumps(self.raw)


def test_fabricated_evidence_dropped_and_case_fixed(personas):
    fx = personas[0]
    li = source_text(fx, "linkedin")
    raw = {
        "summary": "s",
        "hobbies": [
            {"value": "climbing", "evidence": "I climb most weekends", "source": "linkedin", "confidence": 0.9},
            {"value": "CLIMBING-lowercase", "evidence": "I CLIMB MOST WEEKENDS", "source": "linkedin", "confidence": 0.9},
            {"value": "skydiving", "evidence": "I skydive over the Alps", "source": "linkedin", "confidence": 0.99},
        ],
        "humor": {"value": "dry", "evidence": "invented quote not in text", "confidence": 0.9},
        "linkedin_persona": {"summary": "x", "evidence": ["I climb most weekends", "made up line"]},
    }
    p = analyze(fx, FakeClient(raw))
    vals = [c.value for c in p.hobbies]
    assert "skydiving" not in vals and "climbing" in vals
    for c in p.hobbies:
        assert c.evidence in li
    assert p.humor.confidence <= 0.1 and p.humor.value == "not enough evidence"
    assert p.linkedin_persona.evidence == ["I climb most weekends"]


def test_thin_source_lowers_confidence():
    fx = {"id": "t", "display_name": "T", "linkedin": {"headline": "Engineer", "about": "I love cooking.", "location": "Leeds"},
          "instagram": {"bio": "hi", "location": "Leeds", "posts": []}}
    raw = {"hobbies": [{"value": "cooking", "evidence": "I love cooking.", "source": "linkedin", "confidence": 0.9}]}
    p = analyze(fx, FakeClient(raw))
    assert p.source_status["linkedin"] == "thin"
    assert p.hobbies[0].confidence == pytest.approx(0.63)


# ---- sensitive-inference post-filter ----

def _profile_with(claims, trait_value="warm", trait_ev="I am warm"):
    t = Trait(value=trait_value, evidence=trait_ev, confidence=0.5)
    return Profile(summary="s", values=claims, communication_style=t, humor=t, energy=t,
                   linkedin_persona=Persona(summary=""), instagram_persona=Persona(summary=""),
                   persona_gap=PersonaGap(score=0, description=""), identity_match=IdentityMatch(score=1, reason=""),
                   source_status={"linkedin": "ok", "instagram": "ok"})


@pytest.mark.parametrize("text,cat", [
    ("Volunteers at the church every Sunday", "religion"),
    ("Attends mosque and prayer groups", "religion"),
    ("She is a lesbian activist", "sexual_orientation"),
    ("Is transgender and proud", "gender_identity"),
    ("Was diagnosed with depression last year", "health"),
    ("Manages chronic illness and medication", "health"),
    ("Votes for the Republican party", "politics"),
    ("Proud conservative", "politics"),
    ("Strong ethnic heritage", "ethnicity"),
])
def test_sensitive_filter_drops(text, cat):
    assert cat in sensitive_categories(text)
    keep = Claim(value="community", evidence="I help my neighbours", source="linkedin", confidence=0.8)
    bad = Claim(value="belief", evidence=text, source="instagram", confidence=0.9)
    out, dropped = apply_sensitive_filter(_profile_with([keep, bad]))
    assert [c.value for c in out.values] == ["community"]
    assert dropped and cat in dropped[0]["categories"]


def test_sensitive_filter_checks_value_and_neutralises_traits():
    bad_val = Claim(value="religious", evidence="I enjoy quiet Sundays", source="instagram", confidence=0.9)
    out = filter_sensitive(_profile_with([bad_val], trait_value="political firebrand", trait_ev="I vote for the democrat"))
    assert out.values == []
    assert out.humor.value == "not enough evidence" and out.humor.confidence <= 0.1


def test_sensitive_filter_applied_inside_analyze(personas):
    raw = {"values": [{"value": "devout", "evidence": "I am direct and honest about risk", "source": "linkedin", "confidence": 0.9},
                      {"value": "honesty", "evidence": "I am direct and honest about risk", "source": "linkedin", "confidence": 0.9}]}
    p = analyze(personas[0], FakeClient(raw))
    assert [c.value for c in p.values] == ["honesty"]


def test_benign_text_not_flagged():
    for t in ("I climb and cook", "straight-talking engineer", "temple run speedrun", "Bouldering before breakfast", "Race number collected"):
        assert sensitive_categories(t) == []
