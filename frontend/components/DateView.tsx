"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { DateRecord, DateTurn, Rubric } from "@/lib/types";
import { DIMENSIONS } from "@/lib/types";
import ChemistryCurve from "./ChemistryCurve";
import { Badge, Card, Empty, SyntheticBadge, cx, faithTone, fmtFaith } from "./ui";

const FLAG_TONE: Record<string, "green" | "red" | "blue" | "amber"> = { spark: "green", friction: "red", repair: "blue", unsupported_claim: "amber" };
const FLAG_LABEL: Record<string, string> = { spark: "Spark", friction: "Friction", repair: "Repair", unsupported_claim: "Referee: unsupported" };

function RubricBox({ name, r }: { name: string; r: Rubric | null }) {
  if (!r) return null;
  return (
    <div className="rounded-lg border border-stone-100 bg-stone-50 p-3 text-sm">
      <p className="font-medium">{name}&rsquo;s rating</p>
      <p className="mt-1 italic text-stone-600">&ldquo;{r.verdict}&rdquo;</p>
      <p className="mt-1 text-xs text-stone-500">{r.would_meet_again ? "Would meet again" : "Would not meet again"}</p>
      <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
        {DIMENSIONS.map((d) => (
          <div key={d} className="flex justify-between"><dt className="text-stone-500">{d.replace(/_/g, " ")}</dt><dd className="tabular-nums">{r[d]}/10</dd></div>
        ))}
      </dl>
    </div>
  );
}

