import { DemoProfile } from "@/components/Demo";
import { Shell } from "@/components/ui";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Shell demo>
      <DemoProfile id={decodeURIComponent(id)} />
    </Shell>
  );
}
