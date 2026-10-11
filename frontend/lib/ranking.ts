// Pure ranking logic. No network, no React: sliders re-sort entirely client-side.
import { DIMENSIONS, type DateRecord, type Dimension, type Rubric } from "./types";

export type Weights = Record<Dimension, number>;
export type Scores = Record<Dimension, number>;

export const DEFAULT_WEIGHTS: Weights = {
  interest_overlap: 1,
  values_alignment: 1,
  communication_chemistry: 1,
  lifestyle_fit: 1,
  growth_potential: 1,
};

/** Weights clamped to >= 0. If they all sum to 0, fall back to equal weights. */
export function normalizeWeights(w: Partial<Weights>): Weights {
  const clean = {} as Weights;
  let sum = 0;
  for (const d of DIMENSIONS) {
    const v = Number.isFinite(w[d]) ? Math.max(0, w[d] as number) : 0;
    clean[d] = v;
    sum += v;
  }
  if (sum <= 0) {
    for (const d of DIMENSIONS) clean[d] = 1 / DIMENSIONS.length;
    return clean;
  }
  for (const d of DIMENSIONS) clean[d] = clean[d] / sum;
  return clean;
}

/** Directional score: weighted mean of the five rubric dimensions (0-10). */
export function weightedMean(scores: Scores, weights: Partial<Weights> = DEFAULT_WEIGHTS): number {
  const w = normalizeWeights(weights);
  let total = 0;
  for (const d of DIMENSIONS) total += w[d] * scores[d];
  return total;
}

/** Harmonic mean of two directional scores; 0 if either is non-positive. */
export function harmonicMean(a: number, b: number): number {
  if (!(a > 0) || !(b > 0)) return 0;
  return (2 * a * b) / (a + b);
}

/** pair_score = harmonic_mean(a->b, b->a) with each side a weighted mean. */
export function pairScore(mine: Scores, theirs: Scores, weights: Partial<Weights> = DEFAULT_WEIGHTS): number {
  return harmonicMean(weightedMean(mine, weights), weightedMean(theirs, weights));
}

export interface RankEntry {
  person_id: string;
  date_id?: string;
  mine: Rubric | null; // my rating of them
  theirs: Rubric | null; // their rating of me
  best_moment?: string;
}
export interface Ranked extends RankEntry {
  rank: number;
  outgoing: number | null;
  incoming: number | null;
  mutual: number | null;
}

/** Score and sort entries by mutual fit (desc). Entries with a missing side sort last. Stable. */
export function rankEntries(entries: RankEntry[], weights: Partial<Weights> = DEFAULT_WEIGHTS): Ranked[] {
  const scored = entries.map((e, i) => {
    const outgoing = e.mine ? weightedMean(e.mine, weights) : null;
    const incoming = e.theirs ? weightedMean(e.theirs, weights) : null;
    const mutual = outgoing !== null && incoming !== null ? harmonicMean(outgoing, incoming) : null;
    return { e, i, outgoing, incoming, mutual };
  });
  scored.sort((x, y) => {
    if (x.mutual === null && y.mutual === null) return x.i - y.i;
    if (x.mutual === null) return 1;
    if (y.mutual === null) return -1;
    return y.mutual - x.mutual || x.i - y.i;
  });
  return scored.map((s, idx) => ({ ...s.e, rank: idx + 1, outgoing: s.outgoing, incoming: s.incoming, mutual: s.mutual }));
}

/** Prefer the standard date between two people; fall back to any date. */
function findDate(dates: DateRecord[], a: string, b: string): DateRecord | undefined {
  const between = dates.filter(
    (d) => (d.person_a === a && d.person_b === b) || (d.person_a === b && d.person_b === a),
  );
  return between.find((d) => d.kind === "standard" && d.score_a && d.score_b) ?? between.find((d) => d.score_a && d.score_b) ?? between[0];
}

/** Entries for one person from a set of dates (client-side, used by /demo). */
export function entriesFromDates(
  dates: DateRecord[],
  personId: string,
  bestMoments: Record<string, string> = {},
): RankEntry[] {
  const others = new Set<string>();
  for (const d of dates) {
    if (d.person_a === personId) others.add(d.person_b);
    else if (d.person_b === personId) others.add(d.person_a);
  }
  return [...others].map((other) => {
    const d = findDate(dates, personId, other)!;
    const iAmA = d.person_a === personId;
    return {
      person_id: other,
      date_id: d.id,
      mine: iAmA ? d.score_a : d.score_b,
      theirs: iAmA ? d.score_b : d.score_a,
      best_moment: bestMoments[`${personId}|${other}`],
    };
  });
}

/** Re-weighted n x n matrix of directional scores; matrix[i][j] = i's score for j. */
export function matrixFromDates(order: string[], dates: DateRecord[], weights: Partial<Weights> = DEFAULT_WEIGHTS): (number | null)[][] {
  return order.map((a) =>
    order.map((b) => {
      if (a === b) return null;
      const d = findDate(dates, a, b);
      if (!d) return null;
      const r = d.person_a === a ? d.score_a : d.score_b;
      return r ? weightedMean(r, weights) : null;
    }),
  );
}

/** Pairs [i, j] (i < j) where each is the other's single highest-scored person. */
export function mutualFirsts(matrix: (number | null)[][], order: string[]): [string, string][] {
  const top = matrix.map((row) => {
    let best = -1;
    let bestScore = -Infinity;
    row.forEach((v, j) => {
      if (v !== null && v > bestScore) {
        bestScore = v;
        best = j;
      }
    });
    return best;
  });
  const out: [string, string][] = [];
  top.forEach((j, i) => {
    if (j > i && top[j] === i) out.push([order[i], order[j]]);
  });
  return out;
}

/** Order-independent key for a pair of ids. */
export function pairKey(a: string, b: string): string {
  return a < b ? `${a}\u0000${b}` : `${b}\u0000${a}`;
}
