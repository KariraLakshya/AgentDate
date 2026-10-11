import itertools
import random

import pytest

from common.models import DIMENSIONS, DateRecord, DateTurn, Rubric
from ranking import (best_moment, blocking_pairs, build_matrix, directional_score, gale_shapley,
                     mark_mutual_first, mutual_first_choices, pair_score, rank_for_person)


def rub(vals, again=True):
    if isinstance(vals, (int, float)):
        vals = [vals] * 5
    return Rubric(**dict(zip(DIMENSIONS, vals)), would_meet_again=again, verdict="v")


def mk_date(a, b, sa, sb, turns=(), kind="standard", did=None):
    return DateRecord(id=did or f"{a}-{b}", person_a=a, person_b=b, kind=kind, status="done",
                      turns=list(turns), score_a=sa, score_b=sb)


def turn(idx, chem, text="hi", stage="opening", speaker="a"):
    return DateTurn(idx=idx, speaker=speaker, stage=stage, public_text=text, private_note="SECRET", chemistry=chem)


# ---- directional / pair ----
def test_directional_default_equal_weights():
    assert directional_score(rub([2, 4, 6, 8, 10])) == pytest.approx(6.0)
    assert directional_score({d: 3 for d in DIMENSIONS}) == pytest.approx(3.0)  # dict rubric ok


def test_directional_weights_normalised_and_zero_sum():
    r = rub([10, 0, 0, 0, 0])
    assert directional_score(r, {"interest_overlap": 5}) == pytest.approx(10)
    assert directional_score(r, {"interest_overlap": 1, "values_alignment": 1}) == pytest.approx(5)
    assert directional_score(r, {d: 0 for d in DIMENSIONS}) == pytest.approx(2.0)  # fallback equal
    assert directional_score(r, {}) == pytest.approx(2.0)
    assert directional_score(r, {"interest_overlap": -3, "values_alignment": 1}) == pytest.approx(0)


def test_pair_score_harmonic_less_than_arithmetic():
    assert pair_score(9, 3) == pytest.approx(4.5) and 4.5 < 6
    assert pair_score(7, 7) == pytest.approx(7)
    for a, b in [(10, 1), (8, 6), (2.5, 9)]:
        assert pair_score(a, b) < (a + b) / 2


def test_pair_score_zeros_and_missing():
    assert pair_score(0, 5) == 0.0 and pair_score(0, 0) == 0.0
    assert pair_score(None, 5) is None


# ---- matrix ----
def test_build_matrix_directions_diag_missing():
    d = [mk_date("a", "b", rub(8), rub(4)), mk_date("a", "c", rub(6), None)]
    m, mu = build_matrix(d, ["a", "b", "c"])
    assert (m[0][1], m[1][0], m[0][2]) == pytest.approx((8, 4, 6))
    assert m[2][0] is None and m[1][2] is None
    assert all(m[i][i] is None and mu[i][i] is None for i in range(3))
    assert mu[0][1] == mu[1][0] == pytest.approx(pair_score(8, 4))
    assert mu[0][2] is None


def test_build_matrix_ignores_scenario():
    d = [mk_date("a", "b", rub(8), rub(8)), mk_date("a", "b", rub(0), rub(0), kind="scenario", did="s")]
    m, _ = build_matrix(d, ["a", "b"])
    assert m[0][1] == 8


# ---- weights change order ----
def _weights_pool():
    hi_int = [10, 5, 5, 5, 5]
    hi_life = [5, 5, 5, 10, 5]
    return [mk_date("a", "b", rub(hi_int), rub(hi_int)), mk_date("a", "c", rub(hi_life), rub(hi_life))]


def test_weights_change_order():
    d = _weights_pool()
    r_int = rank_for_person("a", d, {"interest_overlap": 1})
    r_life = rank_for_person("a", d, {"lifestyle_fit": 1})
    assert [x["person_id"] for x in r_int] == ["b", "c"]
    assert [x["person_id"] for x in r_life] == ["c", "b"]
    eq = rank_for_person("a", d)  # tie -> person_id asc, deterministic
    assert [x["person_id"] for x in eq] == ["b", "c"]


