"use client";
import Link from "next/link";
import { Fragment } from "react";
import { pairKey } from "@/lib/ranking";
import { cx } from "./ui";

export default function Heatmap({
  order,
  matrix,
  names,
  highlightId,
  stablePairs = [],
  mutualFirsts = [],
  base = "",
}: {
  order: string[];
  matrix: (number | null)[][];
  names: Record<string, string>;
  highlightId?: string;
  stablePairs?: [string, string][];
  mutualFirsts?: [string, string][];
  base?: string;
}) {
  const n = order.length;
  const stable = new Set(stablePairs.map(([a, b]) => pairKey(a, b)));
  const mutual = new Set(mutualFirsts.map(([a, b]) => pairKey(a, b)));
  const short = (id: string) => (names[id] ?? id).split(" ")[0];
  return (
    <div>
      <div className="overflow-x-auto">
        <div className="grid gap-px text-[10px]" style={{ gridTemplateColumns: `minmax(70px, 96px) repeat(${n}, minmax(18px, 1fr))`, minWidth: 96 + n * 20 }}>
          <div />
          {order.map((id, j) => (
            <div key={id} className="pb-1 text-center text-stone-400" title={names[id] ?? id}>{j + 1}</div>
          ))}
          {order.map((a, i) => (
            <Fragment key={a}>
              <Link href={`${base}/rankings/${encodeURIComponent(a)}`} className={cx("truncate pr-1 text-right leading-5 hover:text-accent", highlightId === a ? "font-bold text-accent" : "text-stone-600")} title={names[a] ?? a}>
                <span className="text-stone-400">{i + 1}</span> {short(a)}
              </Link>
              {order.map((b, j) => {
                const v = matrix[i]?.[j] ?? null;
                const k = pairKey(a, b);
                const isMutual = a !== b && mutual.has(k);
                const isStable = a !== b && stable.has(k);
                return (
                  <div
                    key={b}
                    title={a === b ? names[a] ?? a : `${names[a] ?? a} rates ${names[b] ?? b}: ${v === null ? "n/a" : v.toFixed(1)}${isMutual ? " (mutual #1)" : isStable ? " (stable pair)" : ""}`}
                    className={cx("h-5 rounded-[2px]", a === b && "bg-stone-100", v === null && a !== b && "bg-stone-50", isMutual ? "ring-2 ring-inset ring-amber-400" : isStable && "ring-1 ring-inset ring-stone-900/70", highlightId && (a === highlightId || b === highlightId) && "outline outline-1 outline-accent/40")}
                    style={v === null ? undefined : { backgroundColor: `rgba(190, 24, 93, ${(0.08 + (Math.max(0, Math.min(10, v)) / 10) * 0.92).toFixed(2)})` }}
                  />
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-stone-500">
        <span className="flex items-center gap-1">low <span className="inline-block h-2.5 w-24 rounded" style={{ background: "linear-gradient(90deg, rgba(190,24,93,.08), rgba(190,24,93,1))" }} /> high</span>
        <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm ring-2 ring-inset ring-amber-400" />mutual #1</span>
        <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm ring-1 ring-inset ring-stone-900/70" />stable pairing</span>
        <span>Row rates column.</span>
      </div>
    </div>
  );
}
