"use client";
import Link from "next/link";
import { useCallback, useMemo, type ReactNode } from "react";
import { useDemo } from "@/lib/hooks";
import { entriesFromDates, matrixFromDates, type Weights } from "@/lib/ranking";
import type { DemoBundle } from "@/lib/types";
import DateView from "./DateView";
import ProfileView from "./ProfileView";
import RankingsView from "./RankingsView";
import { Card, Empty, ErrorBox, Spinner, SyntheticBadge } from "./ui";

const BASE = "/demo";

function Gate({ children }: { children: (b: DemoBundle) => ReactNode }) {
  const { data, error, loading, reload } = useDemo();
  if (loading) return <Spinner label="Loading the pre-run demo..." />;
  if (error || !data) return <ErrorBox message={error ?? "Demo data missing."} onRetry={reload} />;
  if (!data.people?.length) return <Empty>The demo bundle is empty.</Empty>;
  return <>{children(data)}</>;
}

function maps(b: DemoBundle) {
  const names: Record<string, string> = {};
  const synthetic: Record<string, boolean> = {};
  b.people.forEach((p) => {
    names[p.id] = p.display_name;
    if (p.synthetic) synthetic[p.id] = true;
  });
  return { names, synthetic };
}

export function DemoHome() {
  return (
    <Gate>
      {(b) => (
        <div className="space-y-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Pre-run demo</h1>
            <p className="mt-1 text-stone-600">
              {b.people.length} people, {b.dates.length} agent-vs-agent dates, all pre-computed. Every person below is a clearly labelled synthetic persona; no real individuals are simulated.
              This page needs no backend.
            </p>
          </div>
          <Card title="Pick a person">
            <ul className="grid gap-3 sm:grid-cols-2">
              {b.people.map((p) => (
                <li key={p.id} className="rounded-lg border border-stone-200 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{p.display_name}</span>
                    {p.synthetic && <SyntheticBadge />}
                  </div>
                  {p.profile && <p className="mt-1 line-clamp-2 text-sm text-stone-600">{p.profile.summary}</p>}
                  <div className="mt-2 flex gap-3 text-sm">
                    <Link className="text-accent underline" href={`${BASE}/p/${encodeURIComponent(p.id)}`}>Profile</Link>
                    <Link className="text-accent underline" href={`${BASE}/rankings/${encodeURIComponent(p.id)}`}>Matches</Link>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          {b.dates.length > 0 && (
            <Card title="Browse dates">
              <ul className="grid gap-1 text-sm sm:grid-cols-2">
                {b.dates.slice(0, 40).map((d) => {
                  const { names } = maps(b);
                  return (
                    <li key={d.id}>
                      <Link className="hover:text-accent" href={`${BASE}/dates/${encodeURIComponent(d.id)}`}>
                        {names[d.person_a] ?? d.person_a} &times; {names[d.person_b] ?? d.person_b}
                        {d.kind === "scenario" && " (scenario)"}
                      </Link>
                    </li>
                  );
                })}
              </ul>
              {b.dates.length > 40 && <p className="mt-2 text-xs text-stone-400">Showing 40 of {b.dates.length}. Use a person&rsquo;s matches page to reach the rest.</p>}
            </Card>
          )}
        </div>
      )}
    </Gate>
  );
}

export function DemoProfile({ id }: { id: string }) {
  return (
    <Gate>
      {(b) => {
        const p = b.people.find((x) => x.id === id);
        if (!p) return <Empty>No such demo person. <Link className="text-accent underline" href="/demo">Back to the picker</Link></Empty>;
        if (!p.profile) return <Empty>This demo person has no profile.</Empty>;
        return <ProfileView personId={p.id} name={p.display_name} synthetic={p.synthetic} profile={p.profile} base={BASE} />;
      }}
    </Gate>
  );
}

export function DemoDate({ id }: { id: string }) {
  return (
    <Gate>
      {(b) => {
        const d = b.dates.find((x) => x.id === id || `${x.person_a}-${x.person_b}` === id || `${x.person_b}-${x.person_a}` === id);
        if (!d) return <Empty>No such date in the demo. <Link className="text-accent underline" href="/demo">Back to the picker</Link></Empty>;
        const { names, synthetic } = maps(b);
        return <DateView date={d} names={names} synthetic={synthetic} base={BASE} />;
      }}
    </Gate>
  );
}

function RankingsInner({ b, id }: { b: DemoBundle; id: string }) {
  const { names, synthetic } = useMemo(() => maps(b), [b]);
  const entries = useMemo(() => entriesFromDates(b.dates, id, b.best_moments), [b, id]);
  const matrixFor = useCallback((w: Weights) => matrixFromDates(b.order, b.dates, w), [b]);
  const me = names[id] ?? id;
  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight">Matches for {me}</h1>
          {synthetic[id] && <SyntheticBadge />}
        </div>
        <p className="mt-1 text-sm text-stone-600"><Link className="text-accent underline" href={`${BASE}/p/${encodeURIComponent(id)}`}>View profile</Link></p>
      </div>
      <RankingsView personId={id} entries={entries} names={names} synthetic={synthetic} order={b.order} matrixFor={matrixFor} stablePairs={b.stable_pairs} briefing={b.briefings?.[id] ?? null} base={BASE} />
    </div>
  );
}

export function DemoRankings({ id }: { id: string }) {
  return (
    <Gate>
      {(b) => (b.people.some((p) => p.id === id) ? <RankingsInner b={b} id={id} /> : <Empty>No such demo person. <Link className="text-accent underline" href="/demo">Back to the picker</Link></Empty>)}
    </Gate>
  );
}
