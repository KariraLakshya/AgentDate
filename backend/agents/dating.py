"""Date engine: runs a plan -> speak -> reflect loop between two persona agents and streams events.

run_date(profile_a, profile_b, ids, client=None, kind="standard", on_event=None) -> DateRecord
Each turn the speaker PLANS (private note, learned, probe, chemistry 0-10), SPEAKS (public message) and the
speaker's next plan REFLECTS on the other side's reply (the `learned` field). After the date each agent fills the
rubric privately."""
from __future__ import annotations

import logging
from typing import Callable

from common.models import STAGES, DateRecord, DateTurn, Profile
from agents.persona import PersonaAgent

log = logging.getLogger(__name__)

SCHEDULES = {
    8: ["opening", "shared_interests", "shared_interests", "friction", "values", "what_do_you_want", "what_do_you_want", "close"],
    9: ["opening", "shared_interests", "shared_interests", "friction", "friction", "values", "what_do_you_want", "what_do_you_want", "close"],
    10: ["opening", "opening", "shared_interests", "shared_interests", "friction", "friction", "values", "what_do_you_want", "what_do_you_want", "close"],
}
SPARK_DELTA = 1.2
FRICTION_DELTA = -1.2
REPAIR_DELTA = 0.8
DEAD_CHEM = 2.5
MIN_TURNS_BEFORE_EXIT = 4

SCENARIO_TASK = (
    "Together, plan a 4-day trip with ONE shared budget of 1500 USD. There is a built-in disagreement: "
    "decide how to split the money between comfort (nicer places to stay and eat) and experiences (activities, "
    "going out). {stance} Try to reach a plan you both can live with, or say honestly if you cannot."
)
SCENARIO_STANCES = (
    "You lean toward spending most of it on comfort, in line with your own lifestyle.",
    "You lean toward spending most of it on experiences, in line with your own lifestyle.",
)


def _ensure_mock():
    """Register mock handlers for plan/speak/rubric (idempotent; survives another module resetting handlers)."""
    from agents import mock_dates

    mock_dates.register()


def default_client():
    from common import config

    if config.LLM_MODE == "anthropic":
        from common.llm import get_client

        return get_client()
    _ensure_mock()
    from common.llm import MockClient

    try:  # let agent B's handlers load too if present
        from agents import mock  # noqa: F401
    except ImportError:
        pass
    _ensure_mock()
    return MockClient()


def _is_mock(client) -> bool:
    from common.llm import MockClient

    return isinstance(client, MockClient)


def _emit(on_event, event: str, data: dict):
    if on_event:
        try:
            on_event({"event": event, "data": data})
        except Exception:  # a broken stream consumer must never kill a date
            log.exception("on_event failed")


def _flags_for(prev: float | None, cur: float, last_flag: str | None) -> list[dict]:
    if prev is None:
        return []
    d = cur - prev
    if d >= SPARK_DELTA:
        if last_flag == "friction":
            return [{"type": "repair", "note": f"Chemistry recovered after friction (+{d:.1f})"}]
        return [{"type": "spark", "note": f"Chemistry jumped +{d:.1f}"}]
    if d <= FRICTION_DELTA:
        return [{"type": "friction", "note": f"Chemistry dropped {d:.1f}"}]
    if d >= REPAIR_DELTA and last_flag == "friction":
        return [{"type": "repair", "note": f"Chemistry recovering after friction (+{d:.1f})"}]
    return []


