"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Books, Database, FileText } from "@phosphor-icons/react";

import { AppPage, EmptyState, InlineError, LoadingRows, Panel, PanelHeader, StatusPill } from "@/components/AppPage";
import { api } from "@/lib/api/client";
import { formatDate, formatDateTime } from "@/lib/format";

export default function SourcesPage() {
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);

  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: () => api.listSources(200),
  });

  const resolvedSourceId = selectedSourceId ?? sources.data?.sources[0]?.id ?? null;

  const documents = useQuery({
    queryKey: ["source-documents", resolvedSourceId],
    queryFn: () => api.listSourceDocuments(resolvedSourceId!, 200),
    enabled: resolvedSourceId != null,
  });

  const selected = sources.data?.sources.find((source) => source.id === resolvedSourceId);

  return (
    <AppPage
      eyebrow="Sources"
      title="Documents overview"
      description="Review indexed sources, document counts, chunks, and tags."
    >
      <div className="grid gap-5 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Sources" />
          {sources.isLoading && <LoadingRows rows={6} />}
          {sources.error && !sources.isLoading && (
            <div className="p-4">
              <InlineError message={sources.error instanceof Error ? sources.error.message : "Sources failed"} />
            </div>
          )}
          {sources.data?.sources.length === 0 && (
            <EmptyState icon={<Books size={20} />} title="No sources yet" body="Ingest a document to populate this list." />
          )}
          {sources.data && sources.data.sources.length > 0 && (
            <div className="divide-y divide-border">
              {sources.data.sources.map((source) => {
                const active = source.id === resolvedSourceId;
                return (
                  <button
                    key={source.id}
                    type="button"
                    onClick={() => setSelectedSourceId(source.id)}
                    className={`block w-full px-4 py-3 text-left transition-colors ${
                      active ? "bg-amber-50/70 dark:bg-amber-950/20" : "hover:bg-muted/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">{source.name}</p>
                        <p className="mt-1 truncate text-xs text-muted-foreground">{source.type}</p>
                      </div>
                      <span className="font-mono text-[11px] text-muted-foreground">#{source.id}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <StatusPill>{source.document_count} docs</StatusPill>
                      <StatusPill>{source.chunk_count} chunks</StatusPill>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </Panel>

        <Panel>
          <PanelHeader
            title={selected ? selected.name : "Documents"}
            description={selected ? `${selected.type} / latest ${formatDate(selected.latest_document_at)}` : undefined}
          />
          {!resolvedSourceId && !sources.isLoading && (
            <EmptyState icon={<Database size={20} />} title="Select a source" />
          )}
          {documents.isLoading && <LoadingRows rows={6} />}
          {documents.error && !documents.isLoading && (
            <div className="p-4">
              <InlineError message={documents.error instanceof Error ? documents.error.message : "Documents failed"} />
            </div>
          )}
          {documents.data?.documents.length === 0 && (
            <EmptyState icon={<FileText size={20} />} title="No documents for this source" />
          )}
          {documents.data && documents.data.documents.length > 0 && (
            <div className="divide-y divide-border">
              {documents.data.documents.map((doc) => (
                <div key={doc.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill tone={doc.status === "embedded" ? "success" : "warning"}>{doc.status}</StatusPill>
                    <p className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">{doc.title}</p>
                    <span className="font-mono text-[11px] text-muted-foreground">#{doc.id}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <StatusPill>{doc.chunk_count} chunks</StatusPill>
                    <StatusPill tone={doc.raw_text_available ? "neutral" : "warning"}>
                      raw text {doc.raw_text_available ? "kept" : "purged"}
                    </StatusPill>
                    {doc.tags.map((tag) => (
                      <span key={tag} className="inline-flex h-5 items-center rounded-md bg-muted px-2 text-[11px] font-semibold text-muted-foreground">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Ingested {formatDateTime(doc.ingested_at)} / {doc.content_type ?? "unknown type"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </AppPage>
  );
}