export default function DateView({
  date,
  names,
  synthetic = {},
  live = false,
  connection,
  base = "",
}: {
  date: DateRecord;
  names: Record<string, string>;
  synthetic?: Record<string, boolean>;
  live?: boolean;
  connection?: string;
  base?: string;
}) {
  const nameOf = (id: string) => names[id] ?? id;
  const turns = useMemo(() => [...date.turns].sort((a, b) => a.idx - b.idx), [date.turns]);
  const [selected, setSelected] = useState<number | null>(null);
  const followLatest = selected === null;
  const lastIdx = turns.length ? turns[turns.length - 1].idx : null;
  const cur = selected ?? lastIdx;
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (live && followLatest) endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [turns.length, live, followLatest]);

  const upTo = cur === null ? [] : turns.filter((t) => t.idx <= cur);
  const lastNote = (id: string): DateTurn | undefined => [...upTo].reverse().find((t) => t.speaker === id);
  const flagged = new Set(date.flagged_turns);
  const speakerColor = (id: string) => (id === date.person_a ? "bg-sky-50 border-sky-200" : "bg-pink-50 border-pink-200");

  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight">
            <Link href={`${base}/p/${encodeURIComponent(date.person_a)}`} className="hover:text-accent">{nameOf(date.person_a)}</Link>
            <span className="mx-2 text-stone-400">&times;</span>
            <Link href={`${base}/p/${encodeURIComponent(date.person_b)}`} className="hover:text-accent">{nameOf(date.person_b)}</Link>
          </h1>
          <Badge tone={date.status === "running" ? "green" : date.status === "failed" ? "red" : "stone"}>
            {date.status === "running" ? "Live" : date.status}
          </Badge>
          <Badge>{date.kind === "scenario" ? "Scenario date" : "Standard date"}</Badge>
          {[date.person_a, date.person_b].some((id) => synthetic[id]) && <SyntheticBadge />}
        </div>
        {connection && <p className="mt-1 text-xs text-stone-500">{connection}</p>}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
        <div className="space-y-5">
          <Card title="Chemistry curve">
            {turns.length ? <ChemistryCurve turns={turns} selected={cur} onSelect={setSelected} /> : <Empty>{date.status === "failed" ? "This date failed before any turns." : "Waiting for the first turn..."}</Empty>}
          </Card>

          <Card title="Transcript" right={!followLatest ? <button className="text-xs text-accent underline" onClick={() => setSelected(null)}>Follow latest</button> : undefined}>
            {turns.length === 0 ? (
              <Empty>No turns yet.</Empty>
            ) : (
              <ol className="space-y-3">
                {turns.map((t) => {
                  const isFlag = flagged.has(t.idx) || t.flags.some((f) => f.type === "unsupported_claim");
                  const other = t.flags.filter((f) => f.type !== "unsupported_claim");
                  const bad = t.flags.filter((f) => f.type === "unsupported_claim");
                  return (
                    <li key={t.idx} onClick={() => setSelected(t.idx)}
                      className={cx("cursor-pointer rounded-lg border p-3 transition", speakerColor(t.speaker), isFlag && "border-amber-400 bg-amber-50 ring-2 ring-amber-300", cur === t.idx && "outline outline-2 outline-accent/60")}>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-stone-500">
                        <span className="font-semibold text-stone-800">{nameOf(t.speaker)}</span>
                        <span>turn {t.idx + 1}</span>
                        <span>{t.stage.replace(/_/g, " ")}</span>
                        <span className="tabular-nums">chem {t.chemistry.toFixed(1)}</span>
                        {other.map((f, i) => <Badge key={i} tone={FLAG_TONE[f.type]}>{FLAG_LABEL[f.type]}</Badge>)}
                      </div>
                      <p className="mt-1 text-[15px] leading-relaxed">{t.public_text}</p>
                      {isFlag && (
                        <p className="mt-2 rounded bg-amber-100 p-2 text-xs text-amber-900">
                          <strong>Referee flag:</strong> {bad.length ? bad.map((f) => f.note).join(" ") : "Claim not supported by this person's profile."}
                          {" "}Faithfulness {nameOf(t.speaker)}: {fmtFaith(t.speaker === date.person_a ? date.faithfulness_a : date.faithfulness_b)}
                        </p>
                      )}
                    </li>
                  );
                })}
                <div ref={endRef} />
              </ol>
            )}
            {live && date.status === "running" && <p className="mt-3 flex items-center gap-2 text-xs text-stone-500"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />Agents are still talking...</p>}
          </Card>
        </div>

        <aside className="space-y-5 lg:sticky lg:top-4 lg:self-start">
          <Card title="Whisper panel" right={cur !== null ? <span className="text-xs text-stone-400">as of turn {cur + 1}</span> : undefined}>
            <p className="mb-3 text-xs text-stone-500">Each agent&rsquo;s private reasoning. The other agent never sees this.</p>
            <div className="space-y-3">
              {[date.person_a, date.person_b].map((id) => {
                const t = lastNote(id);
                return (
                  <div key={id} className={cx("rounded-lg border p-3 text-sm", speakerColor(id))}>
                    <p className="font-medium">{nameOf(id)}&rsquo;s agent thinks</p>
                    {t ? (
                      <>
                        <p className="mt-1 italic text-stone-700">{t.private_note}</p>
                        <p className="mt-1 text-xs text-stone-500">turn {t.idx + 1} &middot; chemistry {t.chemistry.toFixed(1)}/10</p>
                      </>
                    ) : (
                      <p className="mt-1 text-stone-400">Nothing yet.</p>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>

          <Card title="Referee">
            <div className="space-y-2 text-sm">
              {[[date.person_a, date.faithfulness_a], [date.person_b, date.faithfulness_b]].map(([id, f]) => (
                <div key={id as string} className="flex items-center justify-between">
                  <span>{nameOf(id as string)}</span>
                  <Badge tone={faithTone(f as number | null)}>Faithfulness {fmtFaith(f as number | null)}</Badge>
                </div>
              ))}
              <p className="text-xs text-stone-500">{date.flagged_turns.length ? `${date.flagged_turns.length} line(s) flagged and highlighted in the transcript.` : "No unsupported claims flagged."}</p>
            </div>
          </Card>

          {(date.score_a || date.score_b) && (
            <Card title="After the date">
              <div className="space-y-3">
                <RubricBox name={nameOf(date.person_a)} r={date.score_a} />
                <RubricBox name={nameOf(date.person_b)} r={date.score_b} />
              </div>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
