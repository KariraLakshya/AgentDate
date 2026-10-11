"""Run the full round-robin (C(25,2)=300 dates) in mock mode and write data/demo/demo.json.

    cd backend && python -m scripts.round_robin [--out ../data/demo/demo.json] [--workers 8] [--fake]

--fake uses generated profiles (tests only) instead of agent B's personas + analyst.
"""
from __future__ import annotations

import argparse
import itertools
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from common.models import Briefing, DateRecord, DemoBundle, PersonSummary, Profile  # noqa: E402

log = logging.getLogger("round_robin")
PRIVATE_NOTE_MAX = 200


# ------------------------------------------------------------------ people
def _fixtures() -> list:
    try:
        from agents.personas_loader import load_personas

        return list(load_personas())
    except ImportError:
        out = []
        for p in sorted((ROOT / "data" / "personas").glob("p*.json")):
            out.append(json.loads(p.read_text(encoding="utf-8")))
        return out


def _fget(f, k, default=None):
    return f.get(k, default) if isinstance(f, dict) else getattr(f, k, default)


def load_people(client, fake: bool = False):
    """-> list[(id, display_name, synthetic, Profile)]"""
    if fake:
        from agents.tests_dating.fakes import make_pool

        return [(i, n, True, p) for i, n, p in make_pool(25)]
    from agents.analyst import analyze

    out = []
    for f in _fixtures():
        prof = analyze(f, client=client)
        if not isinstance(prof, Profile):
            prof = Profile.model_validate(prof)
        out.append((_fget(f, "id"), _fget(f, "display_name"), bool(_fget(f, "synthetic", True)), prof))
    return out


# ------------------------------------------------------------------ dates
def _one_date(pa, pb, ids, client, names, kind="standard", referee=True) -> DateRecord:
    from agents.dating import apply_referee, run_date

    rec = run_date(pa, pb, ids, client=client, kind=kind, names=names)
    if referee and rec.status == "done":
        rec = apply_referee(rec, pa, pb, client)
    return compact(rec)


def run_all_dates(people, client, workers: int = 8, referee: bool = True) -> list[DateRecord]:
    names = {i: n for i, n, _, _ in people}
    profs = {i: p for i, _, _, p in people}
    pairs = list(itertools.combinations([i for i, _, _, _ in people], 2))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda ab: _one_date(profs[ab[0]], profs[ab[1]], ab, client, names, referee=referee), pairs))


def compact(rec: DateRecord) -> DateRecord:
    for t in rec.turns:
        if len(t.private_note) > PRIVATE_NOTE_MAX:
            t.private_note = t.private_note[: PRIVATE_NOTE_MAX - 1].rstrip() + "..."
    return rec


# ------------------------------------------------------------------ briefings
def _local_briefing(pid, dates, profiles) -> Briefing:
    from ranking import rank_for_person

    rows = rank_for_person(pid, dates)
    best = [r for r in rows if r["would_meet_again"]][:3] or rows[:3]
    introduce = [{"person_id": r["person_id"],
                  "reason": f"Mutual fit {r['pair_score']:.1f}/10. " + (r["best_moment"]["quote"] if r["best_moment"] else "")}
                 for r in best]
    worst = sorted(rows, key=lambda r: r["pair_score"])[:2]
    warn = [{"person_id": r["person_id"],
             "reason": f"Mutual fit only {r['pair_score']:.1f}/10; lowest dimension: "
                       f"{min(r['dimension_scores'], key=r['dimension_scores'].get).replace('_', ' ')}."} for r in worst]
    p = profiles[pid]
    unsure = []
    if p.persona_gap.score >= 0.4:
        unsure.append(f"Your public and off-duty selves differ ({p.persona_gap.description}); I may have weighted one too heavily.")
    for src, st in p.source_status.items():
        if st != "ok":
            unsure.append(f"Your {src} was {st.replace('_', ' ')}, so some traits are low confidence.")
    low = [c.value for c in p.values + p.needs if c.confidence < 0.5]
    if low:
        unsure.append("I was unsure about: " + ", ".join(low[:3]) + ".")
    return Briefing(introduce=introduce, warn=warn,
                    unsure=unsure or ["I was fairly confident, but I only know what your two public profiles say."])


