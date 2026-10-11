"use client";
import { useCallback, useMemo } from "react";
import { api, type PoolMatrix, type RankingMatch, type RankingsResponse } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import type { Briefing } from "@/lib/types";
import RankingsView from "./RankingsView";
import { Empty, ErrorBox, Spinner } from "./ui";

export default function LiveRankings({ id }: { id: string }) {
  const rankings = useAsync(() => api<RankingsResponse>(`/api/people/${encodeURIComponent(id)}/rankings`), [id]);
  // matrix + briefing are optional extras: a failure should not hide the ranked list
  const pool = useAsync(() => api<PoolMatrix>("/api/pool/matrix").catch(() => null), [id]);
  const brief = useAsync(() => api<Briefing>(`/api/people/${encodeURIComponent(id)}/briefing`).catch(() => null), [id]);

  const matches: RankingMatch[] = useMemo(() => {
    const r = rankings.data as unknown;
    if (!r) return [];
    const list: any[] = Array.isArray(r) ? r : (r as any).matches ?? (r as any).rankings ?? [];
    // backend rows carry dimension_scores (my rating) / dimension_scores_received (theirs) instead of mine/theirs
    const rub = (d: any, meet: any): any => (d ? { ...d, would_meet_again: !!meet, verdict: "" } : null);
    return list.map((m) => ({
      ...m,
      mine: m.mine ?? rub(m.dimension_scores, m.would_meet_again_me),
      theirs: m.theirs ?? rub(m.dimension_scores_received, m.would_meet_again_them),
      best_moment: typeof m.best_moment === "string" ? m.best_moment : m.best_moment?.quote ?? m.explanation,
    })) as RankingMatch[];
  }, [rankings.data]);

  const names = useMemo(() => {
    const n: Record<string, string> = {};
    const syn: Record<string, boolean> = {};
    const pm = pool.data as any;
    pm?.order?.forEach((pid: string, i: number) => {
      if (pm.names?.[i] ?? pm.names?.[pid]) n[pid] = pm.names[i] ?? pm.names[pid];
    });
    pool.data?.people?.forEach((p) => {
      n[p.id] = p.display_name;
      if (p.synthetic) syn[p.id] = true;
    });
    matches.forEach((m) => {
      if (m.display_name) n[m.person_id] = m.display_name;
      if (m.synthetic) syn[m.person_id] = true;
    });
    if (!Array.isArray(rankings.data) && rankings.data?.person) n[rankings.data.person.id] = rankings.data.person.display_name;
    return { n, syn };
  }, [pool.data, matches, rankings.data]);

  const matrix = pool.data?.matrix ?? [];
  const matrixFor = useCallback(() => matrix, [matrix]);
  const onAsk = useCallback(
    async (question: string) => {
      const r = await api<{ answer: string }>(`/api/people/${encodeURIComponent(id)}/ask`, { method: "POST", body: JSON.stringify({ question }) });
      return r.answer;
    },
    [id],
  );

  if (rankings.loading) return <Spinner label="Loading matches..." />;
  if (rankings.error) return <ErrorBox message={rankings.error} onRetry={rankings.reload} />;
  if (matches.length === 0) return <Empty>No rankings yet. Dates run after your profile is ready; check back soon.</Empty>;

  return (
    <RankingsView
      personId={id}
      entries={matches}
      names={names.n}
      synthetic={names.syn}
      order={pool.data?.order ?? []}
      matrixFor={matrixFor}
      stablePairs={pool.data?.stable_pairs ?? []}
      briefing={brief.data}
      onAsk={onAsk}
    />
  );
}
