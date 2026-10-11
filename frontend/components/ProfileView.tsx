import Link from "next/link";
import type { Claim, Profile, Source, SourceStatus, Trait } from "@/lib/types";
import { Badge, Card, ConfidenceBar, SourceBadge, SyntheticBadge } from "./ui";

const STATUS_NOTE: Record<SourceStatus, { tone: "green" | "amber" | "red"; text: (s: Source) => string }> = {
  ok: { tone: "green", text: (s) => `${label(s)} was readable.` },
  thin: { tone: "amber", text: (s) => `${label(s)} had very little public content, so fields drawn from it carry lower confidence.` },
  not_readable: { tone: "red", text: (s) => `${label(s)} was private or login-walled and was not read. Nothing was inferred from it and no other route was tried.` },
};
const label = (s: Source) => (s === "linkedin" ? "LinkedIn" : "Instagram");

function ClaimList({ claims }: { claims: Claim[] }) {
  if (!claims?.length) return <p className="text-sm text-stone-400">Nothing supported by the sources.</p>;
  return (
    <ul className="space-y-3">
      {claims.map((c, i) => (
        <li key={i} className="rounded-lg border border-stone-100 bg-stone-50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium">{c.value}</span>
            <div className="flex items-center gap-2">
              <SourceBadge source={c.source} />
              <ConfidenceBar value={c.confidence} />
            </div>
          </div>
          <blockquote className="mt-2 border-l-2 border-stone-300 pl-3 text-sm italic text-stone-600">&ldquo;{c.evidence}&rdquo;</blockquote>
        </li>
      ))}
    </ul>
  );
}

function TraitRow({ name, t }: { name: string; t: Trait }) {
  return (
    <div className="rounded-lg border border-stone-100 bg-stone-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="text-xs uppercase tracking-wide text-stone-500">{name}</span>
          <p className="font-medium">{t.value}</p>
        </div>
        <ConfidenceBar value={t.confidence} />
      </div>
      <blockquote className="mt-2 border-l-2 border-stone-300 pl-3 text-sm italic text-stone-600">&ldquo;{t.evidence}&rdquo;</blockquote>
    </div>
  );
}

export default function ProfileView({
  personId,
  name,
  synthetic,
  profile,
  base = "",
}: {
  personId: string;
  name: string;
  synthetic?: boolean;
  profile: Profile;
  base?: string;
}) {
  const gap = Math.round(profile.persona_gap.score * 100);
  const bothSources = profile.source_status.linkedin !== "not_readable" && profile.source_status.instagram !== "not_readable";
  const idm = Math.round(profile.identity_match.score * 100);
  const lowIdentity = profile.identity_match.score < 0.6;
  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight">{name}</h1>
          {synthetic && <SyntheticBadge />}
        </div>
        <p className="mt-2 text-stone-700">{profile.summary}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link href={`${base}/rankings/${encodeURIComponent(personId)}`} className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90">
            See matches
          </Link>
        </div>
      </div>

      <Card title="Source status">
        <ul className="space-y-2 text-sm">
          {(["linkedin", "instagram"] as Source[]).map((s) => {
            const st = profile.source_status[s];
            const n = STATUS_NOTE[st];
            return (
              <li key={s} className="flex flex-wrap items-center gap-2">
                <SourceBadge source={s} />
                <Badge tone={n.tone}>{st.replace("_", " ")}</Badge>
                <span className="text-stone-600">{n.text(s)}</span>
              </li>
            );
          })}
        </ul>
        <p className="mt-3 text-xs text-stone-400">Only LinkedIn and public Instagram are ever used.</p>
      </Card>

      <Card title="Identity cross-check">
        <div className="flex flex-wrap items-center gap-3">
          <ConfidenceBar value={profile.identity_match.score} />
          <span className="text-sm text-stone-600">{profile.identity_match.reason}</span>
        </div>
        {lowIdentity && (
          <p className="mt-3 rounded-md bg-amber-50 p-2 text-sm text-amber-800">
            Low match ({idm}%): the Instagram account may not belong to the same person as the LinkedIn profile.
          </p>
        )}
      </Card>

      <Card title="Public self vs. off-duty self" right={bothSources ? <Badge tone={gap >= 50 ? "amber" : "stone"}>Gap {gap}%</Badge> : <Badge tone="stone">Not enough data</Badge>}>
        <div className="grid gap-3 sm:grid-cols-2">
          {([
            ["linkedin", "LinkedIn persona", profile.linkedin_persona],
            ["instagram", "Instagram persona", profile.instagram_persona],
          ] as const).map(([s, title, p]) => (
            <div key={s} className="rounded-lg border border-stone-100 bg-stone-50 p-3">
              <div className="mb-1 flex items-center gap-2">
                <SourceBadge source={s} />
                <span className="text-sm font-medium">{title}</span>
              </div>
              <p className="text-sm text-stone-700">{p.summary}</p>
              {p.evidence.length > 0 && (
                <ul className="mt-2 list-disc space-y-1 pl-4 text-xs italic text-stone-500">
                  {p.evidence.map((e, i) => <li key={i}>&ldquo;{e}&rdquo;</li>)}
                </ul>
              )}
            </div>
          ))}
        </div>
        {!bothSources ? null : (
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-stone-200" aria-hidden>
            <div className="h-full rounded-full bg-gradient-to-r from-sky-400 to-pink-500" style={{ width: `${gap}%` }} />
          </div>
        )}
        <p className="mt-2 text-sm text-stone-600">{profile.persona_gap.description}</p>
      </Card>

      <div className="grid gap-5 md:grid-cols-2">
        <Card title="Needs"><ClaimList claims={profile.needs} /></Card>
        <Card title="What they want in a partner"><ClaimList claims={profile.wants_in_partner} /></Card>
        <Card title="Hobbies"><ClaimList claims={profile.hobbies} /></Card>
        <Card title="Interests"><ClaimList claims={profile.interests} /></Card>
        <Card title="Values"><ClaimList claims={profile.values} /></Card>
        <Card title="Lifestyle"><ClaimList claims={profile.lifestyle} /></Card>
      </div>

      <Card title="Style">
        <div className="grid gap-3 md:grid-cols-3">
          <TraitRow name="Communication" t={profile.communication_style} />
          <TraitRow name="Humor" t={profile.humor} />
          <TraitRow name="Energy" t={profile.energy} />
        </div>
      </Card>
    </div>
  );
}