def test_rank_for_person_fields_sort_topn():
    d = [mk_date("a", "b", rub(9), rub(3), [turn(0, 4), turn(1, 8, "great!")]),
         mk_date("a", "c", rub(6), rub(6), [turn(0, 5), turn(1, 5)]),
         mk_date("b", "c", rub(5), rub(5))]
    rows = rank_for_person("a", d)
    assert [r["person_id"] for r in rows] == ["c", "b"]  # 6.0 > harmonic(9,3)=4.5
    b = rows[1]
    assert b["pair_score"] == pytest.approx(4.5)
    assert (b["score_given"], b["score_received"]) == pytest.approx((9, 3))
    assert set(b["dimension_scores"]) == set(DIMENSIONS)
    assert set(b["dimension_scores_received"]) == set(DIMENSIONS)
    assert b["would_meet_again"] is True
    assert b["best_moment"]["quote"] == "great!"
    assert len(b["explanation"].split("\n")) == 2
    assert len(rank_for_person("a", d, top_n=1)) == 1
    assert {r["person_id"] for r in rank_for_person("c", d)} == {"a", "b"}


def test_would_meet_again_needs_both():
    d = [mk_date("a", "b", rub(7, True), rub(7, False))]
    r = rank_for_person("a", d)[0]
    assert r["would_meet_again"] is False and r["would_meet_again_me"] and not r["would_meet_again_them"]


def test_one_sided_not_ranked():
    assert rank_for_person("a", [mk_date("a", "b", rub(7), None)]) == []


# ---- best moment ----
def test_best_moment_picks_largest_jump_and_hides_private():
    t = [turn(0, 5, "hello"), turn(1, 6, "ok"), turn(2, 9, "We both love night markets!", "shared_interests"),
         turn(3, 8, "later"), turn(4, 3, "ugh", "friction")]
    m = best_moment(mk_date("a", "b", rub(5), rub(5), t))
    assert m["idx"] == 2 and m["jump"] == pytest.approx(3)
    assert m["quote"] == "We both love night markets!"
    lines = m["explanation"].split("\n")
    assert len(lines) == 2 and '"We both love night markets!"' in lines[0] and "6.0 to 9.0" in lines[1]
    assert "SECRET" not in m["explanation"]


def test_best_moment_edge_cases():
    assert best_moment(mk_date("a", "b", None, None)) is None
    m = best_moment(mk_date("a", "b", None, None, [turn(0, 8, "x" * 500)]))
    assert m["idx"] == 0 and len(m["quote"]) <= 200
    flat = best_moment(mk_date("a", "b", None, None, [turn(0, 5), turn(1, 5), turn(2, 5)]))
    assert flat["idx"] == 1  # earliest tie; first turn has no predecessor


# ---- stable matching ----
def rand_matrix(n, rng, symmetric=0.0):
    q = [[rng.random() for _ in range(n)] for _ in range(n)]
    return [[None if i == j else 10 * ((1 - symmetric) * q[i][j] + symmetric * (q[i][j] + q[j][i]) / 2)
             for j in range(n)] for i in range(n)]


def assert_no_blocking(m, order, res):
    """Independent brute-force stability check (does not use ranking.blocking_pairs)."""
    pos = {p: i for i, p in enumerate(order)}
    partner = {}
    for a, b in res["pairs"]:
        partner[a], partner[b] = b, a
    assert len(partner) == 2 * len(res["pairs"])  # nobody matched twice
    if len(order) % 2:
        assert res["unmatched"] is not None and res["unmatched"] not in partner
    else:
        assert res["unmatched"] is None
    assert len(partner) + (1 if res["unmatched"] else 0) == len(order)

    def better(i, j, cur):
        if cur is None:
            return True
        sj, sc = m[i][pos[j]], m[i][pos[cur]]

        def key(s, k):
            return (s is None, -(s or 0), k)
        return key(sj, pos[j]) < key(sc, pos[cur])

    for x, y in itertools.combinations(order, 2):
        if partner.get(x) == y:
            continue
        assert not (better(pos[x], y, partner.get(x)) and better(pos[y], x, partner.get(y))), (x, y)


