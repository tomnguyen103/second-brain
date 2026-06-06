"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, FilePlus, Plus, Trash } from "@phosphor-icons/react";

import {
  AppButton,
  AppPage,
  Field,
  InlineError,
  Panel,
  PanelHeader,
  SegmentedControl,
  SelectControl,
  StatusPill,
  TextArea,
  TextInput,
} from "@/components/AppPage";
import { api } from "@/lib/api/client";
import { queryClient } from "@/lib/query-client";
import type { IngestResponse, SourceType } from "@/lib/api/types";

type IngestMode = "text" | "upload";

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
  "file_upload",
  "bookmark",
  "github",
  "rss",
  "research_note",
];
const UPLOAD_SOURCE_TYPES: SourceType[] = ["file_upload", "pdf_upload"];

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
  const [mode, setMode] = useState<IngestMode>("text");
  const [sourceType, setSourceType] = useState<SourceType>("manual");
  const [sourceName, setSourceName] = useState("Manual notes");
  const [sourceUri, setSourceUri] = useState("");
  const [documents, setDocuments] = useState<DraftDocument[]>([newDraftDocument("doc-1")]);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadTags, setUploadTags] = useState("");
  const [lastResult, setLastResult] = useState<IngestResponse | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (mode === "upload") {
        const formData = new FormData();
        uploadFiles.forEach((file) => formData.append("files", file, file.name));
        formData.append("source_name", sourceName.trim());
        formData.append("source_type", sourceType);
        if (sourceUri.trim()) formData.append("source_uri", sourceUri.trim());
        if (uploadTags.trim()) formData.append("tags", uploadTags.trim());
        return api.ingestUpload(formData);
      }

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
  const validFiles = uploadFiles.length;
  const canSubmit = sourceName.trim().length > 0
    && !mutation.isPending
    && (mode === "upload" ? validFiles > 0 : validDocs > 0);
  const sourceTypeOptions = mode === "upload" ? UPLOAD_SOURCE_TYPES : SOURCE_TYPES;

  const updateDoc = (id: string, patch: Partial<DraftDocument>) => {
    setDocuments((prev) => prev.map((doc) => (doc.id === id ? { ...doc, ...patch } : doc)));
  };

  const chooseMode = (nextMode: IngestMode) => {
    setMode(nextMode);
    if (nextMode === "upload") {
      if (!UPLOAD_SOURCE_TYPES.includes(sourceType)) setSourceType("file_upload");
      if (sourceName === "Manual notes") setSourceName("Uploaded files");
    } else {
      if (UPLOAD_SOURCE_TYPES.includes(sourceType)) setSourceType("manual");
      if (sourceName === "Uploaded files") setSourceName("Manual notes");
    }
  };

  const addUploadFiles = (files: File[]) => {
    if (files.length === 0) return;
    setUploadFiles((prev) => [...prev, ...files]);
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
            <SegmentedControl
              value={mode}
              options={[
                { value: "text", label: "Text" },
                { value: "upload", label: "Upload" },
              ]}
              onChange={chooseMode}
              className="sm:col-span-3"
            />
            <Field label="Type">
              <SelectControl
                value={sourceType}
                onChange={(event) => setSourceType(event.target.value as SourceType)}
              >
                {sourceTypeOptions.map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </SelectControl>
            </Field>
            <Field label="Name" className="sm:col-span-2">
              <TextInput
                value={sourceName}
                onChange={(event) => setSourceName(event.target.value)}
                placeholder="Source name"
              />
            </Field>
            <Field label="URI" className="sm:col-span-3">
              <TextInput
                value={sourceUri}
                onChange={(event) => setSourceUri(event.target.value)}
                placeholder="Optional file path, URL, or folder"
              />
            </Field>
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

        {mode === "text" ? (
        <Panel>
          <PanelHeader
            title="Documents"
            actions={
              <AppButton
                type="button"
                onClick={() => setDocuments((prev) => [...prev, newDraftDocument(`doc-${Date.now()}`)])}
                variant="secondary"
                size="sm"
              >
                <Plus size={13} weight="bold" /> Add
              </AppButton>
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
                    <AppButton
                      type="button"
                      onClick={() => setDocuments((prev) => prev.filter((item) => item.id !== doc.id))}
                      variant="dangerSoft"
                      size="icon"
                      aria-label="Remove document"
                    >
                      <Trash size={14} />
                    </AppButton>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem]">
                  <Field label="Title">
                    <TextInput
                      value={doc.title}
                      onChange={(event) => updateDoc(doc.id, { title: event.target.value })}
                      placeholder="Document title"
                    />
                  </Field>
                  <Field label="Content type">
                    <TextInput
                      value={doc.contentType}
                      onChange={(event) => updateDoc(doc.id, { contentType: event.target.value })}
                      placeholder="text/plain"
                    />
                  </Field>
                </div>
                <Field label="Content">
                  <TextArea
                    value={doc.content}
                    onChange={(event) => updateDoc(doc.id, { content: event.target.value })}
                    className="min-h-44"
                    placeholder="Paste note or document text"
                  />
                </Field>
                <Field label="Tags">
                  <TextInput
                    value={doc.tags}
                    onChange={(event) => updateDoc(doc.id, { tags: event.target.value })}
                    placeholder="Tags, comma separated"
                  />
                </Field>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
            <p className="text-xs text-muted-foreground">{validDocs} ready document{validDocs === 1 ? "" : "s"}</p>
            <AppButton
              type="button"
              onClick={() => mutation.mutate()}
              disabled={!canSubmit}
            >
              {mutation.isPending ? "Ingesting" : "Ingest"} <ArrowRight size={14} weight="bold" />
            </AppButton>
          </div>
        </Panel>
        ) : (
        <Panel>
          <PanelHeader title="Files" />
          <div className="grid gap-3 p-4">
            <label className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/30 px-4 py-8 text-center transition-colors hover:bg-muted/60">
              <FilePlus size={26} className="text-muted-foreground" />
              <span className="mt-2 text-sm font-semibold text-foreground">Select PDF, TXT, or MD files</span>
              <input
                type="file"
                multiple
                accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
                onChange={(event) => {
                  const selectedFiles = Array.from(event.currentTarget.files ?? []);
                  addUploadFiles(selectedFiles);
                  event.currentTarget.value = "";
                }}
                className="sr-only"
              />
            </label>
            {uploadFiles.length > 0 && (
              <div className="divide-y divide-border rounded-lg ring-1 ring-border">
                {uploadFiles.map((file, index) => (
                  <div key={`${file.name}-${file.lastModified}-${index}`} className="flex items-center justify-between gap-3 p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">{file.name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {(file.size / 1024).toFixed(file.size >= 1024 * 1024 ? 0 : 1)} KB
                      </p>
                    </div>
                    <AppButton
                      type="button"
                      onClick={() => setUploadFiles((prev) => prev.filter((_, i) => i !== index))}
                      variant="dangerSoft"
                      size="icon"
                      aria-label="Remove file"
                    >
                      <Trash size={14} />
                    </AppButton>
                  </div>
                ))}
              </div>
            )}
            <Field label="Tags">
              <TextInput
                value={uploadTags}
                onChange={(event) => setUploadTags(event.target.value)}
                placeholder="Tags, comma separated"
              />
            </Field>
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
            <p className="text-xs text-muted-foreground">{validFiles} ready file{validFiles === 1 ? "" : "s"}</p>
            <AppButton
              type="button"
              onClick={() => mutation.mutate()}
              disabled={!canSubmit}
            >
              {mutation.isPending ? "Ingesting" : "Ingest"} <ArrowRight size={14} weight="bold" />
            </AppButton>
          </div>
        </Panel>
        )}
      </div>
    </AppPage>
  );
}
