import LiveDate from "@/components/LiveDate";
import { Shell } from "@/components/ui";

export default async function Page({ params }: { params: Promise<{ pairId: string }> }) {
  const { pairId } = await params;
  return (
    <Shell wide>
      <LiveDate dateId={pairId} />
    </Shell>
  );
}
