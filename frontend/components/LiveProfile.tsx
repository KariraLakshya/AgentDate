"use client";
import { FAILED_STATUSES, TERMINAL_STATUSES, api, type PersonRecord } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import ProfileView from "./ProfileView";
import { Empty, ErrorBox, Spinner } from "./ui";

const STEPS: Record<string, string> = {
  pending: "Queued",
  queued: "Queued",
  ingesting: "Reading your LinkedIn and public Instagram",
  analyzing: "The analyst agent is building your profile",
};

export default function LiveProfile({ id }: { id: string }) {
  const { data, error, loading } = usePolling(
    () => api<PersonRecord>(`/api/people/${encodeURIComponent(id)}`),
    (p) => (p.profile !== null && TERMINAL_STATUSES.includes(p.status)) || FAILED_STATUSES.includes(p.status) || p.status === "not_readable" || p.status === "deleted",
    2000,
    [id],
  );
  if (loading && !data) return <Spinner label="Loading profile..." />;
  if (!data) return <ErrorBox message={error ?? "Profile not found."} />;
  if (data.status === "deleted") return <Empty>This person&rsquo;s data has been deleted.</Empty>;
  if (data.status === "not_readable")
    return <ErrorBox message="We could not read either source. The LinkedIn or Instagram page may be private or login-walled, and we never try other routes. Make both public, or check the links, then submit again." />;
  if (FAILED_STATUSES.includes(data.status)) return <ErrorBox message={data.error ?? "Profile generation failed. Try submitting again."} />;
  if (!data.profile) {
    return (
      <div>
        <Spinner label={STEPS[data.status] ?? `Working (${data.status})...`} />
        <p className="text-sm text-stone-500">This takes a minute. The page updates by itself.</p>
        {error && <p className="mt-2 text-sm text-amber-700">Connection hiccup: {error}. Retrying...</p>}
      </div>
    );
  }
  return <ProfileView personId={data.id} name={data.display_name || "Your profile"} synthetic={data.synthetic} profile={data.profile} />;
}
