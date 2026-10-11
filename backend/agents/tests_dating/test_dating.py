import json
import statistics as st

import pytest

from agents import mock_dates
from agents.dating import SCHEDULES, run_date
from agents.persona import parse_plan, parse_rubric, parse_speak
from agents.tests_dating.fakes import make_pool, make_profile
from common.llm import MockClient
from common.models import DIMENSIONS, STAGES, DateRecord


@pytest.fixture(autouse=True)
def _handlers():
    mock_dates.register()


def _date(i=0, j=1, **kw):
    pool = make_pool(25)
    a, b = pool[i], pool[j]
    return run_date(a[2], b[2], (a[0], b[0]), names={a[0]: a[1], b[0]: b[1]}, **kw), a, b


def test_stage_order_and_length():
    rec, *_ = _date()
    assert rec.status == "done" and 6 <= len(rec.turns) <= 10
    idxs = [STAGES.index(t.stage) for t in rec.turns]
    assert idxs == sorted(idxs)
    assert rec.turns[0].stage == "opening" and rec.turns[-1].stage == "close"
    assert [t.idx for t in rec.turns] == list(range(len(rec.turns)))
    assert {t.speaker for t in rec.turns} == {rec.person_a, rec.person_b}
    for n, sched in SCHEDULES.items():
        assert len(sched) == n and [STAGES.index(s) for s in sched] == sorted(STAGES.index(s) for s in sched)


def test_rubric_bounds_and_directional_difference():
    rec, *_ = _date()
    for s in (rec.score_a, rec.score_b):
        assert s is not None and s.verdict
        for d in DIMENSIONS:
            assert 0 <= getattr(s, d) <= 10
        assert isinstance(s.would_meet_again, bool)
    assert any(getattr(rec.score_a, d) != getattr(rec.score_b, d) for d in DIMENSIONS)


def test_determinism():
    r1, *_ = _date(2, 5)
    r2, *_ = _date(2, 5)
    assert r1.model_dump() == r2.model_dump()


class DeadClient:
    """plan always reports dead chemistry; speak/rubric are trivial."""

    def complete(self, *, system, user, tier="fast", task="", context=None):
        if task == "plan":
            return json.dumps({"learned": "", "probe": "", "private_note": "cold", "chemistry": 0.5, "end_date": False})
        if task == "speak":
            return json.dumps({"message": "ok"})
        return json.dumps({d: 1 for d in DIMENSIONS} | {"would_meet_again": False, "verdict": "no"})


def test_early_exit_on_dead_chemistry():
    pa, pb = make_profile(1), make_profile(2)
    rec = run_date(pa, pb, ("a", "b"), client=DeadClient())
    assert rec.status == "done"
    assert len(rec.turns) < 8
    assert rec.turns[-1].stage == "close"
    assert rec.score_a.would_meet_again is False


class SpyClient:
    """records every prompt; returns healthy plan/speak/rubric."""

    def __init__(self):
        self.calls = []

    def complete(self, *, system, user, tier="fast", task="", context=None):
        self.calls.append((system, user, task, context))
        if task == "plan":
            return json.dumps({"learned": "x", "probe": "p", "private_note": "n", "chemistry": 6, "end_date": False})
        if task == "speak":
            return json.dumps({"message": "hello there"})
        return json.dumps({d: 7 for d in DIMENSIONS} | {"would_meet_again": True, "verdict": "good"})


def test_persona_isolation():
    pa, pb = make_profile(11), make_profile(12)
    spy = SpyClient()
    run_date(pa, pb, ("a", "b"), client=spy, names={"a": "Alice", "b": "Bob"}, kind="scenario")
    assert spy.calls
    a_only = {"b_summary": pb.summary}
    secret_b = [c.value for k in ("hobbies", "interests", "values", "lifestyle", "wants_in_partner", "needs") for c in getattr(pb, k)]
    secret_a = [c.value for k in ("hobbies", "interests", "values", "lifestyle", "wants_in_partner", "needs") for c in getattr(pa, k)]
    secret_b = [s for s in secret_b if s not in secret_a]  # only values unique to B can prove a leak
    secret_a = [s for s in secret_a if s not in [c.value for k in ("hobbies", "interests", "values", "lifestyle", "wants_in_partner", "needs") for c in getattr(pb, k)]]
    assert secret_a and secret_b
    for system, user, task, ctx in spy.calls:
        text = system + user
        speaker_is_a = "dating agent for Alice" in system
        mine, theirs = (pa, secret_b) if speaker_is_a else (pb, secret_a)
        assert mine.summary in system
        for s in theirs:
            assert s not in text
        # a real (non-mock) client never receives the other profile via context either
        assert not ctx or "mock_oracle" not in ctx
    assert a_only["b_summary"] not in "".join(s + u for s, u, *_ in spy.calls if "dating agent for Alice" in s)


