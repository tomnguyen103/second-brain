"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Books,
  Check,
  Database,
  FilePlus,
  FileText,
  FolderSimple,
  PencilSimple,
  Trash,
  WarningCircle,
  X,
} from "@phosphor-icons/react";

import {
  AppButton,
  AppPage,
  EmptyState,
  Field,
  InlineError,
  LoadingRows,
  Panel,
  PanelHeader,
  StatusPill,
  TextArea,
  TextInput,
} from "@/components/AppPage";
import { api } from "@/lib/api/client";
import type { DocumentSummary, SourceSummary } from "@/lib/api/types";
import { formatDate, formatDateTime } from "@/lib/format";
import { queryClient } from "@/lib/query-client";
import { cn } from "@/lib/utils";

type DeleteTarget =
  | { kind: "source"; id: number; label: string; documents: number }
  | { kind: "document"; id: number; sourceId: number; label: string };

function sourceTypeLabel(type: string): string {
  return type.replace(/_/g, " ");
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function contentSourceLabel(value: string): string {
  if (value === "raw_text") return "raw text";
  if (value === "chunks") return "indexed chunks";
  return "unavailable";
}

function MetricTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <div className="rounded-lg bg-card/90 px-4 py-3 ring-1 ring-border/90 shadow-sm shadow-zinc-950/[0.02]">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-foreground">
        {value}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </div>
  );
}

function DocumentMeta({ doc }: { doc: DocumentSummary }) {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      <StatusPill>{doc.chunk_count} chunks</StatusPill>
      <StatusPill tone={doc.raw_text_available ? "neutral" : "warning"}>
        raw text {doc.raw_text_available ? "kept" : "purged"}
      </StatusPill>
      {doc.tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex h-5 items-center rounded-md bg-muted px-2 text-[11px] font-semibold text-muted-foreground"
        >
          {tag}
        </span>
      ))}
    </div>
  );
}