def _briefing_rows(pid, dates, names) -> list[dict]:
    """Rankings in the shape agent B's make_briefing expects."""
    from ranking import rank_for_person

    rows = []
    for r in rank_for_person(pid, dates):
        low = min(r["dimension_scores"], key=r["dimension_scores"].get).replace("_", " ")
        rows.append({"person_id": r["person_id"], "name": names.get(r["person_id"]), "score": r["pair_score"],
                     "best_moment": r["best_moment"]["quote"] if r["best_moment"] else None,
                     "friction": f"weakest area was {low}", "would_meet_again": r["would_meet_again"]})
    return rows


def make_briefings(dates, order, names, profiles, client) -> dict[str, Briefing]:
    try:
        from agents.briefing import make_briefing  # agent B
    except ImportError:
        make_briefing = None
    out = {}
    for pid in order:
        b = None
        if make_briefing:
            try:
                b = make_briefing(pid, _briefing_rows(pid, dates, names), profiles[pid], names, client)
            except Exception as e:
                log.warning("make_briefing failed for %s (%s); using local fallback", pid, e)
        out[pid] = b or _local_briefing(pid, dates, profiles)
    return out


# ------------------------------------------------------------------ main
def build_bundle(people, client, workers=8, scenarios=3, referee=True) -> DemoBundle:
    from ranking import best_moment, build_matrix, gale_shapley

    order = [i for i, _, _, _ in people]
    names = {i: n for i, n, _, _ in people}
    profs = {i: p for i, _, _, p in people}
    dates = run_all_dates(people, client, workers, referee)
    matrix, mutual = build_matrix(dates, order)
    stable = gale_shapley(matrix, order)
    n = len(order)
    cand = sorted(((mutual[i][j], i, j) for i in range(n) for j in range(i + 1, n) if mutual[i][j] is not None), reverse=True)
    std_dates = list(dates)
    for _, i, j in cand[:scenarios]:
        a, b = order[i], order[j]
        dates.append(_one_date(profs[a], profs[b], (a, b), client, names, kind="scenario", referee=referee))
    moments = {}
    for d in std_dates:
        m = best_moment(d)
        if m:
            moments[f"{d.person_a}|{d.person_b}"] = m["quote"]
            moments[f"{d.person_b}|{d.person_a}"] = m["quote"]
    return DemoBundle(
        people=[PersonSummary(id=i, display_name=nm, synthetic=s, profile=p) for i, nm, s, p in people],
        dates=dates,
        matrix=[[None if v is None else round(v, 3) for v in row] for row in matrix],
        order=order,
        stable_pairs=[tuple(p) for p in stable["pairs"]],
        briefings=make_briefings(std_dates, order, names, profs, client),
        best_moments=moments,
    )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "demo" / "demo.json"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--fake", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    from common import config

    if not config.ANTHROPIC_API_KEY:
        config.LLM_MODE = "mock"
    from agents.dating import default_client

    client = default_client()
    t0 = time.time()
    people = load_people(client, fake=args.fake)
    bundle = build_bundle(people, client, args.workers)
    DemoBundle.model_validate(bundle.model_dump())  # explicit validation
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bundle.model_dump_json(), encoding="utf-8")
    std = sum(1 for d in bundle.dates if d.kind == "standard")
    log.info("wrote %s: %d people, %d standard + %d scenario dates, %.2f MB, %.1fs", out, len(bundle.people), std,
             len(bundle.dates) - std, out.stat().st_size / 1e6, time.time() - t0)


if __name__ == "__main__":
    main()
