import { DemoDate } from "@/components/Demo";
import { Shell } from "@/components/ui";

export default async function Page({ params }: { params: Promise<{ pairId: string }> }) {
  const { pairId } = await params;
  return (
    <Shell wide demo>
      <DemoDate id={decodeURIComponent(pairId)} />
    </Shell>
  );
}
