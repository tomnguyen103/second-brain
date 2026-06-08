"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { LockKey, ShieldCheck } from "@phosphor-icons/react";

import {
  DEMO_ACCESS_ENABLED,
  DEMO_ACCESS_HASH,
  DEMO_ACCESS_STORAGE_KEY,
  STATIC_DEMO_MODE,
} from "@/lib/demo/config";

type AccessState = "checking" | "granted" | "locked";

async function sha256Hex(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await window.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function DemoAccessGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AccessState>(
    STATIC_DEMO_MODE && DEMO_ACCESS_ENABLED ? "checking" : "granted",
  );
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!STATIC_DEMO_MODE || !DEMO_ACCESS_ENABLED) return;

    const saved = window.localStorage.getItem(DEMO_ACCESS_STORAGE_KEY);
    const frame = window.requestAnimationFrame(() => {
      setState(saved === DEMO_ACCESS_HASH ? "granted" : "locked");
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const submit = async () => {
    setError(null);
    const normalized = passcode.trim();
    if (!normalized) {
      setError("Enter the demo passcode.");
      return;
    }

    if (!window.crypto?.subtle) {
      setError("This browser cannot verify the passcode locally.");
      return;
    }

    const hash = await sha256Hex(normalized);
    if (hash === DEMO_ACCESS_HASH) {
      window.localStorage.setItem(DEMO_ACCESS_STORAGE_KEY, hash);
      setState("granted");
      return;
    }
    setError("Passcode did not match.");
  };

  if (state === "granted") return <>{children}</>;

  return (
    <div className="flex h-full w-full items-center justify-center bg-background px-4 py-6 text-foreground">
      <section className="w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-2xl shadow-black/20">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/25">
            <LockKey size={20} weight="bold" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
              Portfolio Demo
            </p>
            <h1 className="mt-1 text-lg font-semibold leading-6 text-foreground">
              Second Brain static preview
            </h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              This read-only Netlify build uses a public-safe corpus and a local passcode check for casual access control.
            </p>
          </div>
        </div>

        <form
          className="mt-5 grid gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
            <span>Demo passcode</span>
            <input
              type="password"
              value={passcode}
              onChange={(event) => setPasscode(event.target.value)}
              autoComplete="off"
              className="h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground hover:bg-surface-hover/60 focus:border-primary focus:ring-3 focus:ring-primary/25"
              placeholder="Enter passcode"
            />
          </label>
          {error && (
            <p className="rounded-lg border border-destructive/25 bg-destructive/10 px-3 py-2 text-xs leading-5 text-destructive">
              {error}
            </p>
          )}
          <button
            type="submit"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25"
          >
            <ShieldCheck size={15} weight="bold" />
            Open demo
          </button>
        </form>

        <p className="mt-4 text-[11px] leading-5 text-muted-foreground">
          The passcode gate is not a security boundary. No private notes, API keys, database URLs, or admin secrets are included in this static build.
        </p>
      </section>
    </div>
  );
}
