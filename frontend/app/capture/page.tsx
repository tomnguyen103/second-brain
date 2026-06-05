"use client";

import { Suspense, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { ArrowRight, BookmarkSimple, CheckCircle } from "@phosphor-icons/react";

import { AppPage, InlineError, Panel, PanelHeader, StatusPill } from "@/components/AppPage";
import { api } from "@/lib/api/client";
import { queryClient } from "@/lib/query-client";
import type { CaptureResponse } from "@/lib/api/types";

function splitTags(value: string): string[] {
  return Array.from(new Set(value.split(",").map((tag) => tag.trim()).filter(Boolean)));
}

function resultTone(status: string): "neutral" | "success" | "warning" | "danger" {
  if (status === "embedded") return "success";
  if (status === "duplicate") return "warning";
  if (status === "failed") return "danger";
  return "neutral";
}

function CapturePageContent() {
  const searchParams = useSearchParams();
  const [url, setUrl] = useState(searchParams.get("url") ?? "");
  const [title, setTitle] = useState(searchParams.get("title") ?? "");
  const [selectedText, setSelectedText] = useState(searchParams.get("text") ?? "");
  const [notes, setNotes] = useState(searchParams.get("notes") ?? "");
  const [tags, setTags] = useState(searchParams.get("tags") ?? "");
  const [lastResult, setLastResult] = useState<CaptureResponse | null>(null);

  const capture = useMutation({
    mutationFn: () =>
      api.capture({
        url: url.trim(),
        title: title.trim() || undefined,
        selected_text: selectedText.trim() || undefined,
        notes: notes.trim() || undefined,
        tags: splitTags(tags),
      }),
    onSuccess: (data) => {
      setLastResult(data);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const canSubmit = Boolean(url.trim() && (selectedText.trim() || notes.trim())) && !capture.isPending;

  return (
    <AppPage
      eyebrow="Capture"
      title="Save a web note"
      description="Store a URL, selected text, notes, and tags as a searchable bookmark document."
    >
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Panel>
          <PanelHeader title="Bookmark" />
          <form
            className="grid gap-3 p-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (canSubmit) capture.mutate();
            }}
          >
            {capture.error && (
              <InlineError message={capture.error instanceof Error ? capture.error.message : "Capture failed"} />
            )}
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
              URL
              <input
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                placeholder="https://example.com/article"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
              Title
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                placeholder="Page title"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
              Selected text
              <textarea
                value={selectedText}
                onChange={(event) => setSelectedText(event.target.value)}
                className="min-h-44 resize-y rounded-lg border border-input bg-background px-3 py-2.5 text-sm leading-6 text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                placeholder="Quoted passage"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
              Notes
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                className="min-h-28 resize-y rounded-lg border border-input bg-background px-3 py-2.5 text-sm leading-6 text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                placeholder="Why this matters"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
              Tags
              <input
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                placeholder="inbox, reading, project"
              />
            </label>
            <div className="flex justify-end border-t border-border pt-3">
              <button
                type="submit"
                disabled={!canSubmit}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3 text-sm font-semibold text-white shadow-sm shadow-amber-200/60 transition-colors hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-40 dark:shadow-none"
              >
                {capture.isPending ? "Capturing" : "Capture"} <ArrowRight size={14} weight="bold" />
              </button>
            </div>
          </form>
        </Panel>

        <Panel>
          <PanelHeader title="Result" />
          <div className="p-4">
            {!lastResult && (
              <div className="rounded-lg bg-muted/50 px-3 py-8 text-center">
                <BookmarkSimple size={22} className="mx-auto text-muted-foreground" />
                <p className="mt-2 text-sm font-semibold text-foreground">Ready</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Captures appear here after they are stored and embedded.
                </p>
              </div>
            )}
            {lastResult && (
              <div className="space-y-4">
                <div className="flex items-start gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:ring-emerald-900/60">
                  <CheckCircle size={15} weight="bold" className="mt-0.5 shrink-0" />
                  <span className="leading-5">Saved to source #{lastResult.source_id}</span>
                </div>
                <div className="rounded-lg bg-muted/50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-semibold text-foreground">{lastResult.document.title}</p>
                    <StatusPill tone={resultTone(lastResult.document.status)}>
                      {lastResult.document.status}
                    </StatusPill>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{lastResult.capture_url}</p>
                  <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                    {lastResult.document.chunk_count} chunks / {lastResult.document.embedded_count} embedded
                  </p>
                  {lastResult.document.duplicate_of && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Duplicate of document #{lastResult.document.duplicate_of}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </Panel>
      </div>
    </AppPage>
  );
}

export default function CapturePage() {
  return (
    <Suspense fallback={<div className="flex-1" />}>
      <CapturePageContent />
    </Suspense>
  );
}
