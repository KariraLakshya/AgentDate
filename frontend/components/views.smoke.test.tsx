import { readFileSync } from "node:fs";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import DateView from "./DateView";
import ProfileView from "./ProfileView";
import RankingsView from "./RankingsView";
import { entriesFromDates, matrixFromDates } from "@/lib/ranking";
import type { DemoBundle } from "@/lib/types";

const b: DemoBundle = JSON.parse(readFileSync("public/demo/demo.json", "utf8"));
const names = Object.fromEntries(b.people.map((p) => [p.id, p.display_name]));
const synthetic = Object.fromEntries(b.people.map((p) => [p.id, p.synthetic]));

describe("shared views render from demo.json props", () => {
  it("ProfileView", () => {
    const p = b.people[0];
    const html = renderToString(<ProfileView personId={p.id} name={p.display_name} synthetic={p.synthetic} profile={p.profile!} base="/demo" />);
    expect(html).toContain("Synthetic persona");
    expect(html).toContain("Public self vs. off-duty self");
  });
  it("DateView highlights referee-flagged lines", () => {
    const d = b.dates.find((x) => x.flagged_turns.length) ?? b.dates[0];
    const html = renderToString(<DateView date={d} names={names} synthetic={synthetic} base="/demo" />);
    expect(html).toContain("Whisper panel");
    if (d.flagged_turns.length) expect(html).toContain("Referee flag");
  });
  it("RankingsView", () => {
    const id = b.order[0];
    const html = renderToString(
      <RankingsView personId={id} entries={entriesFromDates(b.dates, id, b.best_moments)} names={names} synthetic={synthetic} order={b.order} matrixFor={(w) => matrixFromDates(b.order, b.dates, w)} stablePairs={b.stable_pairs} briefing={b.briefings[id]} base="/demo" />,
    );
    expect(html).toContain("Your best matches");
    expect(html).toContain("Best moment");
  });
});