@pytest.mark.parametrize("seed", range(25))
def test_stability_25_person_symmetric_always_stable(seed):
    rng = random.Random(seed)
    n = 25
    base = rand_matrix(n, rng, symmetric=1.0)  # symmetric distinct scores: a stable matching exists
    order = [f"p{i}" for i in range(n)]
    res = gale_shapley(base, order)
    assert res["stable"] and res["method"] == "irving" and res["blocking_pairs"] == []
    assert len(res["pairs"]) == 12 and res["unmatched"] is not None
    assert_no_blocking(base, order, res)
    assert res == gale_shapley(base, order)  # deterministic


@pytest.mark.parametrize("seed", range(25))
def test_stability_noisy_flag_is_truthful(seed):
    rng = random.Random(1000 + seed)
    for n, sym in [(24, 0.7), (25, 0.5), (25, 0.0), (10, 0.0)]:
        m = rand_matrix(n, rng, sym)
        order = [f"p{i}" for i in range(n)]
        res = gale_shapley(m, order)
        assert res["stable"] == (blocking_pairs(m, order, res["pairs"]) == [])
        if res["stable"]:
            assert_no_blocking(m, order, res)
        else:
            assert res["method"] == "greedy_fallback" and res["blocking_pairs"]


def test_many_correlated_instances_mostly_solved_by_irving():
    rng = random.Random(7)
    found = sum(gale_shapley(rand_matrix(25, rng, 0.7))["method"] == "irving" for _ in range(30))
    assert found >= 20


def test_known_unsolvable_roommates_flagged():
    # classic 4-person instance with no stable roommates matching
    m = [[None, 3, 2, 1], [2, None, 3, 1], [3, 2, None, 1], [3, 2, 1, None]]
    res = gale_shapley(m, list("abcd"))
    assert res["method"] == "greedy_fallback" and res["stable"] is False and res["blocking_pairs"]


def test_odd_and_tiny():
    assert gale_shapley([], []) == {"pairs": [], "unmatched": None, "stable": True,
                                    "blocking_pairs": [], "method": "irving"}
    assert gale_shapley([[None]], ["a"])["unmatched"] == "a"
    two = gale_shapley([[None, 5], [1, None]], ["a", "b"])
    assert two["pairs"] == [("a", "b")] and two["unmatched"] is None and two["stable"]
    three = gale_shapley([[None, 9, 1], [9, None, 1], [1, 1, None]], ["a", "b", "c"])
    assert three["pairs"] == [("a", "b")] and three["unmatched"] == "c" and three["stable"]


def test_tie_break_deterministic_by_order():
    m = [[None, 5, 5, 5], [5, None, 5, 5], [5, 5, None, 5], [5, 5, 5, None]]
    res = gale_shapley(m, list("abcd"))
    assert res == gale_shapley(m, list("abcd"))
    assert res["stable"]


def test_missing_scores_rank_last():
    m = [[None, None, 5], [None, None, 5], [5, 5, None]]
    res = gale_shapley(m, ["a", "b", "c"])
    assert res["unmatched"] in {"a", "b"} and res["stable"]


def test_mutual_first_marking():
    m = [[None, 9, 1, 1], [9, None, 1, 1], [1, 1, None, 8], [2, 1, 3, None]]
    order = list("abcd")
    assert mutual_first_choices(m, order) == [("a", "b"), ("c", "d")]
    res = gale_shapley(m, order)
    marked = mark_mutual_first(res["pairs"], m, order)
    assert len(marked) == 2 and all(x["mutual_first"] for x in marked)
    m2 = [[None, 9, 8], [1, None, 9], [8, 9, None]]  # b and c pick each other; a picks b
    assert mutual_first_choices(m2, ["a", "b", "c"]) == [("b", "c")]
    assert mark_mutual_first([("a", "b")], m2, ["a", "b", "c"])[0]["mutual_first"] is False


def test_end_to_end_matrix_to_matching():
    rng = random.Random(3)
    ids = [f"p{i}" for i in range(6)]
    dates = [mk_date(a, b, rub(rng.uniform(1, 10)), rub(rng.uniform(1, 10)))
             for a, b in itertools.combinations(ids, 2)]
    m, _ = build_matrix(dates, ids)
    res = gale_shapley(m, ids)
    assert res["stable"] == (blocking_pairs(m, ids, res["pairs"]) == [])
