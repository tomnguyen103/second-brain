import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { WarningCircle } from "@phosphor-icons/react";

import { cn } from "@/lib/utils";

const focusRing =
  "focus-visible:border-primary focus-visible:ring-3 focus-visible:ring-primary/25 focus-visible:outline-none";

const controlBase =
  "w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground transition-colors placeholder:text-muted-foreground hover:bg-surface-hover/60 disabled:cursor-not-allowed disabled:opacity-50";

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
      <header className="shrink-0 border-b border-grid bg-background px-4 py-4 md:px-6">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-primary">
              {eyebrow}
            </p>
            <h1 className="mt-1 text-xl font-semibold leading-tight text-foreground md:text-2xl">
              {title}
            </h1>
            {description && (
              <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
                {description}
              </p>
            )}
          </div>
          {actions && <div className="shrink-0 sm:self-center">{actions}</div>}
        </div>
      </header>
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-4 md:px-6 md:py-5">
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
    <section className={cn("rounded-lg border border-border bg-card", className)}>
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
    <div className="flex items-start justify-between gap-4 border-b border-grid px-5 py-4">
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
    <div className={cn("flex flex-col items-center justify-center px-6 py-12 text-center", className)}>
      {icon && (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/25">
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
    <div className="flex items-start gap-2 rounded-lg border border-destructive/30 border-l-4 bg-destructive/10 px-3 py-2 text-xs text-destructive">
      <WarningCircle size={14} weight="bold" className="mt-0.5 shrink-0" />
      <span className="leading-5">{message}</span>
    </div>
  );
}

export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="divide-y divide-border/80" aria-hidden="true">
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
    success: "bg-live/10 text-live ring-live/30",
    warning: "bg-primary/10 text-primary ring-primary/25",
    danger: "bg-destructive/10 text-destructive ring-destructive/20",
  };
  return (
    <span className={cn("inline-flex h-5 items-center rounded-md px-2 text-[11px] font-semibold ring-1", tones[tone])}>
      {children}
    </span>
  );
}

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("flex flex-col gap-1.5 text-xs font-medium text-muted-foreground", className)}>
      <span>{label}</span>
      {children}
      {hint && <span className="text-[11px] font-normal leading-4 text-muted-foreground/75">{hint}</span>}
    </label>
  );
}

export function TextInput({ className, ...props }: ComponentPropsWithoutRef<"input">) {
  return (
    <input
      className={cn(controlBase, "h-9", focusRing, className)}
      {...props}
    />
  );
}

export function TextArea({
  className,
  ...props
}: ComponentPropsWithoutRef<"textarea">) {
  return (
    <textarea
      className={cn(controlBase, "resize-y py-2.5 leading-6", focusRing, className)}
      {...props}
    />
  );
}

export function SelectControl({
  className,
  ...props
}: ComponentPropsWithoutRef<"select">) {
  return (
    <select
      className={cn(controlBase, "h-9", focusRing, className)}
      {...props}
    />
  );
}

export function AppButton({
  className,
  variant = "primary",
  size = "default",
  ...props
}: ComponentPropsWithoutRef<"button"> & {
  variant?: "primary" | "secondary" | "quiet" | "danger" | "dangerSoft";
  size?: "default" | "sm" | "icon";
}) {
  const variants = {
    primary:
      "bg-primary text-primary-foreground shadow-sm shadow-primary/20 hover:bg-primary/90",
    secondary:
      "border border-border bg-background text-foreground hover:bg-surface-hover",
    quiet:
      "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
    danger:
      "bg-destructive text-background hover:bg-destructive/90",
    dangerSoft:
      "bg-destructive/10 text-destructive hover:bg-destructive/20",
  };
  const sizes = {
    default: "h-9 gap-1.5 px-3 text-sm",
    sm: "h-8 gap-1.5 px-2.5 text-xs",
    icon: "h-8 w-8 p-0",
  };
  return (
    <button
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-lg font-semibold transition-all active:translate-y-px disabled:cursor-not-allowed disabled:opacity-40",
        focusRing,
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  className,
}: {
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex rounded-lg border border-border bg-background p-1", className)} role="group">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            "h-8 flex-1 rounded-md px-2 text-xs font-semibold transition-colors",
            value === option.value
              ? "bg-primary text-primary-foreground shadow-sm shadow-primary/20"
              : "text-muted-foreground hover:text-foreground",
            focusRing,
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
