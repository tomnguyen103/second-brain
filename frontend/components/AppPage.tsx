import type { ReactNode } from "react";
import { WarningCircle } from "@phosphor-icons/react";

import { cn } from "@/lib/utils";

export function AppPage({
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      <header className="shrink-0 border-b border-border bg-card/50 px-5 py-4 backdrop-blur-sm">
        <div className="mx-auto flex w-full max-w-6xl items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              {eyebrow}
            </p>
            <h1 className="mt-1 text-2xl font-semibold leading-tight tracking-tight text-foreground">
              {title}
            </h1>
            {description && (
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                {description}
              </p>
            )}
          </div>
          {actions && <div className="shrink-0">{actions}</div>}
        </div>
      </header>
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-5 py-5">
          {children}
        </div>
      </div>
    </div>
  );
}

export function Panel({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn("rounded-xl bg-card ring-1 ring-border", className)}>
      {children}
    </section>
  );
}

export function PanelHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold leading-5 tracking-tight text-foreground">
          {title}
        </h2>
        {description && <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="shrink-0">{actions}</div>}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  className,
}: {
  icon?: ReactNode;
  title: string;
  body?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-14 text-center", className)}>
      {icon && (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-muted-foreground">
          {icon}
        </div>
      )}
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {body && <p className="mt-1 max-w-sm text-xs leading-5 text-muted-foreground">{body}</p>}
    </div>
  );
}

export function InlineError({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
      <WarningCircle size={14} weight="bold" className="mt-0.5 shrink-0" />
      <span className="leading-5">{message}</span>
    </div>
  );
}

export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="divide-y divide-border">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="px-4 py-4">
          <div className="h-3.5 w-2/5 rounded skeleton-shimmer" />
          <div className="mt-2 h-3 w-4/5 rounded skeleton-shimmer" />
        </div>
      ))}
    </div>
  );
}

export function StatusPill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  const tones = {
    neutral: "bg-muted text-muted-foreground ring-border",
    success: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:ring-emerald-900/60",
    warning: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/30 dark:text-amber-300 dark:ring-amber-900/60",
    danger: "bg-destructive/10 text-destructive ring-destructive/20",
  };
  return (
    <span className={cn("inline-flex h-5 items-center rounded-md px-2 text-[11px] font-semibold ring-1", tones[tone])}>
      {children}
    </span>
  );
}
