"""Read-side views over stored dates: rankings, pool matrix + stable pairs, briefings, 'ask my agent why'."""
from __future__ import annotations

from typing import Optional

from db.store import get_store

from . import adapters


def _names() -> dict[str, str]:
    return {p["id"]: (p.get("display_name") or p["id"]) for p in get_store().list_people()}


def rankings_for(person_id: str, top_n: Optional[int] = None, weights=None) -> list[dict]:
    from ranking import rank_for_person

    dates = [d for d in get_store().list_dates(person_id) if d["status"] == "done"]
    names = _names()
    date_ids = {}
    for d in dates:
        if d.get("kind", "standard") == "standard":
            other = d["person_b"] if d["person_a"] == person_id else d["person_a"]
            date_ids[other] = d["id"]
    rows = rank_for_person(person_id, dates, weights=weights, top_n=top_n)
    for r in rows:
        r["display_name"] = names.get(r["person_id"], r["person_id"])
        r["date_id"] = date_ids.get(r["person_id"])
    return rows


def pool_matrix() -> dict:
    from ranking import build_matrix, gale_shapley, mark_mutual_first

    store = get_store()
    dates = [d for d in store.list_dates() if d["status"] == "done"]
    in_dates = {d["person_a"] for d in dates} | {d["person_b"] for d in dates}
    people = [p for p in store.list_people() if p["id"] in in_dates]
    order = [p["id"] for p in people]
    matrix, mutual = build_matrix(dates, order)
    gs = gale_shapley(matrix, order) if len(order) >= 2 else {"pairs": [], "unmatched": None, "stable": True,
                                                              "blocking_pairs": [], "method": "irving"}
    return {
        "order": order,
        "names": {p["id"]: p.get("display_name") or p["id"] for p in people},
        "matrix": matrix,
        "mutual": mutual,
        "stable_pairs": [list(p) for p in gs["pairs"]],
        "pairs": mark_mutual_first(gs["pairs"], matrix, order) if order else [],
        "unmatched": gs["unmatched"],
        "stable": gs["stable"],
    }


def build_briefing(person_id: str) -> dict:
    """Agent B's make_briefing when present, else a deterministic summary of the rankings."""
    store = get_store()
    rows = rankings_for(person_id)
    profile = store.get_profile(person_id)
    made = adapters.make_briefing(person_id, profile=profile, rankings=rows, dates=store.list_dates(person_id),
                                  names=_names())
    if isinstance(made, dict) and {"introduce", "warn", "unsure"} <= set(made):
        return made
    introduce = [{"person_id": r["person_id"], "reason": r["explanation"] or f"Pair score {r['pair_score']:.1f}"}
                 for r in rows if r["would_meet_again"]][:3]
    warn = [{"person_id": r["person_id"], "reason": f"Low mutual fit ({r['pair_score']:.1f}/10)."}
            for r in reversed(rows) if r["pair_score"] < 5 and not r["would_meet_again"]][:2]
    unsure = []
    for s, st in ((profile or {}).get("source_status") or {}).items():
        if st != "ok":
            unsure.append(f"Your {s} source was {st.replace('_', ' ')}, so some profile fields are low confidence.")
    return {"introduce": introduce, "warn": warn, "unsure": unsure}


def ask_why(person_id: str, question: str) -> str:
    store = get_store()
    rows = rankings_for(person_id)
    names = _names()
    ans = adapters.answer_why(person_id, question, profile=store.get_profile(person_id), rankings=rows,
                              dates=store.list_dates(person_id), briefing=store.get_briefing(person_id), names=names)
    if ans:
        return ans
    q = question.lower()
    target = next((r for r in rows if names.get(r["person_id"], "").lower() in q or r["person_id"].lower() in q), None)
    if target is None:
        target = rows[0] if rows else None
    if target is None:
        return "I have no completed dates to explain yet."
    n = names.get(target["person_id"], target["person_id"])
    return (f"{n}: mutual fit {target['pair_score']:.1f}/10 (I gave {target['score_given']:.1f}, "
            f"they gave me {target['score_received']:.1f}). {target['explanation']}").strip()