def run_date(
    profile_a: Profile,
    profile_b: Profile,
    ids: tuple[str, str],
    client=None,
    kind: str = "standard",
    on_event: Callable[[dict], None] | None = None,
    *,
    names: dict[str, str] | None = None,
    n_turns: int = 10,
    date_id: str | None = None,
) -> DateRecord:
    id_a, id_b = ids
    names = {id_a: id_a, id_b: id_b, **(names or {})}
    client = client or default_client()
    schedule = list(SCHEDULES.get(n_turns, SCHEDULES[10]))
    assert all(s in STAGES for s in schedule)
    record = DateRecord(id=date_id or (f"{id_a}__{id_b}" + ("__scenario" if kind == "scenario" else "")),
                        person_a=id_a, person_b=id_b, kind=kind, status="running")
    task_a = task_b = None
    if kind == "scenario":
        task_a = SCENARIO_TASK.format(stance=SCENARIO_STANCES[0])
        task_b = SCENARIO_TASK.format(stance=SCENARIO_STANCES[1])
    mock = _is_mock(client)
    if mock:
        _ensure_mock()
    # The other side's profile is handed ONLY to MockClient (so scores derive from real overlap); never to a real model
    agent_a = PersonaAgent(id_a, names[id_a], profile_a, client, task_a,
                           extra_ctx={"mock_oracle": {"other_profile": profile_b.model_dump(), "kind": kind}} if mock else {})
    agent_b = PersonaAgent(id_b, names[id_b], profile_b, client, task_b,
                           extra_ctx={"mock_oracle": {"other_profile": profile_a.model_dump(), "kind": kind}} if mock else {})
    agents = [agent_a, agent_b]
    history: list[dict] = []
    prev_chem: dict[str, float | None] = {id_a: None, id_b: None}
    last_flag: dict[str, str | None] = {id_a: None, id_b: None}
    total = len(schedule)
    try:
        idx = 0
        while idx < len(schedule):
            stage = schedule[idx]
            ag = agents[idx % 2]
            plan = ag.plan(stage, idx, total, history, names)
            text = ag.speak(stage, idx, total, plan, history, names)
            flags = _flags_for(prev_chem[ag.person_id], ag.chemistry, last_flag[ag.person_id])
            if flags:
                last_flag[ag.person_id] = flags[0]["type"]
            elif prev_chem[ag.person_id] is not None:
                last_flag[ag.person_id] = None
            prev_chem[ag.person_id] = ag.chemistry
            note = plan["private_note"]
            if plan["learned"]:
                note = f"Learned: {plan['learned']} | {note}"
            turn = DateTurn(idx=idx, speaker=ag.person_id, stage=stage, public_text=text, private_note=note,
                            chemistry=round(ag.chemistry, 2), flags=flags)
            record.turns.append(turn)
            history.append({"speaker": ag.person_id, "public_text": text, "stage": stage})
            _emit(on_event, "turn", turn.model_dump())
            _emit(on_event, "chemistry", {"idx": idx, "speaker": ag.person_id, "chemistry": turn.chemistry})
            for f in flags:
                _emit(on_event, "flag", {"idx": idx, **f})
            idx += 1
            # early exit: chemistry dead for the last 3 turns (or the speaker says so) -> one polite close
            if stage != "close" and idx >= MIN_TURNS_BEFORE_EXIT:
                recent = [t.chemistry for t in record.turns[-3:]]
                if all(c <= DEAD_CHEM for c in recent) or (plan["end_date"] and ag.chemistry <= DEAD_CHEM):
                    schedule = schedule[:idx] + ["close"]
                    total = len(schedule)
        record.score_a = agent_a.rate(history, names, id_b, names[id_b])
        record.score_b = agent_b.rate(history, names, id_a, names[id_a])
        record.status = "done"
    except Exception:
        log.exception("date %s failed", record.id)
        record.status = "failed"
    _emit(on_event, "done", {"date_id": record.id, "status": record.status, "turns": len(record.turns),
                             "score_a": record.score_a.model_dump() if record.score_a else None,
                             "score_b": record.score_b.model_dump() if record.score_b else None,
                             "faithfulness_a": record.faithfulness_a, "faithfulness_b": record.faithfulness_b,
                             "flagged_turns": record.flagged_turns})
    return record


def apply_referee(record: DateRecord, profile_a: Profile, profile_b: Profile, client=None) -> DateRecord:
    """Run agent B's referee and write faithfulness + flagged turns onto the record (no-op if referee absent)."""
    try:
        from agents.referee import apply_referee as _apply, referee
    except ImportError:
        return record
    client = client or default_client()
    return _apply(record, referee(record, profile_a, profile_b, client))
