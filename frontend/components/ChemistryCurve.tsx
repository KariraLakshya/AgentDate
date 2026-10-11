"use client";
import type { DateTurn } from "@/lib/types";

const W = 640;
const H = 220;
const P = { l: 34, r: 14, t: 14, b: 26 };

const MARK: Record<string, { color: string; label: string }> = {
  spark: { color: "#059669", label: "Spark" },
  friction: { color: "#dc2626", label: "Friction" },
  repair: { color: "#0284c7", label: "Repair" },
};

export default function ChemistryCurve({ turns, selected, onSelect }: { turns: DateTurn[]; selected?: number | null; onSelect?: (idx: number) => void }) {
  if (turns.length === 0) return null;
  const n = turns.length;
  const x = (i: number) => P.l + (n === 1 ? (W - P.l - P.r) / 2 : (i / (n - 1)) * (W - P.l - P.r));
  const y = (c: number) => P.t + (1 - Math.max(0, Math.min(10, c)) / 10) * (H - P.t - P.b);
  const path = turns.map((t, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(t.chemistry).toFixed(1)}`).join(" ");
  const area = `${path} L${x(n - 1).toFixed(1)},${y(0)} L${x(0).toFixed(1)},${y(0)} Z`;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Chemistry per turn">
        {[0, 5, 10].map((g) => (
          <g key={g}>
            <line x1={P.l} x2={W - P.r} y1={y(g)} y2={y(g)} stroke="#e7e5e4" strokeDasharray={g === 5 ? "3 3" : undefined} />
            <text x={P.l - 6} y={y(g) + 4} textAnchor="end" fontSize="10" fill="#78716c">{g}</text>
          </g>
        ))}
        <path d={area} fill="#be185d" opacity="0.08" />
        <path d={path} fill="none" stroke="#be185d" strokeWidth="2.5" strokeLinejoin="round" />
        {turns.map((t, i) => {
          const marks = t.flags.filter((f) => MARK[f.type]);
          const m = marks[0] ? MARK[marks[0].type] : null;
          const sel = selected === t.idx;
          return (
            <g key={t.idx} onClick={() => onSelect?.(t.idx)} className={onSelect ? "cursor-pointer" : undefined}>
              <circle cx={x(i)} cy={y(t.chemistry)} r={sel ? 7 : m ? 6 : 3.5} fill={m ? m.color : "#fff"} stroke={m ? "#fff" : "#be185d"} strokeWidth={m ? 2 : 1.5}>
                <title>{`Turn ${t.idx + 1}: chemistry ${t.chemistry.toFixed(1)}${marks.map((f) => ` - ${MARK[f.type].label}: ${f.note}`).join("")}`}</title>
              </circle>
              <text x={x(i)} y={H - 8} textAnchor="middle" fontSize="10" fill="#78716c">{t.idx + 1}</text>
            </g>
          );
        })}
      </svg>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-500">
        {Object.entries(MARK).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: v.color }} />{v.label}</span>
        ))}
      </div>
    </div>
  );
}
