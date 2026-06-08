import Link from "next/link";
import { redirect } from "next/navigation";
import { STATIC_DEMO_MODE } from "@/lib/demo/config";

export default function Home() {
  if (!STATIC_DEMO_MODE) {
    redirect("/chat");
  }

  return (
    <div className="flex h-full items-center justify-center bg-background px-4 text-foreground">
      <section className="w-full max-w-md rounded-lg border border-border bg-card p-5 text-center">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
          Second Brain
        </p>
        <h1 className="mt-2 text-xl font-semibold text-foreground">
          Open the workspace
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Continue to the chat workspace for cited answers over the public-safe demo corpus.
        </p>
        <Link
          href="/chat"
          className="mt-5 inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25"
        >
          Open chat
        </Link>
      </section>
    </div>
  );
}
