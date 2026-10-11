"""Stable matching over directional scores (Gale-Shapley family, single pool).

The pool is one set of people, so the proposal/rejection scheme is Irving's
stable-roommates generalisation of Gale-Shapley (phase 1 = proposals, phase 2 =
rotation elimination). Preferences: higher directional score first, ties broken
by position in `order` (deterministic); a missing score ranks below any score.
Odd N: a dummy "unmatched" slot every person ranks last is added; whoever pairs
with it is returned as `unmatched`.

A stable roommates matching does not always exist for arbitrary preferences. If
none does, `stable` is False and a deterministic fallback (greedy by harmonic
pair score) is returned together with its blocking pairs; callers must check.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .scoring import pair_score

_DUMMY = -1  # index of the unmatched slot


def _prefs(matrix: Sequence[Sequence[Optional[float]]], n: int) -> list[list[int]]:
    prefs = []
    for i in range(n):
        others = [j for j in range(n) if j != i]
        others.sort(key=lambda j: (matrix[i][j] is None, -(matrix[i][j] or 0.0), j))
        prefs.append(others)
    return prefs


def _irving(prefs: list[list[int]]) -> Optional[list[int]]:
    """Irving's algorithm on complete lists, even size. Returns partner[] or None."""
    n = len(prefs)
    rank = [{j: r for r, j in enumerate(p)} for p in prefs]
    holds: dict[int, int] = {}
    idx = [0] * n
    free = list(range(n))
    while free:
        i = free.pop(0)
        while True:
            if idx[i] >= len(prefs[i]):
                return None
            j = prefs[i][idx[i]]
            idx[i] += 1
            cur = holds.get(j)
            if cur is None or rank[j][i] < rank[j][cur]:
                holds[j] = i
                if cur is not None:
                    free.append(cur)
                break
    lists = [list(p) for p in prefs]

    def truncate_after(j: int, keep: int) -> None:
        pos = lists[j].index(keep)
        for x in lists[j][pos + 1:]:
            lists[x].remove(j)
        del lists[j][pos + 1:]

    for j, h in holds.items():
        truncate_after(j, h)
    if any(not l for l in lists):
        return None
    while True:
        start = next((i for i in range(n) if len(lists[i]) > 1), None)
        if start is None:
            break
        xs, seen = [], {}
        x = start
        while x not in seen:
            seen[x] = len(xs)
            xs.append(x)
            y = lists[x][1]
            x = lists[y][-1]
        cycle = xs[seen[x]:]
        ys = [lists[c][1] for c in cycle]
        removals = set()  # computed from one snapshot, applied together
        for c, y in zip(cycle, ys):
            pos = lists[y].index(c)
            removals.update((y, z) for z in lists[y][pos + 1:])
        for y, z in removals:
            if z in lists[y]:
                lists[y].remove(z)
            if y in lists[z]:
                lists[z].remove(y)
        if any(not l for l in lists):
            return None
    return [lists[i][0] for i in range(n)]


def blocking_pairs(matrix: Sequence[Sequence[Optional[float]]], order: Sequence[str],
                   pairs: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """Pairs (i, j) not matched together where each prefers the other to their current
    partner (being unmatched is worse than any partner). Same preference rule as matching."""
    n = len(order)
    pos = {p: k for k, p in enumerate(order)}
    prefs = _prefs(matrix, n)
    rank = [{j: r for r, j in enumerate(p)} for p in prefs]
    partner: dict[int, int] = {}
    for a, b in pairs:
        partner[pos[a]], partner[pos[b]] = pos[b], pos[a]

    def prefers(i: int, j: int) -> bool:
        return i not in partner or rank[i][j] < rank[i][partner[i]]

    return [(order[i], order[j]) for i in range(n) for j in range(i + 1, n)
            if partner.get(i) != j and prefers(i, j) and prefers(j, i)]


def gale_shapley(prefs_scores: Sequence[Sequence[Optional[float]]], order: Optional[Sequence[str]] = None) -> dict:
    """Stable pairing from the directional matrix (matrix[i][j] = score i gives j).

    Returns {pairs: [(a, b)] (ordered by pool position, sorted), unmatched: id|None,
    stable: bool, blocking_pairs: [...], method: "irving"|"greedy_fallback"}.
    `order` defaults to "0","1",... .
    """
    n = len(prefs_scores)
    order = list(order) if order is not None else [str(i) for i in range(n)]
    if n < 2:
        return {"pairs": [], "unmatched": order[0] if n else None, "stable": True,
                "blocking_pairs": [], "method": "irving"}
    base = _prefs(prefs_scores, n)
    odd = n % 2 == 1
    if odd:  # dummy index n, ranked last by everyone; its own list is by position
        prefs = [p + [n] for p in base] + [list(range(n))]
    else:
        prefs = base
    partner = _irving(prefs)
    method = "irving"
    if partner is None:
        method = "greedy_fallback"
        edges = []
        for i in range(n):
            for j in range(i + 1, n):
                ps = pair_score(prefs_scores[i][j], prefs_scores[j][i])
                edges.append((-(ps or 0.0), i, j))
        edges.sort()
        partner = [_DUMMY] * (n + (1 if odd else 0))
        for _, i, j in edges:
            if partner[i] == _DUMMY and partner[j] == _DUMMY:
                partner[i], partner[j] = j, i
    pairs, unmatched = [], None
    for i in range(n):
        j = partner[i]
        if j == _DUMMY or j == n:
            unmatched = order[i]
        elif i < j:
            pairs.append((order[i], order[j]))
    bp = blocking_pairs(prefs_scores, order, pairs)
    return {"pairs": pairs, "unmatched": unmatched, "stable": not bp,
            "blocking_pairs": bp, "method": method}


def mutual_first_choices(prefs_scores: Sequence[Sequence[Optional[float]]],
                         order: Optional[Sequence[str]] = None) -> list[tuple[str, str]]:
    """Pairs where each is the other's top-scored choice (ties -> lowest position)."""
    n = len(prefs_scores)
    order = list(order) if order is not None else [str(i) for i in range(n)]
    prefs = _prefs(prefs_scores, n)
    tops = [p[0] if p else None for p in prefs]
    return [(order[i], order[tops[i]]) for i in range(n)
            if tops[i] is not None and tops[i] > i and tops[tops[i]] == i
            and prefs_scores[i][tops[i]] is not None and prefs_scores[tops[i]][i] is not None]


def mark_mutual_first(pairs: Sequence[tuple[str, str]], prefs_scores, order=None) -> list[dict]:
    """Annotate stable pairs: [{a, b, mutual_first: bool}]."""
    firsts = {frozenset(p) for p in mutual_first_choices(prefs_scores, order)}
    return [{"a": a, "b": b, "mutual_first": frozenset((a, b)) in firsts} for a, b in pairs]
