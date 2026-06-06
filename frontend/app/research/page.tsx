"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Flask, MagnifyingGlass, PlusCircle } from "@phosphor-icons/react";

import { AppButton, AppPage, EmptyState, Field, InlineError, LoadingRows, Panel, PanelHeader, StatusPill, TextArea } from "@/components/AppPage";
import { api } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { queryClient } from "@/lib/query-client";
import type { JobStatus, ResearchJob } from "@/lib/api/types";

function statusTone(status: JobStatus): "neutral" | "success" | "warning" | "danger" {
  if (status === "done") return "success";
  if (status === "failed") return "danger";
  if (status === "running" || status === "queued") return "warning";
  return "neutral";
}

function resultLine(job: ResearchJob): string {
  if (job.last_error) return job.last_error;
  if (!job.result) return "Waiting for worker result";
  const status = typeof job.result.status === "string" ? job.result.status : "stored";
  const doc = typeof job.result.document_id === "number" ? `document #${job.result.document_id}` : "document pending";
  const evidence = typeof job.result.evidence_count === "number" ? ` / ${job.result.evidence_count} sources` : "";
  return `${status} / ${doc}${evidence}`;
}

export default function ResearchPage() {
  const [topic, setTopic] = useState("");
  const [sourceUrls, setSourceUrls] = useState("");
  const [sourceText, setSourceText] = useState("");

  const jobs = useQuery({
    queryKey: ["research-jobs"],
    queryFn: () => api.listResearchJobs(30),
    refetchInterval: 5_000,
  });

  const enqueue = useMutation({
    mutationFn: () => {
      const urls = sourceUrls
        .split(/\r?\n/)
        .map((url) => url.trim())
        .filter(Boolean);
      const snippets = sourceText.trim()
        ? [{ title: "Provided source", text: sourceText.trim() }]
        : [];
      return api.enqueueResearchJob({
        topic: topic.trim(),
        ...(urls.length ? { source_urls: urls } : {}),
        ...(snippets.length ? { source_texts: snippets } : {}),
      });
    },
    onSuccess: () => {
      setTopic("");
      setSourceUrls("");
      setSourceText("");
      queryClient.invalidateQueries({ queryKey: ["research-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  return (
    <AppPage
      eyebrow="Research"
      title="Queued research"
      description="Trigger durable research jobs and watch their status."
    >
      <div className="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="New job" />
          <div className="space-y-3 p-4">
            {enqueue.error && (
              <InlineError message={enqueue.error instanceof Error ? enqueue.error.message : "Research job failed"} />
            )}
            <Field label="Topic">
              <TextArea
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                className="min-h-32"
                placeholder="Research topic"
              />
            </Field>
            <Field label="Source URLs">
              <TextArea
                value={sourceUrls}
                onChange={(event) => setSourceUrls(event.target.value)}
                className="min-h-20"
                placeholder="One public URL per line"
              />
            </Field>
            <Field label="Source text">
              <TextArea
                value={sourceText}
                onChange={(event) => setSourceText(event.target.value)}
                className="min-h-28"
                placeholder="Paste source excerpt"
              />
            </Field>
            <AppButton
              type="button"
              onClick={() => enqueue.mutate()}
              disabled={!topic.trim() || enqueue.isPending}
              className="w-full"
            >
              <PlusCircle size={15} weight="bold" /> {enqueue.isPending ? "Queuing" : "Queue research"}
            </AppButton>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Jobs" />
          {jobs.isLoading && <LoadingRows rows={5} />}
          {jobs.error && !jobs.isLoading && (
            <div className="p-4">
              <InlineError message={jobs.error instanceof Error ? jobs.error.message : "Research jobs failed"} />
            </div>
          )}
          {jobs.data?.jobs.length === 0 && (
            <EmptyState
              icon={<Flask size={20} />}
              title="No research jobs"
              body="Queue a topic to create a searchable research note."
            />
          )}
          {jobs.data && jobs.data.jobs.length > 0 && (
            <div className="divide-y divide-border">
              {jobs.data.jobs.map((job) => (
                <div key={job.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill tone={statusTone(job.status)}>{job.status}</StatusPill>
                    <p className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">
                      {job.topic ?? "Untitled research"}
                    </p>
                    <span className="font-mono text-[11px] text-muted-foreground">#{job.id}</span>
                  </div>
                  <div className="mt-2 grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
                    <span>Created {formatDateTime(job.created_at)}</span>
                    <span>Started {formatDateTime(job.started_at)}</span>
                    <span>Finished {formatDateTime(job.finished_at)}</span>
                  </div>
                  <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <MagnifyingGlass size={13} />
                    <span>{resultLine(job)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </AppPage>
  );
}
