import { DemoRankings } from "@/components/Demo";
import { Shell } from "@/components/ui";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Shell wide demo>
      <DemoRankings id={decodeURIComponent(id)} />
    </Shell>
  );
}
