"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { DEFAULT_WEIGHTS, mutualFirsts as computeMutualFirsts, rankEntries, type RankEntry, type Weights } from "@/lib/ranking";
import { DIMENSIONS, type Briefing } from "@/lib/types";
import Heatmap from "./Heatmap";
import { Badge, Card, Empty, SyntheticBadge, cx } from "./ui";

const LABEL: Record<string, string> = {
  interest_overlap: "Interest overlap",
  values_alignment: "Values alignment",
  communication_chemistry: "Communication chemistry",
  lifestyle_fit: "Lifestyle fit",
  growth_potential: "Growth potential",
};

export default function RankingsView({
  personId,
  entries,
  names,
  synthetic = {},
  order,
  matrixFor,
  stablePairs,
  stable,
  briefing,
  onAsk,
  base = "",
}: {
  personId: string;
  entries: RankEntry[];
  names: Record<string, string>;
  synthetic?: Record<string, boolean>;
  order: string[];
  /** Matrix for the current weights (re-computed client-side) or a static matrix. */
  matrixFor: (w: Weights) => (number | null)[][];
  stablePairs: [string, string][];
  /** false when the backend found no fully stable matching and fell back to greedy pairing */
  stable?: boolean;
  briefing?: Briefing | null;
  onAsk?: (question: string) => Promise<string>;
  base?: string;
}) {
  const [weights, setWeights] = useState<Weights>({ ...DEFAULT_WEIGHTS });
  const ranked = useMemo(() => rankEntries(entries, weights), [entries, weights]);
  const matrix = useMemo(() => matrixFor(weights), [matrixFor, weights]);
  const mutual = useMemo(() => computeMutualFirsts(matrix, order), [matrix, order]);
  const nameOf = (id: string) => names[id] ?? id;
  const isDefault = DIMENSIONS.every((d) => weights[d] === DEFAULT_WEIGHTS[d]);

  const myStable = stablePairs.find(([a, b]) => a === personId || b === personId);
  const myStablePartner = myStable ? (myStable[0] === personId ? myStable[1] : myStable[0]) : null;
  const myMutual = mutual.find(([a, b]) => a === personId || b === personId);
  const myMutualPartner = myMutual ? (myMutual[0] === personId ? myMutual[1] : myMutual[0]) : null;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <Card title="What matters to you?" right={!isDefault ? <button className="text-xs text-accent underline" onClick={() => setWeights({ ...DEFAULT_WEIGHTS })}>Reset</button> : undefined} className="lg:sticky lg:top-4 lg:self-start">
          <p className="mb-3 text-xs text-stone-500">Drag to re-weight. The list re-sorts instantly in your browser; no dates are re-run.</p>
          <div className="space-y-4">
            {DIMENSIONS.map((d) => (
              <label key={d} className="block">
                <div className="flex justify-between text-sm"><span>{LABEL[d]}</span><span className="tabular-nums text-stone-500">{weights[d]}</span></div>
                <input type="range" min={0} max={10} step={1} value={weights[d]} onChange={(e) => setWeights((w) => ({ ...w, [d]: Number(e.target.value) }))} className="w-full accent-[#be185d]" aria-label={LABEL[d]} />
              </label>
            ))}
          </div>
        </Card>

        <Card title="Your best matches" right={myMutualPartner ? <Badge tone="amber">Mutual #1: {nameOf(myMutualPartner)}</Badge> : undefined}>
          {ranked.length === 0 ? (
            <Empty>No finished dates yet. Matches appear once your agent has dated the pool.</Empty>
          ) : (
            <ol className="space-y-3">
              {ranked.map((r) => {
                const isMutual = r.person_id === myMutualPartner;
                const isStable = r.person_id === myStablePartner;
                return (
                  <li key={r.person_id} className={cx("rounded-lg border p-3", isMutual ? "border-amber-300 bg-amber-50" : "border-stone-200 bg-white")}>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-sm font-bold text-accent">{r.rank}</span>
                      <Link href={`${base}/p/${encodeURIComponent(r.person_id)}`} className="font-semibold hover:text-accent">{nameOf(r.person_id)}</Link>
                      {synthetic[r.person_id] && <SyntheticBadge />}
                      {isMutual && <Badge tone="amber">Mutual #1</Badge>}
                      {isStable && <Badge tone="green">Stable pairing</Badge>}
                      <span className="ml-auto text-lg font-bold tabular-nums">{r.mutual === null ? "n/a" : r.mutual.toFixed(1)}<span className="text-xs font-normal text-stone-400"> /10</span></span>
                    </div>
                    <p className="mt-2 text-sm text-stone-700">
                      {r.best_moment ? <>Best moment: <q className="italic">{r.best_moment}</q></> : <span className="text-stone-400">No standout moment recorded.</span>}
                    </p>
                    <p className="mt-1 text-xs text-stone-500">
                      You rate them {r.outgoing === null ? "n/a" : r.outgoing.toFixed(1)} &middot; they rate you {r.incoming === null ? "n/a" : r.incoming.toFixed(1)}
                      {r.mine && ` · ${r.mine.would_meet_again ? "you'd meet again" : "you wouldn't meet again"}`}
                      {r.date_id && (
                        <> &middot; <Link className="text-accent underline" href={`${base}/dates/${encodeURIComponent(r.date_id)}`}>watch the date</Link></>
                      )}
                    </p>
                  </li>
                );
              })}
            </ol>
          )}
        </Card>
      </div>

      <Card title="Everyone, mutual fit heatmap">
        {order.length === 0 ? <Empty>No matrix available yet.</Empty> : <Heatmap order={order} matrix={matrix} names={names} highlightId={personId} stablePairs={stablePairs} mutualFirsts={mutual} base={base} />}
      </Card>

      <Card title="Stable pairings (Gale-Shapley)">
        {stable === false && (
          <p className="mb-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">No fully stable matching exists for these scores, so these pairings are a best-effort fallback.</p>
        )}
        {stablePairs.length === 0 ? (
          <Empty>No pairings computed yet.</Empty>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {stablePairs.map(([a, b]) => {
              const m = mutual.some(([x, y]) => (x === a && y === b) || (x === b && y === a));
              return (
                <li key={`${a}-${b}`} className={cx("flex flex-wrap items-center gap-2 rounded-lg border p-2 text-sm", m ? "border-amber-300 bg-amber-50" : "border-stone-200", (a === personId || b === personId) && "ring-2 ring-accent/40")}>
                  <Link className="hover:text-accent" href={`${base}/rankings/${encodeURIComponent(a)}`}>{nameOf(a)}</Link>
                  <span className="text-stone-400">&harr;</span>
                  <Link className="hover:text-accent" href={`${base}/rankings/${encodeURIComponent(b)}`}>{nameOf(b)}</Link>
                  {m && <Badge tone="amber">Mutual #1</Badge>}
                </li>
              );
            })}
          </ul>
        )}
        <p className="mt-2 text-xs text-stone-400">Mutual #1 is computed from the current slider weights; stable pairings come from the backend run.</p>
      </Card>

      <BriefingCard briefing={briefing} nameOf={nameOf} onAsk={onAsk} base={base} />
    </div>
  );
}

function BriefingCard({ briefing, nameOf, onAsk, base }: { briefing?: Briefing | null; nameOf: (id: string) => string; onAsk?: (q: string) => Promise<string>; base: string }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [thread, setThread] = useState<{ q: string; a: string; err?: boolean }[]>([]);
  async function ask(e: React.FormEvent) {
    e.preventDefault();
    const question = q.trim();
    if (!question || !onAsk) return;
    setBusy(true);
    try {
      const a = await onAsk(question);
      setThread((t) => [...t, { q: question, a }]);
      setQ("");
    } catch (err) {
      setThread((t) => [...t, { q: question, a: err instanceof Error ? err.message : "Request failed", err: true }]);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Post-date briefing from your agent">
      {!briefing ? (
        <Empty>Your agent has not written a briefing yet.</Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <h3 className="mb-2 text-sm font-semibold text-emerald-700">Who I would introduce</h3>
            <ul className="space-y-2 text-sm">{briefing.introduce.map((x, i) => <li key={i}><Link className="font-medium hover:text-accent" href={`${base}/p/${encodeURIComponent(x.person_id)}`}>{nameOf(x.person_id)}</Link><p className="text-stone-600">{x.reason}</p></li>)}</ul>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-semibold text-red-700">Who I would warn you about</h3>
            <ul className="space-y-2 text-sm">{briefing.warn.map((x, i) => <li key={i}><Link className="font-medium hover:text-accent" href={`${base}/p/${encodeURIComponent(x.person_id)}`}>{nameOf(x.person_id)}</Link><p className="text-stone-600">{x.reason}</p></li>)}</ul>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-semibold text-stone-700">What I was unsure about</h3>
            <ul className="list-disc space-y-1 pl-4 text-sm text-stone-600">{briefing.unsure.map((x, i) => <li key={i}>{x}</li>)}</ul>
          </div>
        </div>
      )}

      <div className="mt-5 border-t border-stone-100 pt-4">
        <h3 className="mb-2 text-sm font-semibold">Ask my agent why</h3>
        {onAsk ? (
          <>
            <form onSubmit={ask} className="flex flex-col gap-2 sm:flex-row">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Why did you rank my #1 above my #2?" className="min-w-0 flex-1 rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-accent focus:outline-none" aria-label="Question for your agent" />
              <button disabled={busy || !q.trim()} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Thinking..." : "Ask"}</button>
            </form>
            <div className="mt-3 space-y-3">
              {thread.map((t, i) => (
                <div key={i} className="text-sm"><p className="font-medium">You: {t.q}</p><p className={cx("mt-1 rounded-md p-2", t.err ? "bg-red-50 text-red-800" : "bg-stone-50 text-stone-700")}>{t.a}</p></div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm text-stone-500">Asking the agent needs a live backend. In demo mode you can read the briefing above, but the agent is not running.</p>
        )}
      </div>
    </Card>
  );
}