def test_events_streamed():
    ev = []
    rec, *_ = _date(on_event=ev.append)
    kinds = [e["event"] for e in ev]
    assert kinds.count("turn") == len(rec.turns) and kinds.count("chemistry") == len(rec.turns)
    assert kinds[-1] == "done" and kinds.count("done") == 1
    assert kinds.count("flag") == sum(len(t.flags) for t in rec.turns)


def test_speech_uses_only_own_profile():
    rec, a, b = _date(3, 4)
    own = {rec.person_a: a[2], rec.person_b: b[2]}
    other_only = {rec.person_a: b[2], rec.person_b: a[2]}
    for t in rec.turns:
        p, o = own[t.speaker], other_only[t.speaker]
        mine = {c.value for k in ("hobbies", "interests", "values", "lifestyle", "wants_in_partner", "needs") for c in getattr(p, k)}
        theirs = {c.value for k in ("hobbies", "interests", "values", "lifestyle", "wants_in_partner", "needs") for c in getattr(o, k)} - mine
        said_before = " ".join(x.public_text for x in rec.turns[: t.idx] if x.speaker != t.speaker).lower()
        for v in theirs:
            # may only appear if the other party already said it publicly
            assert v.lower() not in t.public_text.lower() or v.lower() in said_before


def test_scenario_kind():
    rec, *_ = _date(kind="scenario")
    assert rec.kind == "scenario" and rec.id.endswith("__scenario")
    assert any("1500" in t.public_text or "budget" in t.public_text.lower() for t in rec.turns)


def test_mock_variance_matrix():
    pool = make_pool(25)
    m = [[st.mean(mock_dates.directional_scores(x[2], y[2], x[0], y[0]).values()) for y in pool if y is not x] for x in pool]
    flat = [v for r in m for v in r]
    assert st.pstdev(flat) > 0.8
    assert max(flat) - min(flat) > 4


def test_parsers_are_robust():
    assert parse_plan("garbage not json", 4.0)["chemistry"] == 4.0
    assert parse_plan('x {"chemistry": 99, "private_note": "n"}', 4.0)["chemistry"] == 10
    assert parse_speak("plain words") == "plain words"
    r = parse_rubric("nonsense")
    assert all(0 <= getattr(r, d) <= 10 for d in DIMENSIONS)
    r = parse_rubric(json.dumps({d: 50 for d in DIMENSIONS} | {"would_meet_again": "yes", "verdict": "v"}))
    assert r.interest_overlap == 10 and isinstance(r.would_meet_again, bool)


def test_registers_on_mockclient():
    assert {"plan", "speak", "rubric"} <= set(MockClient.handlers)
    saved = dict(MockClient.handlers)
    try:
        MockClient.handlers = {}
        rec = run_date(make_profile(1), make_profile(2), ("a", "b"), client=MockClient())  # re-registers itself
        assert rec.status == "done"
    finally:
        MockClient.handlers = saved


def test_round_robin_300_dates(tmp_path):
    from scripts import round_robin as rr
    from common.models import DemoBundle

    out = tmp_path / "demo.json"
    rr.main(["--fake", "--out", str(out)])
    b = DemoBundle.model_validate_json(out.read_text(encoding="utf-8"))
    std = [d for d in b.dates if d.kind == "standard"]
    assert len(b.people) == 25 and len(std) == 300
    assert len({(d.person_a, d.person_b) for d in std}) == 300
    assert len([d for d in b.dates if d.kind == "scenario"]) == 3
    vals = [v for r in b.matrix for v in r if v is not None]
    assert len(vals) == 25 * 24 and st.pstdev(vals) > 0.8
    assert all(b.matrix[i][i] is None for i in range(25))
    assert b.stable_pairs and len(b.briefings) == 25 and b.best_moments
    assert out.stat().st_size < 6_000_000


def test_jobs_inline():
    from workers.jobs import enqueue, run_date_job, run_pool_job

    pool = make_pool(4)
    d = enqueue(run_date_job, {"profile_a": pool[0][2].model_dump(), "profile_b": pool[1][2].model_dump(), "ids": ["p01", "p02"], "referee": False})
    DateRecord.model_validate(d)
    res = run_pool_job("p01", {i: p.model_dump() for i, _, p in pool})
    assert len(res) == 3 and all(r["status"] == "done" for r in res)
