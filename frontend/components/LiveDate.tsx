"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL, api, type PersonRecord } from "@/lib/api";
import type { DateFlag, DateRecord, DateTurn } from "@/lib/types";
import DateView from "./DateView";
import { ErrorBox, Spinner } from "./ui";

const isFinal = (d: DateRecord) => d.status === "done" || d.status === "failed";

function upsertTurn(d: DateRecord, t: Partial<DateTurn> & { idx: number }): DateRecord {
  const turns = [...d.turns];
  const i = turns.findIndex((x) => x.idx === t.idx);
  const merged: DateTurn = { speaker: "", stage: "", public_text: "", private_note: "", chemistry: 0, flags: [], ...(i >= 0 ? turns[i] : {}), ...t } as DateTurn;
  if (!Array.isArray(merged.flags)) merged.flags = [];
  if (i >= 0) turns[i] = merged;
  else turns.push(merged);
  return { ...d, status: d.status === "pending" ? "running" : d.status, turns };
}

export default function LiveDate({ dateId }: { dateId: string }) {
  const [date, setDate] = useState<DateRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [synthetic, setSynthetic] = useState<Record<string, boolean>>({});
  const [conn, setConn] = useState<"connecting" | "stream" | "polling" | "closed">("connecting");
  const namesFor = useRef<string>("");

  const fetchDate = useCallback(async () => {
    const d = await api<DateRecord>(`/api/dates/${encodeURIComponent(dateId)}`);
    setDate(d);
    setError(null);
    return d;
  }, [dateId]);

  // names for the two people
  useEffect(() => {
    if (!date) return;
    const key = `${date.person_a}|${date.person_b}`;
    if (namesFor.current === key) return;
    namesFor.current = key;
    for (const id of [date.person_a, date.person_b]) {
      api<PersonRecord>(`/api/people/${encodeURIComponent(id)}`)
        .then((p) => {
          if (p.display_name) setNames((n) => ({ ...n, [id]: p.display_name as string }));
          if (p.synthetic) setSynthetic((s) => ({ ...s, [id]: true }));
        })
        .catch(() => undefined);
    }
  }, [date]);

  useEffect(() => {
    let alive = true;
    let es: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = () => {
      setConn("polling");
      const tick = async () => {
        try {
          const d = await fetchDate();
          if (!alive) return;
          if (isFinal(d)) return setConn("closed");
        } catch (e) {
          if (alive) setError(e instanceof Error ? e.message : String(e));
        }
        if (alive) timer = setTimeout(tick, 2000);
      };
      tick();
    };

    (async () => {
      let initial: DateRecord;
      try {
        initial = await fetchDate();
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
        return;
      }
      if (!alive) return;
      if (isFinal(initial)) return setConn("closed");
      if (typeof EventSource === "undefined") return poll();

      es = new EventSource(`${API_URL}/api/dates/${encodeURIComponent(dateId)}/stream`);
      es.onopen = () => alive && setConn("stream");
      const parse = (e: MessageEvent): Record<string, unknown> | null => {
        try {
          const j = JSON.parse(e.data);
          return j && typeof j === "object" && "data" in j && typeof j.data === "object" && "event" in j ? j.data : j;
        } catch {
          return null;
        }
      };
      es.addEventListener("turn", (e) => {
        const d = parse(e as MessageEvent);
        if (d && typeof d.idx === "number") setDate((cur) => (cur ? upsertTurn(cur, d as unknown as DateTurn) : cur));
      });
      es.addEventListener("chemistry", (e) => {
        const d = parse(e as MessageEvent);
        if (d && typeof d.idx === "number" && typeof d.chemistry === "number") setDate((cur) => (cur ? upsertTurn(cur, { idx: d.idx as number, chemistry: d.chemistry as number }) : cur));
      });
      es.addEventListener("flag", (e) => {
        const d = parse(e as MessageEvent);
        if (!d || typeof d.idx !== "number") return;
        const f = (d.flag && typeof d.flag === "object" ? d.flag : d) as unknown as DateFlag;
        if (!f.type) return;
        setDate((cur) => {
          if (!cur) return cur;
          const t = cur.turns.find((x) => x.idx === d.idx);
          const flags = [...(t?.flags ?? []), { type: f.type, note: f.note ?? "" }];
          const flagged = f.type === "unsupported_claim" ? [...new Set([...cur.flagged_turns, d.idx as number])] : cur.flagged_turns;
          return { ...upsertTurn(cur, { idx: d.idx as number, flags }), flagged_turns: flagged };
        });
      });
      es.addEventListener("done", () => {
        es?.close();
        if (!alive) return;
        setConn("closed");
        fetchDate().catch(() => undefined);
      });
      es.onerror = () => {
        // browsers auto-reconnect; if the stream is dead, fall back to polling GET
        if (!alive || es?.readyState !== EventSource.CLOSED) return;
        es.close();
        poll();
      };
    })();

    return () => {
      alive = false;
      es?.close();
      if (timer) clearTimeout(timer);
    };
  }, [dateId, fetchDate]);

  if (error && !date) return <ErrorBox message={error} onRetry={() => fetchDate().catch((e) => setError(e.message))} />;
  if (!date) return <Spinner label="Opening the date..." />;
  const connection = conn === "stream" ? "Streaming live" : conn === "polling" ? "Live stream unavailable; refreshing every 2s" : conn === "connecting" ? "Connecting..." : undefined;
  return (
    <>
      {error && <div className="mb-4"><ErrorBox message={error} /></div>}
      <DateView date={date} names={names} synthetic={synthetic} live connection={connection} />
    </>
  );
}
