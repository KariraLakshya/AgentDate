"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, api } from "@/lib/api";

const field = "mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent";

export default function SubmitForm() {
  const router = useRouter();
  const [li, setLi] = useState("");
  const [ig, setIg] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const liOk = /^https?:\/\/([a-z0-9-]+\.)?linkedin\.com\/.+/i.test(li.trim());
  const igOk = /^https?:\/\/([a-z0-9-]+\.)?instagram\.com\/.+/i.test(ig.trim());
  const valid = liOk && igOk;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!consent || !valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ person_id: string }>("/api/people", {
        method: "POST",
        body: JSON.stringify({ linkedin_url: li.trim(), instagram_url: ig.trim(), consent }),
      });
      router.push(`/p/${encodeURIComponent(r.person_id)}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setError("Consent is required. Tick the box to confirm this is you or you have permission.");
      else if (err instanceof ApiError && err.status === 429) setError("Too many requests. Please wait a minute and try again.");
      else setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-stone-200 bg-white p-5 shadow-sm" noValidate>
      <label className="block text-sm font-medium">
        LinkedIn profile link
        <input type="url" inputMode="url" required value={li} onChange={(e) => setLi(e.target.value)} placeholder="https://www.linkedin.com/in/your-name" className={field} aria-invalid={li !== "" && !liOk} />
        {li !== "" && !liOk && <span className="mt-1 block text-xs text-red-600">Enter a linkedin.com link.</span>}
      </label>
      <label className="block text-sm font-medium">
        Public Instagram link
        <input type="url" inputMode="url" required value={ig} onChange={(e) => setIg(e.target.value)} placeholder="https://www.instagram.com/your.handle" className={field} aria-invalid={ig !== "" && !igOk} />
        {ig !== "" && !igOk && <span className="mt-1 block text-xs text-red-600">Enter an instagram.com link.</span>}
      </label>

      <label className="flex items-start gap-3 rounded-md bg-stone-50 p-3 text-sm">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 h-4 w-4 accent-[#be185d]" />
        <span>This is me, or I have this person&rsquo;s permission</span>
      </label>

      {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-800" role="alert">{error}</p>}

      <button type="submit" disabled={!consent || !valid || busy} className="w-full rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-white transition enabled:hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40">
        {busy ? "Starting..." : "Build my profile"}
      </button>
      {!consent && <p className="text-center text-xs text-stone-400">Tick the consent box to continue.</p>}
      <p className="text-center text-xs text-stone-500">Just exploring? <Link href="/demo" className="text-accent underline">Try the demo</Link>, no sign-up or backend needed.</p>
    </form>
  );
}