export default function SourcesPage() {
  const router = useRouter();
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(
    null,
  );
  const [adminToken, setAdminToken] = useState("");
  const [editingSourceId, setEditingSourceId] = useState<number | null>(null);
  const [sourceNameDraft, setSourceNameDraft] = useState("");
  const [editingDocumentId, setEditingDocumentId] = useState<number | null>(
    null,
  );
  const [documentTitleDraft, setDocumentTitleDraft] = useState("");
  const [isEditingContent, setIsEditingContent] = useState(false);
  const [contentDraft, setContentDraft] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState("");

  const adminTokenValue = adminToken.trim();
  const hasAdminToken = adminTokenValue.length > 0;

  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: () => api.listSources(200),
  });

  const sourceRows = sources.data?.sources ?? [];
  const selectedSourceExists =
    selectedSourceId != null &&
    sourceRows.some((source) => source.id === selectedSourceId);
  const resolvedSourceId = selectedSourceExists
    ? selectedSourceId
    : (sourceRows[0]?.id ?? null);

  const documents = useQuery({
    queryKey: ["source-documents", resolvedSourceId],
    queryFn: () => api.listSourceDocuments(resolvedSourceId!, 200),
    enabled: resolvedSourceId != null,
  });

  const documentRows = documents.data?.documents ?? [];
  const resolvedDocumentId =
    selectedDocumentId != null &&
    documentRows.some((doc) => doc.id === selectedDocumentId)
      ? selectedDocumentId
      : null;

  const fileContent = useQuery({
    queryKey: ["document-content", resolvedDocumentId],
    queryFn: () => api.getDocumentContent(resolvedDocumentId!),
    enabled: resolvedDocumentId != null,
  });

  const selected = sourceRows.find((source) => source.id === resolvedSourceId);

  const totals = useMemo(() => {
    const rows = sources.data?.sources ?? [];
    return rows.reduce(
      (acc, source) => ({
        sources: acc.sources + 1,
        documents: acc.documents + source.document_count,
        chunks: acc.chunks + source.chunk_count,
      }),
      { sources: 0, documents: 0, chunks: 0 },
    );
  }, [sources.data?.sources]);

  const renameSource = useMutation({
    mutationFn: ({ sourceId, name }: { sourceId: number; name: string }) =>
      api.updateSource(sourceId, { name }, adminTokenValue),
    onSuccess: async () => {
      setEditingSourceId(null);
      setSourceNameDraft("");
      await queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const renameDocument = useMutation({
    mutationFn: ({
      documentId,
      title,
    }: {
      documentId: number;
      title: string;
    }) => api.updateDocument(documentId, { title }, adminTokenValue),
    onSuccess: async (doc) => {
      setEditingDocumentId(null);
      setDocumentTitleDraft("");
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["source-documents", doc.source_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["document-content", doc.id],
        }),
      ]);
    },
  });

  const updateDocumentContent = useMutation({
    mutationFn: ({
      documentId,
      content,
    }: {
      documentId: number;
      content: string;
    }) => api.updateDocumentContent(documentId, { content }, adminTokenValue),
    onSuccess: async (data) => {
      setIsEditingContent(false);
      setContentDraft(data.content ?? "");
      queryClient.setQueryData(["document-content", data.document.id], data);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sources"] }),
        queryClient.invalidateQueries({
          queryKey: ["source-documents", data.document.source_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["document-content", data.document.id],
        }),
      ]);
    },
  });

  const deleteSource = useMutation({
    mutationFn: ({ sourceId }: { sourceId: number }) =>
      api.deleteSource(sourceId, adminTokenValue),
    onSuccess: async (data) => {
      setDeleteTarget(null);
      setDeleteConfirm("");
      if (resolvedSourceId === data.source_id) {
        setSelectedSourceId(null);
        setSelectedDocumentId(null);
        setIsEditingContent(false);
        setContentDraft("");
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sources"] }),
        queryClient.invalidateQueries({ queryKey: ["source-documents"] }),
      ]);
    },
  });

  const deleteDocument = useMutation({
    mutationFn: ({ documentId }: { documentId: number }) =>
      api.deleteDocument(documentId, adminTokenValue),
    onSuccess: async (data) => {
      setDeleteTarget(null);
      setDeleteConfirm("");
      if (selectedDocumentId === data.document_id) {
        setSelectedDocumentId(null);
        setIsEditingContent(false);
        setContentDraft("");
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sources"] }),
        queryClient.invalidateQueries({
          queryKey: ["source-documents", data.source_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["document-content", data.document_id],
        }),
      ]);
    },
  });

  const actionError =
    renameSource.error ??
    renameDocument.error ??
    updateDocumentContent.error ??
    deleteSource.error ??
    deleteDocument.error;

  function startSourceRename(source: SourceSummary) {
    renameSource.reset();
    setEditingSourceId(source.id);
    setSourceNameDraft(source.name);
  }

  function startDocumentRename(doc: DocumentSummary) {
    renameDocument.reset();
    setEditingDocumentId(doc.id);
    setDocumentTitleDraft(doc.title);
  }

  function requestSourceDelete(source: SourceSummary) {
    deleteSource.reset();
    setDeleteTarget({
      kind: "source",
      id: source.id,
      label: source.name,
      documents: source.document_count,
    });
    setDeleteConfirm("");
  }

  function requestDocumentDelete(doc: DocumentSummary) {
    deleteDocument.reset();
    setDeleteTarget({
      kind: "document",
      id: doc.id,
      sourceId: doc.source_id,
      label: doc.title,
    });
    setDeleteConfirm("");
  }

  function saveSourceRename() {
    const name = sourceNameDraft.trim();
    if (!editingSourceId || !name || !hasAdminToken) return;
    renameSource.mutate({ sourceId: editingSourceId, name });
  }

  function saveDocumentRename() {
    const title = documentTitleDraft.trim();
    if (!editingDocumentId || !title || !hasAdminToken) return;
    renameDocument.mutate({ documentId: editingDocumentId, title });
  }

  function selectSource(sourceId: number) {
    setSelectedSourceId(sourceId);
    setSelectedDocumentId(null);
    setEditingDocumentId(null);
    setIsEditingContent(false);
    setContentDraft("");
    updateDocumentContent.reset();
  }

  function selectDocument(documentId: number) {
    setSelectedDocumentId(documentId);
    setIsEditingContent(false);
    setContentDraft("");
    updateDocumentContent.reset();
  }

  function confirmDelete() {
    if (
      !deleteTarget ||
      deleteConfirm.trim() !== String(deleteTarget.id) ||
      !hasAdminToken
    )
      return;
    if (deleteTarget.kind === "source") {
      deleteSource.mutate({ sourceId: deleteTarget.id });
    } else {
      deleteDocument.mutate({ documentId: deleteTarget.id });
    }
  }

  const deleting = deleteSource.isPending || deleteDocument.isPending;

  function startContentEdit() {
    if (!fileContent.data?.content || fileContent.data.truncated) return;
    updateDocumentContent.reset();
    setContentDraft(fileContent.data.content);
    setIsEditingContent(true);
  }

  function saveContentEdit() {
    if (
      resolvedDocumentId == null ||
      !hasAdminToken ||
      !contentDraft.trim() ||
      contentDraft === (fileContent.data?.content ?? "")
    ) {
      return;
    }
    updateDocumentContent.mutate({
      documentId: resolvedDocumentId,
      content: contentDraft,
    });
  }

  return (
    <AppPage
      eyebrow="Sources"
      title="Source folders and files"
      description="Review indexed folders, inspect file content, and manage source names safely."
      actions={
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-end">
          <AppButton
            type="button"
            onClick={() => router.push("/ingest")}
            className="w-full sm:w-auto"
          >
            <FilePlus size={14} weight="bold" /> Add New Sources
          </AppButton>
          <Field label="Admin token" className="w-full sm:w-72">
            <TextInput
              type="password"
              value={adminToken}
              onChange={(event) => setAdminToken(event.target.value)}
              placeholder="Required for rename/delete/save"
            />
          </Field>
        </div>
      }
    >
      <div className="grid gap-3 md:grid-cols-3">
        <MetricTile
          label="Source folders"
          value={sources.isLoading ? "..." : totals.sources}
          detail="Indexed buckets"
        />
        <MetricTile
          label="Files"
          value={sources.isLoading ? "..." : totals.documents}
          detail="Documents across sources"
        />
        <MetricTile
          label="Chunks"
          value={sources.isLoading ? "..." : totals.chunks}
          detail="Searchable passages"
        />
      </div>

      {actionError && (
        <InlineError
          message={errorMessage(actionError, "Source action failed")}
        />
      )}

      {deleteTarget && (
        <div className="rounded-lg border border-destructive/25 bg-destructive/10 p-4 text-destructive">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-3">
              <WarningCircle
                size={18}
                weight="bold"
                className="mt-0.5 shrink-0"
              />
              <div>
                <p className="text-sm font-semibold">
                  Delete{" "}
                  {deleteTarget.kind === "source" ? "source folder" : "file"} #
                  {deleteTarget.id}
                </p>
                <p className="mt-1 text-xs leading-5 text-destructive/85">
                  {deleteTarget.kind === "source"
                    ? `${deleteTarget.label} and ${deleteTarget.documents} file${deleteTarget.documents === 1 ? "" : "s"} will be removed with their chunks and embeddings.`
                    : `${deleteTarget.label} will be removed with its chunks and embeddings.`}
                </p>
              </div>
            </div>
            <div className="flex min-w-0 flex-col gap-2 sm:min-w-80">
              <TextInput
                value={deleteConfirm}
                onChange={(event) => setDeleteConfirm(event.target.value)}
                className="font-mono focus-visible:border-destructive focus-visible:ring-destructive/15"
                placeholder={`Type ${deleteTarget.id} to confirm`}
              />
              <div className="flex justify-end gap-2">
                <AppButton
                  type="button"
                  variant="quiet"
                  size="sm"
                  onClick={() => {
                    setDeleteTarget(null);
                    setDeleteConfirm("");
                  }}
                >
                  <X size={14} weight="bold" /> Cancel
                </AppButton>
                <AppButton
                  type="button"
                  variant="dangerSoft"
                  size="sm"
                  onClick={confirmDelete}
                  disabled={
                    !hasAdminToken ||
                    deleteConfirm.trim() !== String(deleteTarget.id) ||
                    deleting
                  }
                >
                  <Trash size={14} weight="bold" />{" "}
                  {deleting ? "Deleting" : "Delete"}
                </AppButton>
              </div>
              {!hasAdminToken && (
                <p className="text-right text-[11px] font-medium text-destructive/85">
                  Admin token required.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[21rem_minmax(0,1fr)]">
        <Panel className="overflow-hidden">
          <PanelHeader
            title="Source folders"
            description={
              sources.data
                ? `${sources.data.total} indexed`
                : "Loading indexed folders"
            }
          />
          {sources.isLoading && <LoadingRows rows={6} />}
          {sources.error && !sources.isLoading && (
            <div className="p-4">
              <InlineError
                message={errorMessage(sources.error, "Sources failed")}
              />
            </div>
          )}
          {sources.data?.sources.length === 0 && (
            <EmptyState
              icon={<Books size={20} />}
              title="No sources yet"
              body="Use Add New Sources to populate this list."
            />
          )}
          {sources.data && sources.data.sources.length > 0 && (
            <div className="space-y-2 p-3">
              {sources.data.sources.map((source) => {
                const active = source.id === resolvedSourceId;
                const editing = source.id === editingSourceId;
                return (
                  <div
                    key={source.id}
                    className={cn(
                      "rounded-lg border bg-background/70 transition-colors",
                      active
                        ? "border-primary/45 bg-primary/10"
                        : "border-border hover:border-foreground/20",
                    )}
                  >
                    {editing ? (
                      <div className="space-y-3 p-3">
                        <Field label="Folder name">
                          <TextInput
                            value={sourceNameDraft}
                            onChange={(event) =>
                              setSourceNameDraft(event.target.value)
                            }
                            autoFocus
                          />
                        </Field>
                        <div className="flex justify-end gap-2">
                          <AppButton
                            type="button"
                            variant="quiet"
                            size="sm"
                            onClick={() => setEditingSourceId(null)}
                          >
                            <X size={14} weight="bold" /> Cancel
                          </AppButton>
                          <AppButton
                            type="button"
                            size="sm"
                            onClick={saveSourceRename}
                            disabled={
                              !hasAdminToken ||
                              !sourceNameDraft.trim() ||
                              renameSource.isPending
                            }
                          >
                            <Check size={14} weight="bold" />{" "}
                            {renameSource.isPending ? "Saving" : "Save"}
                          </AppButton>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start gap-2 p-2">
                        <button
                          type="button"
                          onClick={() => selectSource(source.id)}
                          className="min-w-0 flex-1 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/60 focus-visible:border-primary focus-visible:ring-3 focus-visible:ring-primary/15 focus-visible:outline-none"
                        >
                          <div className="flex min-w-0 items-start gap-2">
                            <FolderSimple
                              size={17}
                              weight={active ? "fill" : "bold"}
                              className="mt-0.5 shrink-0 text-primary"
                            />
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-foreground">
                                {source.name}
                              </p>
                              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                                {sourceTypeLabel(source.type)} / latest{" "}
                                {formatDate(source.latest_document_at)}
                              </p>
                            </div>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            <StatusPill>
                              {source.document_count} files
                            </StatusPill>
                            <StatusPill>{source.chunk_count} chunks</StatusPill>
                            <StatusPill>#{source.id}</StatusPill>
                          </div>
                        </button>
                        <div className="flex shrink-0 gap-1">
                          <AppButton
                            type="button"
                            title="Rename source"
                            aria-label={`Rename ${source.name}`}
                            variant="quiet"
                            size="icon"
                            onClick={() => startSourceRename(source)}
                          >
                            <PencilSimple size={15} weight="bold" />
                          </AppButton>
                          <AppButton
                            type="button"
                            title="Delete source"
                            aria-label={`Delete ${source.name}`}
                            variant="dangerSoft"
                            size="icon"
                            onClick={() => requestSourceDelete(source)}
                          >
                            <Trash size={15} weight="bold" />
                          </AppButton>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Panel>

        <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_26rem]">
          <Panel className="overflow-hidden">
            <PanelHeader
              title={selected ? selected.name : "Files"}
              description={
                selected
                  ? `${sourceTypeLabel(selected.type)} / updated ${formatDateTime(selected.updated_at)}`
                  : "Select a source folder"
              }
              actions={
                selected ? (
                  <div className="hidden flex-wrap gap-1.5 sm:flex">
                    <StatusPill>{selected.document_count} files</StatusPill>
                    <StatusPill>{selected.chunk_count} chunks</StatusPill>
                  </div>
                ) : undefined
              }
            />
            {!resolvedSourceId && !sources.isLoading && (
              <EmptyState
                icon={<Database size={20} />}
                title="Select a source"
              />
            )}
            {documents.isLoading && <LoadingRows rows={6} />}
            {documents.error && !documents.isLoading && (
              <div className="p-4">
                <InlineError
                  message={errorMessage(documents.error, "Documents failed")}
                />
              </div>
            )}
            {documents.data?.documents.length === 0 && (
              <EmptyState
                icon={<FileText size={20} />}
                title="No files in this source"
              />
            )}
            {documents.data && documents.data.documents.length > 0 && (
              <div className="divide-y divide-border/80">
                {documentRows.map((doc) => {
                  const active = doc.id === resolvedDocumentId;
                  const editing = doc.id === editingDocumentId;
                  return (
                    <div
                      key={doc.id}
                      className={cn(
                        "px-4 py-3 transition-colors",
                        active && "bg-primary/5",
                      )}
                    >
                      {editing ? (
                        <div className="space-y-3">
                          <Field label="File title">
                            <TextInput
                              value={documentTitleDraft}
                              onChange={(event) =>
                                setDocumentTitleDraft(event.target.value)
                              }
                              autoFocus
                            />
                          </Field>
                          <div className="flex justify-end gap-2">
                            <AppButton
                              type="button"
                              variant="quiet"
                              size="sm"
                              onClick={() => setEditingDocumentId(null)}
                            >
                              <X size={14} weight="bold" /> Cancel
                            </AppButton>
                            <AppButton
                              type="button"
                              size="sm"
                              onClick={saveDocumentRename}
                              disabled={
                                !hasAdminToken ||
                                !documentTitleDraft.trim() ||
                                renameDocument.isPending
                              }
                            >
                              <Check size={14} weight="bold" />{" "}
                              {renameDocument.isPending ? "Saving" : "Save"}
                            </AppButton>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-start gap-3">
                          <button
                            type="button"
                            onClick={() => selectDocument(doc.id)}
                            className="min-w-0 flex-1 rounded-md text-left transition-colors hover:bg-muted/45 focus-visible:border-primary focus-visible:ring-3 focus-visible:ring-primary/15 focus-visible:outline-none"
                          >
                            <div className="flex min-w-0 flex-wrap items-center gap-2 px-1 py-0.5">
                              <StatusPill
                                tone={
                                  doc.status === "embedded"
                                    ? "success"
                                    : "warning"
                                }
                              >
                                {doc.status}
                              </StatusPill>
                              <p className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">
                                {doc.title}
                              </p>
                              <span className="font-mono text-[11px] text-muted-foreground">
                                #{doc.id}
                              </span>
                            </div>
                            <DocumentMeta doc={doc} />
                            <p className="mt-2 px-1 text-xs text-muted-foreground">
                              Ingested {formatDateTime(doc.ingested_at)} /{" "}
                              {doc.content_type ?? "unknown type"}
                            </p>
                          </button>
                          <div className="flex shrink-0 gap-1">
                            <AppButton
                              type="button"
                              title="Open file content"
                              aria-label={`Open file content for ${doc.title}`}
                              variant="quiet"
                              size="icon"
                              onClick={() => selectDocument(doc.id)}
                            >
                              <FileText size={15} weight="bold" />
                            </AppButton>
                            <AppButton
                              type="button"
                              title="Rename file"
                              aria-label={`Rename ${doc.title}`}
                              variant="quiet"
                              size="icon"
                              onClick={() => startDocumentRename(doc)}
                            >
                              <PencilSimple size={15} weight="bold" />
                            </AppButton>
                            <AppButton
                              type="button"
                              title="Delete file"
                              aria-label={`Delete ${doc.title}`}
                              variant="dangerSoft"
                              size="icon"
                              onClick={() => requestDocumentDelete(doc)}
                            >
                              <Trash size={15} weight="bold" />
                            </AppButton>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>

          <Panel className="overflow-hidden 2xl:sticky 2xl:top-5 2xl:self-start">
            <PanelHeader
              title="File content"
              description={
                fileContent.data
                  ? fileContent.data.document.title
                  : "Select a file to inspect its text"
              }
              actions={
                fileContent.data ? (
                  <div className="flex flex-wrap justify-end gap-2">
                    <StatusPill
                      tone={
                        fileContent.data.content_source === "raw_text"
                          ? "neutral"
                          : "warning"
                      }
                    >
                      {contentSourceLabel(fileContent.data.content_source)}
                    </StatusPill>
                    {fileContent.data.content && !isEditingContent && (
                      <AppButton
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={startContentEdit}
                        disabled={fileContent.data.truncated}
                      >
                        <PencilSimple size={14} weight="bold" /> Edit
                      </AppButton>
                    )}
                  </div>
                ) : undefined
              }
            />
            {resolvedDocumentId == null && (
              <EmptyState
                icon={<FileText size={20} />}
                title="No file selected"
                body="Choose a file from the list to view stored text or indexed chunks."
              />
            )}
            {fileContent.isLoading && <LoadingRows rows={5} />}
            {fileContent.error && !fileContent.isLoading && (
              <div className="p-4">
                <InlineError
                  message={errorMessage(
                    fileContent.error,
                    "File content failed",
                  )}
                />
              </div>
            )}
            {fileContent.data && (
              <div className="space-y-4 p-4">
                <div className="rounded-lg bg-muted/40 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill
                      tone={
                        fileContent.data.document.status === "embedded"
                          ? "success"
                          : "warning"
                      }
                    >
                      {fileContent.data.document.status}
                    </StatusPill>
                    <StatusPill>#{fileContent.data.document.id}</StatusPill>
                    <StatusPill>
                      {fileContent.data.document.chunk_count} chunks
                    </StatusPill>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    Source: {fileContent.data.source.name} / Updated{" "}
                    {formatDateTime(fileContent.data.document.updated_at)}
                  </p>
                </div>
                {fileContent.data.content ? (
                  isEditingContent ? (
                    <div className="space-y-3">
                      <Field label="File content">
                        <TextArea
                          value={contentDraft}
                          onChange={(event) =>
                            setContentDraft(event.target.value)
                          }
                          rows={18}
                          className="min-h-[24rem] font-mono text-xs"
                          autoFocus
                        />
                      </Field>
                      {updateDocumentContent.error && (
                        <InlineError
                          message={errorMessage(
                            updateDocumentContent.error,
                            "Content save failed",
                          )}
                        />
                      )}
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        {!hasAdminToken ? (
                          <p className="text-[11px] font-medium text-muted-foreground">
                            Admin token required to save.
                          </p>
                        ) : (
                          <span />
                        )}
                        <div className="flex justify-end gap-2">
                          <AppButton
                            type="button"
                            variant="quiet"
                            size="sm"
                            onClick={() => {
                              setIsEditingContent(false);
                              setContentDraft("");
                              updateDocumentContent.reset();
                            }}
                          >
                            <X size={14} weight="bold" /> Cancel
                          </AppButton>
                          <AppButton
                            type="button"
                            size="sm"
                            onClick={saveContentEdit}
                            disabled={
                              !hasAdminToken ||
                              !contentDraft.trim() ||
                              contentDraft === fileContent.data.content ||
                              updateDocumentContent.isPending
                            }
                          >
                            <Check size={14} weight="bold" />{" "}
                            {updateDocumentContent.isPending
                              ? "Saving"
                              : "Save"}
                          </AppButton>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {fileContent.data.truncated && (
                        <InlineError message="File content is too large to edit safely from this panel." />
                      )}
                      <pre className="max-h-[34rem] overflow-auto whitespace-pre-wrap rounded-lg bg-background p-4 text-xs leading-6 text-foreground ring-1 ring-border">
                        {fileContent.data.content}
                        {fileContent.data.truncated
                          ? "\n\n[Content truncated]"
                          : ""}
                      </pre>
                    </div>
                  )
                ) : (
                  <EmptyState
                    icon={<FileText size={20} />}
                    title="No file content available"
                    body="This file has no retained raw text or indexed chunk content."
                    className="rounded-lg bg-muted/30"
                  />
                )}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </AppPage>
  );
}
