"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, FilePlus, Plus, Trash } from "@phosphor-icons/react";

import { AppPage, InlineError, Panel, PanelHeader, StatusPill } from "@/components/AppPage";
import { api } from "@/lib/api/client";
import { queryClient } from "@/lib/query-client";
import type { IngestResponse, SourceType } from "@/lib/api/types";

type DraftDocument = {
  id: string;
  title: string;
  content: string;
  tags: string;
  contentType: string;
};

const SOURCE_TYPES: SourceType[] = [
  "manual",
  "notes_folder",
  "pdf_upload",
  "bookmark",
  "github",
  "rss",
  "research_note",
];

function newDraftDocument(id: string): DraftDocument {
  return { id, title: "", content: "", tags: "", contentType: "text/plain" };
}

function splitTags(value: string): string[] {
  return value.split(",").map((tag) => tag.trim()).filter(Boolean);
}

function resultTone(status: string): "neutral" | "success" | "warning" | "danger" {
  if (status === "embedded") return "success";
  if (status === "duplicate") return "warning";
  if (status === "failed") return "danger";
  return "neutral";
}

export default function IngestPage() {
  const [sourceType, setSourceType] = useState<SourceType>("manual");
  const [sourceName, setSourceName] = useState("Manual notes");
  const [sourceUri, setSourceUri] = useState("");
  const [documents, setDocuments] = useState<DraftDocument[]>([newDraftDocument("doc-1")]);
  const [lastResult, setLastResult] = useState<IngestResponse | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const cleanDocs = documents
        .map((doc) => ({
          title: doc.title.trim(),
          content: doc.content.trim(),
          content_type: doc.contentType.trim() || "text/plain",
          tags: splitTags(doc.tags),
        }))
        .filter((doc) => doc.title && doc.content);

      return api.ingest({
        source: {
          type: sourceType,
          name: sourceName.trim(),
          uri: sourceUri.trim() || undefined,
          config: {},
        },
        documents: cleanDocs,
      });
    },
    onSuccess: (data) => {
      setLastResult(data);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const validDocs = documents.filter((doc) => doc.title.trim() && doc.content.trim()).length;
  const canSubmit = sourceName.trim().length > 0 && validDocs > 0 && !mutation.isPending;

  const updateDoc = (id: string, patch: Partial<DraftDocument>) => {
    setDocuments((prev) => prev.map((doc) => (doc.id === id ? { ...doc, ...patch } : doc)));
  };

  return (
    <AppPage
      eyebrow="Ingest"
      title="Add notes and documents"
      description="Store text, tags, and source metadata so chat and search can cite them later."
    >
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Panel>
          <PanelHeader
            title="Source"
            description="Choose the source bucket these documents belong to."
          />
          <div className="grid gap-3 p-4 sm:grid-cols-3">
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
              Type
              <select
                value={sourceType}
                onChange={(event) => setSourceType(event.target.value as SourceType)}
                className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
              >
                {SOURCE_TYPES.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground sm:col-span-2">
              Name
              <input
                value={sourceName}
                onChange={(event) => setSourceName(event.target.value)}
                className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                placeholder="Source name"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground sm:col-span-3">
              URI
              <input
                value={sourceUri}
                onChange={(event) => setSourceUri(event.target.value)}
                className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                placeholder="Optional file path, URL, or folder"
              />
            </label>
          </div>
        </Panel>

        <Panel className="lg:row-span-2">
          <PanelHeader title="Result" />
          <div className="p-4">
            {mutation.error && (
              <InlineError message={mutation.error instanceof Error ? mutation.error.message : "Ingest failed"} />
            )}
            {!mutation.error && !lastResult && (
              <div className="rounded-lg bg-muted/50 px-3 py-8 text-center">
                <FilePlus size={22} className="mx-auto text-muted-foreground" />
                <p className="mt-2 text-sm font-semibold text-foreground">Ready to ingest</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Results appear here after the API stores and embeds the batch.
                </p>
              </div>
            )}
            {lastResult && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {[
                    ["Source", lastResult.source_id],
                    ["Embedded", lastResult.summary.embedded],
                    ["Duplicates", lastResult.summary.duplicates],
                    ["Chunks", lastResult.summary.chunks_created],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg bg-muted/50 p-3">
                      <p className="text-muted-foreground">{label}</p>
                      <p className="mt-1 font-mono text-base font-semibold text-foreground">{value}</p>
                    </div>
                  ))}
                </div>
                <div className="divide-y divide-border rounded-lg ring-1 ring-border">
                  {lastResult.documents.map((doc) => (
                    <div key={`${doc.title}-${doc.content_hash}`} className="p-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-sm font-semibold text-foreground">{doc.title}</p>
                        <StatusPill tone={resultTone(doc.status)}>{doc.status}</StatusPill>
                      </div>
                      <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                        {doc.chunk_count} chunks / {doc.embedded_count} embedded
                      </p>
                      {doc.error && <p className="mt-1 text-xs text-destructive">{doc.error}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            title="Documents"
            actions={
              <button
                type="button"
                onClick={() => setDocuments((prev) => [...prev, newDraftDocument(`doc-${Date.now()}`)])}
                className="inline-flex h-7 items-center gap-1.5 rounded-lg border border-border px-2.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Plus size={13} weight="bold" /> Add
              </button>
            }
          />
          <div className="divide-y divide-border">
            {documents.map((doc, index) => (
              <div key={doc.id} className="grid gap-3 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Document {index + 1}
                  </p>
                  {documents.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setDocuments((prev) => prev.filter((item) => item.id !== doc.id))}
                      className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                      aria-label="Remove document"
                    >
                      <Trash size={14} />
                    </button>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem]">
                  <input
                    value={doc.title}
                    onChange={(event) => updateDoc(doc.id, { title: event.target.value })}
                    className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                    placeholder="Title"
                  />
                  <input
                    value={doc.contentType}
                    onChange={(event) => updateDoc(doc.id, { contentType: event.target.value })}
                    className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                    placeholder="text/plain"
                  />
                </div>
                <textarea
                  value={doc.content}
                  onChange={(event) => updateDoc(doc.id, { content: event.target.value })}
                  className="min-h-44 resize-y rounded-lg border border-input bg-background px-3 py-2.5 text-sm leading-6 text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                  placeholder="Paste note or document text"
                />
                <input
                  value={doc.tags}
                  onChange={(event) => updateDoc(doc.id, { tags: event.target.value })}
                  className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                  placeholder="Tags, comma separated"
                />
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
            <p className="text-xs text-muted-foreground">{validDocs} ready document{validDocs === 1 ? "" : "s"}</p>
            <button
              type="button"
              onClick={() => mutation.mutate()}
              disabled={!canSubmit}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-amber-500 px-3 text-sm font-semibold text-white shadow-sm shadow-amber-200/60 transition-colors hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-40 dark:shadow-none"
            >
              {mutation.isPending ? "Ingesting" : "Ingest"} <ArrowRight size={14} weight="bold" />
            </button>
          </div>
        </Panel>
      </div>
    </AppPage>
  );
}
