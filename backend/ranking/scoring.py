"""Mutual-fit scoring, per-person rankings and best-moment explanations.

Pure functions, no I/O. Rankings use compatibility rubric dimensions only; no
profile attribute (sensitive or otherwise) is ever read here.

RE-WEIGHT SEMANTICS (the frontend replicates this exactly, client-side):
    weights: {dimension: non-negative number}, one per entry of DIMENSIONS.
    normalised w_d = max(w_d, 0) / sum(max(w, 0)); missing dimension = 0;
    if the sum is 0 (all sliders at zero) fall back to equal weights.
    directional(i->j) = sum_d w_d * rubric_i_of_j[d]            (0-10)
    pair(i,j)         = 2*a*b/(a+b) with a=directional(i->j), b=directional(j->i);
                        0 if either is <= 0.
    Sorting: pair desc, then person_id asc. Per-dimension scores are stored in
    each ranking row ("dimension_scores" = what I gave them, "dimension_scores_received"
    = what they gave me) so sliders re-sort without calling the backend.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

from common.models import DIMENSIONS

Weights = Optional[Mapping[str, float]]


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def normalise_weights(weights: Weights = None) -> dict[str, float]:
    """Weights summing to 1 over DIMENSIONS; equal if None / all zero / invalid."""
    equal = {d: 1.0 / len(DIMENSIONS) for d in DIMENSIONS}
    if not weights:
        return equal
    raw = {}
    for d in DIMENSIONS:
        try:
            w = float(weights.get(d, 0.0))
        except (TypeError, ValueError):
            w = 0.0
        raw[d] = w if w > 0 and w == w and w != float("inf") else 0.0
    total = sum(raw.values())
    if total <= 0:
        return equal
    return {d: w / total for d, w in raw.items()}


def dimension_scores(rubric: Any) -> dict[str, float]:
    return {d: float(_get(rubric, d)) for d in DIMENSIONS}


def directional_score(rubric: Any, weights: Weights = None) -> float:
    """Weighted mean (0-10) of the 5 dimensions of one rater's rubric."""
    w = normalise_weights(weights)
    return sum(w[d] * float(_get(rubric, d)) for d in DIMENSIONS)


def pair_score(a_to_b: Optional[float], b_to_a: Optional[float]) -> Optional[float]:
    """Harmonic mean of the two directional scores; 0 if either is <= 0; None if missing."""
    if a_to_b is None or b_to_a is None:
        return None
    if a_to_b <= 0 or b_to_a <= 0:
        return 0.0
    return 2.0 * a_to_b * b_to_a / (a_to_b + b_to_a)


