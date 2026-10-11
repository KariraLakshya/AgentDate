"use client";
import { useState } from "react";
import { api } from "@/lib/api";

/** Delete-my-data: removes the person, consent, profile, dates and cached source data on the backend. */
export default function DeleteMyData({ personId, onDeleted }: { personId: string; onDeleted: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function del() {
    if (!window.confirm("Delete all data for this person? This cannot be undone.")) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/api/people/${encodeURIComponent(personId)}`, { method: "DELETE" });
      onDeleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed.");
      setBusy(false);
    }
  }
  return (
    <div className="mt-6 border-t border-stone-200 pt-4 text-sm">
      <p className="text-stone-500">Your data is kept only to build this profile and run dates. You can remove it any time.</p>
      <button onClick={del} disabled={busy} className="mt-2 rounded-lg border border-red-300 px-3 py-1.5 text-red-700 hover:bg-red-50 disabled:opacity-50">
        {busy ? "Deleting..." : "Delete my data"}
      </button>
      {error && <p className="mt-2 text-red-700">{error}</p>}
    </div>
  );
}
