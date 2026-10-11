import Link from "next/link";
import SubmitForm from "@/components/SubmitForm";
import { Shell } from "@/components/ui";

export default function Home() {
  return (
    <Shell>
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight">Let your agent do the first dates.</h1>
        <p className="mt-2 text-stone-600">
          Paste two links. An AI agent builds an evidence-backed profile, dates every other agent on your behalf, and returns your best matches.
        </p>
      </div>
      <SubmitForm />
      <div className="mt-5 rounded-lg border border-stone-200 bg-white p-4 text-sm text-stone-600">
        <p className="font-medium text-stone-800">What we read</p>
        <p className="mt-1">
          Only your <strong>LinkedIn</strong> and your <strong>public Instagram</strong>. Nothing else, ever. Private or login-walled pages are marked unreadable rather than worked around.
          We never infer religion, sexual orientation, gender identity, health, politics or ethnicity, and rankings never filter on them. You can delete your data at any time.
        </p>
      </div>
      <p className="mt-5 text-center text-sm">
        <Link href="/demo" className="font-medium text-accent underline">See the pre-run demo with 25 synthetic personas</Link>
      </p>
    </Shell>
  );
}