def _rubrics_by_direction(dates: Iterable[Any], kind: Optional[str]) -> dict[tuple[str, str], list[Any]]:
    """(rater, ratee) -> rubrics. Failed/unscored dates skipped; kind filter optional."""
    out: dict[tuple[str, str], list[Any]] = {}
    for d in dates:
        if kind is not None and _get(d, "kind", "standard") != kind:
            continue
        if _get(d, "status", "done") == "failed":
            continue
        a, b = _get(d, "person_a"), _get(d, "person_b")
        sa, sb = _get(d, "score_a"), _get(d, "score_b")
        if sa is not None:
            out.setdefault((a, b), []).append(sa)
        if sb is not None:
            out.setdefault((b, a), []).append(sb)
    return out


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def build_matrix(dates: Iterable[Any], order: Sequence[str], weights: Weights = None,
                 kind: Optional[str] = "standard"):
    """Return (matrix, mutual).

    matrix[i][j] = directional score person order[i] gives order[j] (None on the
    diagonal or when no scored date exists). mutual[i][j] = pair_score (symmetric,
    same None rules). Several dates for one direction are averaged. `kind`
    restricts to standard dates by default (scenario dates are extras); None = all.
    """
    rub = _rubrics_by_direction(dates, kind)
    n = len(order)
    matrix: list[list[Optional[float]]] = [[None] * n for _ in range(n)]
    for i, a in enumerate(order):
        for j, b in enumerate(order):
            if i != j and (a, b) in rub:
                matrix[i][j] = _mean([directional_score(r, weights) for r in rub[(a, b)]])
    mutual: list[list[Optional[float]]] = [[None] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                mutual[i][j] = pair_score(matrix[i][j], matrix[j][i])
    return matrix, mutual


def _avg_dims(rubrics: Sequence[Any]) -> dict[str, float]:
    return {d: _mean([float(_get(r, d)) for r in rubrics]) for d in DIMENSIONS}


def _truncate(text: str, limit: int = 200) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def best_moment(date: Any) -> Optional[dict]:
    """Turn with the biggest chemistry jump (chem[k] - chem[k-1]); ties -> earliest.

    Returns {idx, speaker, stage, quote, jump, chemistry_before, chemistry_after,
    explanation} or None if the date has no turns. `quote` is the PUBLIC line only
    (private notes are never surfaced). `explanation` is exactly two lines. With a
    single turn the jump is measured from a neutral 5.0 baseline.
    """
    turns = sorted(_get(date, "turns", []) or [], key=lambda t: _get(t, "idx", 0))
    if not turns:
        return None
    best = None
    prev = 5.0 if len(turns) == 1 else None
    for t in turns:
        c = float(_get(t, "chemistry", 0.0))
        if prev is not None:
            jump = c - prev
            if best is None or jump > best[0]:
                best = (jump, t, prev, c)
        prev = c
    if best is None:  # defensive; unreachable for >=2 turns
        return None
    jump, t, before, after = best
    quote = _truncate(_get(t, "public_text", ""))
    stage = str(_get(t, "stage", "")).replace("_", " ")
    line1 = f'Best moment ({stage}): "{quote}"'
    line2 = f"Chemistry moved from {before:.1f} to {after:.1f} ({jump:+.1f}) at turn {_get(t, 'idx')}."
    return {"idx": _get(t, "idx"), "speaker": _get(t, "speaker"), "stage": _get(t, "stage"),
            "quote": quote, "jump": jump, "chemistry_before": before, "chemistry_after": after,
            "explanation": line1 + "\n" + line2}


def rank_for_person(person_id: str, dates: Iterable[Any], weights: Weights = None,
                    top_n: Optional[int] = None, kind: Optional[str] = "standard") -> list[dict]:
    """Ranked matches for one person, best first.

    Row: {person_id, pair_score, score_given (me->them), score_received (them->me),
    dimension_scores (what I gave them), dimension_scores_received, would_meet_again
    (both said yes), would_meet_again_me, would_meet_again_them, best_moment,
    explanation}. Only people with a scored date in BOTH directions are ranked.
    Sorted by pair_score desc then person_id asc.
    """
    dates = list(dates)
    rub = _rubrics_by_direction(dates, kind)
    others = sorted({b for (a, b) in rub if a == person_id} & {a for (a, b) in rub if b == person_id})
    rows = []
    for o in others:
        mine, theirs = rub[(person_id, o)], rub[(o, person_id)]
        given = _mean([directional_score(r, weights) for r in mine])
        received = _mean([directional_score(r, weights) for r in theirs])
        me_again = all(bool(_get(r, "would_meet_again", False)) for r in mine)
        them_again = all(bool(_get(r, "would_meet_again", False)) for r in theirs)
        pair_dates = [d for d in dates
                      if {_get(d, "person_a"), _get(d, "person_b")} == {person_id, o}
                      and (kind is None or _get(d, "kind", "standard") == kind)]
        moment = None
        for d in pair_dates:
            m = best_moment(d)
            if m and (moment is None or m["jump"] > moment["jump"]):
                moment = m
        rows.append({
            "person_id": o,
            "pair_score": pair_score(given, received),
            "score_given": given,
            "score_received": received,
            "dimension_scores": _avg_dims(mine),
            "dimension_scores_received": _avg_dims(theirs),
            "would_meet_again": me_again and them_again,
            "would_meet_again_me": me_again,
            "would_meet_again_them": them_again,
            "best_moment": moment,
            "explanation": moment["explanation"] if moment else "",
        })
    rows.sort(key=lambda r: (-r["pair_score"], r["person_id"]))
    return rows[:top_n] if top_n is not None else rows
