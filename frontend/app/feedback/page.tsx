"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChartBar, Flask, ThumbsDown, TrendDown } from "@phosphor-icons/react";

import { AppPage, EmptyState, InlineError, LoadingRows, Panel, PanelHeader, StatusPill } from "@/components/AppPage";
import { api } from "@/lib/api/client";
import { formatDate, formatDateTime } from "@/lib/format";
import type { FeedbackAnalyticsResponse, NegativeFeedbackItem } from "@/lib/api/types";

const WINDOWS = [7, 30, 90] as const;

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function excerpt(value: string | null | undefined, max = 320): string {
  if (!value) return "No text";
  return value.length > max ? `${value.slice(0, max).trim()}...` : value;
}

function MetricPanel({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  return (
    <Panel className="px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight text-foreground">{value}</p>
          {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
        </div>
        <StatusPill tone={tone}>{label}</StatusPill>
      </div>
    </Panel>
  );
}

function TrendPanel({ analytics }: { analytics: FeedbackAnalyticsResponse }) {
  const recent = analytics.trend.slice(-14);
  const maxTotal = Math.max(1, ...recent.map((bucket) => bucket.total));

  return (
    <Panel>
      <PanelHeader title="Daily trend" description={`${recent.length} most recent buckets`} />
      <div className="divide-y divide-border">
        {recent.map((bucket) => {
          const totalWidth = `${Math.max(3, (bucket.total / maxTotal) * 100)}%`;
          const negativeWidth = `${bucket.total ? (bucket.negative / bucket.total) * 100 : 0}%`;
          return (
            <div key={bucket.date} className="grid gap-3 px-4 py-3 sm:grid-cols-[8rem_minmax(0,1fr)_5rem] sm:items-center">
              <p className="text-xs text-muted-foreground">{formatDate(bucket.date)}</p>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-emerald-400/70" style={{ width: totalWidth }}>
                  <div className="h-full bg-destructive/80" style={{ width: negativeWidth }} />
                </div>
              </div>
              <p className="font-mono text-[11px] text-muted-foreground sm:text-right">
                {bucket.negative}/{bucket.total}
              </p>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function NegativeFeedbackCard({ item }: { item: NegativeFeedbackItem }) {
  return (
    <article className="px-4 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone="danger">negative</StatusPill>
        <Link
          href={`/chat?cid=${item.conversation_id}`}
          className="text-xs font-semibold text-amber-700 hover:text-amber-800 dark:text-amber-300 dark:hover:text-amber-200"
        >
          Conversation #{item.conversation_id}
        </Link>
        <span className="font-mono text-[11px] text-muted-foreground">
          message #{item.message_id}
        </span>
        <span className="text-xs text-muted-foreground">{formatDateTime(item.feedback_created_at)}</span>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Question
          </p>
          <p className="mt-1 text-sm leading-6 text-foreground">{item.question ?? "No prior user message"}</p>
          {item.comment && (
            <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-xs leading-5 text-destructive">
              {item.comment}
            </p>
          )}
        </div>

        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Answer
          </p>
          <p className="mt-1 text-sm leading-6 text-foreground">{excerpt(item.answer)}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <StatusPill>{item.model ?? "unknown model"}</StatusPill>
            <StatusPill>{item.latency_ms ?? 0}ms</StatusPill>
            <StatusPill>{item.citations.length} citations</StatusPill>
          </div>
        </div>
      </div>

      {item.citations.length > 0 && (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {item.citations.slice(0, 4).map((citation) => (
            <div key={`${item.feedback_id}-${citation.marker}-${citation.chunk_id}`} className="rounded-lg bg-muted/50 px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] text-muted-foreground">[{citation.marker}]</span>
                <p className="min-w-0 truncate text-xs font-semibold text-foreground">
                  {citation.document_title}
                </p>
              </div>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                {citation.snippet ?? "Snippet unavailable"}
              </p>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

export default function FeedbackPage() {
  const [days, setDays] = useState<number>(30);

  const analytics = useQuery({
    queryKey: ["feedback-analytics", days],
    queryFn: () => api.getFeedbackAnalytics(days),
  });

  const negative = useQuery({
    queryKey: ["feedback-negative", days],
    queryFn: () => api.listNegativeFeedback({ limit: 25, days }),
  });

  const candidates = useQuery({
    queryKey: ["feedback-eval-candidates", days],
    queryFn: () => api.getFeedbackEvalCandidates({ limit: 25, days }),
  });

  const latestTotal = analytics.data?.trend.at(-1)?.total ?? 0;
  const latestNegative = analytics.data?.trend.at(-1)?.negative ?? 0;

  const candidateDocs = useMemo(() => {
    const docs = new Set<string>();
    candidates.data?.cases.forEach((candidate) => {
      candidate.expected_docs.forEach((doc) => docs.add(doc));
    });
    return Array.from(docs).slice(0, 6);
  }, [candidates.data]);

  return (
    <AppPage
      eyebrow="Quality"
      title="Feedback review"
      description="Track thumbs feedback, inspect negative examples, and stage eval candidates."
      actions={
        <div className="flex gap-1 rounded-lg bg-muted p-1">
          {WINDOWS.map((windowDays) => (
            <button
              key={windowDays}
              type="button"
              onClick={() => setDays(windowDays)}
              className={`h-7 rounded-md px-2.5 text-xs font-semibold transition-colors ${
                days === windowDays ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {windowDays}d
            </button>
          ))}
        </div>
      }
    >
      {analytics.error && (
        <InlineError message={analytics.error instanceof Error ? analytics.error.message : "Feedback analytics failed"} />
      )}

      {analytics.isLoading && (
        <div className="grid gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Panel key={index} className="px-4 py-5">
              <div className="h-4 w-24 rounded skeleton-shimmer" />
              <div className="mt-3 h-8 w-16 rounded skeleton-shimmer" />
            </Panel>
          ))}
        </div>
      )}

      {analytics.data && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <MetricPanel label="Total" value={String(analytics.data.total)} detail={`${analytics.data.window_days} day window`} />
            <MetricPanel label="Negative" value={String(analytics.data.negative)} detail={percent(analytics.data.negative_rate)} tone={analytics.data.negative ? "danger" : "success"} />
            <MetricPanel label="Positive" value={String(analytics.data.positive)} detail={`latest ${formatDateTime(analytics.data.latest_feedback_at)}`} tone="success" />
            <MetricPanel label="Today" value={`${latestNegative}/${latestTotal}`} detail="negative / total" tone={latestNegative ? "warning" : "neutral"} />
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
            <TrendPanel analytics={analytics.data} />

            <Panel>
              <PanelHeader title="Concentrations" description="Models and cited documents with negative feedback" />
              <div className="divide-y divide-border">
                {analytics.data.by_model.slice(0, 4).map((model) => (
                  <div key={model.model} className="px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-semibold text-foreground">{model.model}</p>
                      <StatusPill tone={model.negative ? "danger" : "success"}>{percent(model.negative_rate)}</StatusPill>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {model.negative} negative / {model.total} total
                    </p>
                  </div>
                ))}
                {analytics.data.top_negative_documents.slice(0, 4).map((doc) => (
                  <div key={`${doc.source_id}-${doc.document_id}`} className="px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-semibold text-foreground">{doc.document_title}</p>
                      <StatusPill tone="danger">{doc.negative}</StatusPill>
                    </div>
                    <p className="mt-1 truncate text-xs text-muted-foreground">{doc.source_name}</p>
                  </div>
                ))}
                {analytics.data.by_model.length === 0 && analytics.data.top_negative_documents.length === 0 && (
                  <EmptyState icon={<ChartBar size={20} />} title="No feedback in this window" />
                )}
              </div>
            </Panel>
          </div>
        </>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(20rem,0.65fr)]">
        <Panel>
          <PanelHeader
            title="Negative review queue"
            description={`${negative.data?.total ?? 0} matching examples`}
            actions={<ThumbsDown size={16} className="text-destructive" />}
          />
          {negative.isLoading && <LoadingRows rows={5} />}
          {negative.error && !negative.isLoading && (
            <div className="p-4">
              <InlineError message={negative.error instanceof Error ? negative.error.message : "Negative feedback failed"} />
            </div>
          )}
          {negative.data?.items.length === 0 && (
            <EmptyState icon={<TrendDown size={20} />} title="No negative feedback in this window" />
          )}
          {negative.data && negative.data.items.length > 0 && (
            <div className="divide-y divide-border">
              {negative.data.items.map((item) => (
                <NegativeFeedbackCard key={item.feedback_id} item={item} />
              ))}
            </div>
          )}
        </Panel>

        <Panel>
          <PanelHeader
            title="Eval candidates"
            description={`${candidates.data?.cases.length ?? 0} staged cases`}
            actions={<Flask size={16} className="text-amber-500" />}
          />
          {candidates.isLoading && <LoadingRows rows={4} />}
          {candidates.error && !candidates.isLoading && (
            <div className="p-4">
              <InlineError message={candidates.error instanceof Error ? candidates.error.message : "Eval candidates failed"} />
            </div>
          )}
          {candidates.data?.cases.length === 0 && (
            <EmptyState icon={<Flask size={20} />} title="No candidates in this window" />
          )}
          {candidates.data && candidates.data.cases.length > 0 && (
            <div className="divide-y divide-border">
              {candidates.data.cases.slice(0, 8).map((candidate) => (
                <div key={candidate.id} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-mono text-[11px] font-semibold text-foreground">{candidate.id}</p>
                    <StatusPill tone="warning">review</StatusPill>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                    {candidate.question || "Missing question"}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {candidate.expected_docs.map((doc) => (
                      <span key={`${candidate.id}-${doc}`} className="inline-flex h-5 items-center rounded-md bg-muted px-2 text-[11px] font-semibold text-muted-foreground">
                        {doc}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
              {candidateDocs.length > 0 && (
                <div className="px-4 py-3">
                  <p className="text-xs font-semibold text-muted-foreground">Candidate docs</p>
                  <p className="mt-1 text-xs leading-5 text-foreground">{candidateDocs.join(", ")}</p>
                </div>
              )}
            </div>
          )}
        </Panel>
      </div>
    </AppPage>
  );
}
