import Link from "next/link";
import type { ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Shell({ children, wide, demo }: { children: ReactNode; wide?: boolean; demo?: boolean }) {
  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <Link href="/" className="text-base font-semibold tracking-tight text-accent">
            Agentic Dating
          </Link>
          <nav className="flex items-center gap-3 text-sm">
            {demo && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">Demo mode</span>}
            <Link href="/demo" className="text-stone-600 hover:text-accent">Demo</Link>
            <Link href="/" className="text-stone-600 hover:text-accent">Try it</Link>
          </nav>
        </div>
      </header>
      <main className={cx("mx-auto px-4 py-6 sm:py-8", wide ? "max-w-6xl" : "max-w-3xl")}>{children}</main>
    </div>
  );
}

export function Card({ title, children, className, right }: { title?: ReactNode; children: ReactNode; className?: string; right?: ReactNode }) {
  return (
    <section className={cx("rounded-xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5", className)}>
      {(title || right) && (
        <div className="mb-3 flex items-start justify-between gap-2">
          {title && <h2 className="text-sm font-semibold uppercase tracking-wide text-stone-500">{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function SyntheticBadge({ className }: { className?: string }) {
  return (
    <span className={cx("inline-block rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-800", className)}>
      Synthetic persona
    </span>
  );
}

export function Badge({ children, tone = "stone" }: { children: ReactNode; tone?: "stone" | "blue" | "pink" | "green" | "red" | "amber" }) {
  const tones = {
    stone: "bg-stone-100 text-stone-700",
    blue: "bg-sky-100 text-sky-800",
    pink: "bg-pink-100 text-pink-800",
    green: "bg-emerald-100 text-emerald-800",
    red: "bg-red-100 text-red-800",
    amber: "bg-amber-100 text-amber-800",
  };
  return <span className={cx("inline-block rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>{children}</span>;
}

export function SourceBadge({ source }: { source: "linkedin" | "instagram" }) {
  return <Badge tone={source === "linkedin" ? "blue" : "pink"}>{source === "linkedin" ? "LinkedIn" : "Instagram"}</Badge>;
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const color = pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2" title={`Confidence ${pct}%`}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-stone-200" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Confidence">
        <div className={cx("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-stone-500">{pct}%</span>
    </div>
  );
}

export function Spinner({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-stone-500" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-stone-300 border-t-accent" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
      <p className="font-medium">Something went wrong</p>
      <p className="mt-1 break-words">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-3 rounded-md bg-red-600 px-3 py-1.5 text-white hover:bg-red-700">Retry</button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-stone-300 p-6 text-center text-sm text-stone-500">{children}</div>;
}

/** Faithfulness scores may arrive as 0-1 or 0-10. */
export function fmtFaith(v: number | null | undefined): string {
  if (v === null || v === undefined) return "n/a";
  return `${Math.round((v <= 1 ? v : v / 10) * 100)}%`;
}
export function faithTone(v: number | null | undefined): "green" | "amber" | "red" | "stone" {
  if (v === null || v === undefined) return "stone";
  const n = v <= 1 ? v : v / 10;
  return n >= 0.9 ? "green" : n >= 0.75 ? "amber" : "red";
}
