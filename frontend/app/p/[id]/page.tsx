import LiveProfile from "@/components/LiveProfile";
import { Shell } from "@/components/ui";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Shell>
      <LiveProfile id={id} />
    </Shell>
  );
}
