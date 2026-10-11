import { describe, expect, it } from "vitest";
import {
  DEFAULT_WEIGHTS,
  entriesFromDates,
  harmonicMean,
  matrixFromDates,
  mutualFirsts,
  normalizeWeights,
  rankEntries,
  weightedMean,
} from "./ranking";
import type { DateRecord, Rubric } from "./types";

const rub = (v: number[]): Rubric => ({
  interest_overlap: v[0],
  values_alignment: v[1],
  communication_chemistry: v[2],
  lifestyle_fit: v[3],
  growth_potential: v[4],
  would_meet_again: true,
  verdict: "",
});

describe("weightedMean", () => {
  it("is the plain mean with equal weights", () => {
    expect(weightedMean(rub([2, 4, 6, 8, 10]), DEFAULT_WEIGHTS)).toBeCloseTo(6);
  });
  it("respects weights", () => {
    const w = { ...DEFAULT_WEIGHTS, interest_overlap: 3, values_alignment: 0, communication_chemistry: 0, lifestyle_fit: 0, growth_potential: 1 };
    expect(weightedMean(rub([10, 0, 0, 0, 2]), w)).toBeCloseTo((3 * 10 + 1 * 2) / 4);
  });
  it("falls back to equal weights when all zero", () => {
    const w = normalizeWeights({ interest_overlap: 0, values_alignment: 0, communication_chemistry: 0, lifestyle_fit: 0, growth_potential: 0 });
    expect(Object.values(w).reduce((a, b) => a + b, 0)).toBeCloseTo(1);
    expect(weightedMean(rub([2, 4, 6, 8, 10]), w)).toBeCloseTo(6);
  });
});

describe("harmonicMean", () => {
  it("matches the formula", () => expect(harmonicMean(4, 12)).toBeCloseTo(6));
  it("is <= arithmetic mean and punishes imbalance", () => {
    expect(harmonicMean(9, 1)).toBeLessThan(5);
  });
  it("is 0 if either side is 0", () => expect(harmonicMean(0, 9)).toBe(0));
});

describe("rankEntries", () => {
  const entries = [
    { person_id: "x", mine: rub([9, 9, 9, 9, 9]), theirs: rub([2, 2, 2, 2, 2]) }, // lopsided
    { person_id: "y", mine: rub([6, 6, 6, 6, 6]), theirs: rub([6, 6, 6, 6, 6]) }, // balanced
    { person_id: "z", mine: null, theirs: rub([9, 9, 9, 9, 9]) }, // missing
  ];
  it("ranks balanced above lopsided and puts missing last", () => {
    expect(rankEntries(entries).map((r) => r.person_id)).toEqual(["y", "x", "z"]);
  });
  it("re-sorts when weights change", () => {
    const e = [
      { person_id: "a", mine: rub([10, 0, 0, 0, 0]), theirs: rub([10, 0, 0, 0, 0]) },
      { person_id: "b", mine: rub([0, 10, 0, 0, 0]), theirs: rub([0, 10, 0, 0, 0]) },
    ];
    const onInterest = { ...DEFAULT_WEIGHTS, values_alignment: 0, communication_chemistry: 0, lifestyle_fit: 0, growth_potential: 0 };
    const onValues = { ...DEFAULT_WEIGHTS, interest_overlap: 0, communication_chemistry: 0, lifestyle_fit: 0, growth_potential: 0 };
    expect(rankEntries(e, onInterest)[0].person_id).toBe("a");
    expect(rankEntries(e, onValues)[0].person_id).toBe("b");
  });
  it("is stable on ties", () => {
    const e = ["p", "q", "r"].map((id) => ({ person_id: id, mine: rub([5, 5, 5, 5, 5]), theirs: rub([5, 5, 5, 5, 5]) }));
    expect(rankEntries(e).map((r) => r.person_id)).toEqual(["p", "q", "r"]);
  });
});

describe("dates -> entries/matrix", () => {
  const date = (id: string, a: string, b: string, sa: number, sb: number): DateRecord => ({
    id, person_a: a, person_b: b, kind: "standard", status: "done", turns: [],
    score_a: rub([sa, sa, sa, sa, sa]), score_b: rub([sb, sb, sb, sb, sb]),
    faithfulness_a: 1, faithfulness_b: 1, flagged_turns: [],
  });
  const dates = [date("ab", "A", "B", 9, 8), date("ac", "A", "C", 3, 7), date("bc", "B", "C", 2, 4)];
  it("orients scores to the viewer", () => {
    const e = entriesFromDates(dates, "B");
    const a = e.find((x) => x.person_id === "A")!;
    expect(a.mine!.interest_overlap).toBe(8); // B's rating of A
    expect(a.theirs!.interest_overlap).toBe(9);
  });
  it("builds a directional matrix and finds mutual #1s", () => {
    const order = ["A", "B", "C"];
    const m = matrixFromDates(order, dates);
    expect(m[0][1]).toBeCloseTo(9);
    expect(m[1][0]).toBeCloseTo(8);
    expect(m[0][0]).toBeNull();
    expect(mutualFirsts(m, order)).toEqual([["A", "B"]]);
  });
});
