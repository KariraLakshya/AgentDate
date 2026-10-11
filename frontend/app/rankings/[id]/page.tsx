import LiveRankings from "@/components/LiveRankings";
import { Shell } from "@/components/ui";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Shell wide>
      <LiveRankings id={id} />
    </Shell>
  );
}
