"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { DownloadSimple, Shield, Trash, WarningCircle } from "@phosphor-icons/react";

import { AppButton, AppPage, Field, InlineError, Panel, PanelHeader, StatusPill, TextInput } from "@/components/AppPage";
import { api } from "@/lib/api/client";
import { queryClient } from "@/lib/query-client";

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [retentionDays, setRetentionDays] = useState("180");

  const numericSourceId = Number(sourceId);
  const hasSource = Number.isInteger(numericSourceId) && numericSourceId > 0;
  const hasToken = token.trim().length > 0;

  const exportSource = useMutation({
    mutationFn: () => api.exportSource(numericSourceId, token.trim()),
  });

  const deleteSource = useMutation({
    mutationFn: () => api.deleteSource(numericSourceId, token.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      setDeleteConfirm("");
    },
  });

  const purgeRetention = useMutation({
    mutationFn: () => api.purgeRetention({
      older_than_days: retentionDays.trim() ? Number(retentionDays) : undefined,
      adminToken: token.trim(),
    }),
  });

  return (
    <AppPage
      eyebrow="Admin"
      title="Data operations"
      description="Run guarded source export, source deletion, and retention actions."
    >
      <div className="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Authorization" />
          <div className="space-y-3 p-4">
            <Field label="Admin token">
              <TextInput
                type="password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                placeholder="Bearer token"
              />
            </Field>
            <Field label="Source ID">
              <TextInput
                value={sourceId}
                onChange={(event) => setSourceId(event.target.value)}
                className="font-mono"
                placeholder="1"
              />
            </Field>
            <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs leading-5 text-muted-foreground">
              <Shield size={15} weight="bold" className="mt-0.5 shrink-0" />
              <span>The token stays in this browser session and is sent only as the additional admin header.</span>
            </div>
          </div>
        </Panel>

        <div className="grid gap-5">
          <Panel>
            <PanelHeader title="Source export" />
            <div className="space-y-3 p-4">
              {exportSource.error && (
                <InlineError message={exportSource.error instanceof Error ? exportSource.error.message : "Export failed"} />
              )}
              <AppButton
                type="button"
                onClick={() => exportSource.mutate()}
                disabled={!hasToken || !hasSource || exportSource.isPending}
                variant="secondary"
              >
                <DownloadSimple size={15} weight="bold" /> {exportSource.isPending ? "Exporting" : "Export source"}
              </AppButton>
              {exportSource.data && (
                <div className="rounded-lg bg-muted/40 p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <StatusPill tone="success">{exportSource.data.document_count} documents</StatusPill>
                    <span className="text-xs font-semibold text-foreground">{exportSource.data.source.name}</span>
                  </div>
                  <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs leading-5 text-muted-foreground">
                    {JSON.stringify(exportSource.data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Source deletion" />
            <div className="space-y-3 p-4">
              {deleteSource.error && (
                <InlineError message={deleteSource.error instanceof Error ? deleteSource.error.message : "Delete failed"} />
              )}
              <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs leading-5 text-destructive">
                <WarningCircle size={15} weight="bold" className="mt-0.5 shrink-0" />
                <span>Deletes the source and cascades through its documents, chunks, and embeddings.</span>
              </div>
              <Field label="Type the source ID to confirm">
                <TextInput
                  value={deleteConfirm}
                  onChange={(event) => setDeleteConfirm(event.target.value)}
                  className="font-mono focus-visible:border-destructive focus-visible:ring-destructive/15"
                  placeholder={hasSource ? String(numericSourceId) : "Source ID"}
                />
              </Field>
              <AppButton
                type="button"
                onClick={() => deleteSource.mutate()}
                disabled={!hasToken || !hasSource || deleteConfirm !== String(numericSourceId) || deleteSource.isPending}
                variant="dangerSoft"
              >
                <Trash size={15} weight="bold" /> {deleteSource.isPending ? "Deleting" : "Delete source"}
              </AppButton>
              {deleteSource.data && (
                <p className="text-sm text-foreground">
                  Deleted source #{deleteSource.data.source_id} and {deleteSource.data.documents_deleted} document{deleteSource.data.documents_deleted === 1 ? "" : "s"}.
                </p>
              )}
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Retention purge" />
            <div className="space-y-3 p-4">
              {purgeRetention.error && (
                <InlineError message={purgeRetention.error instanceof Error ? purgeRetention.error.message : "Retention purge failed"} />
              )}
              <Field label="Older than days" className="max-w-xs">
                <TextInput
                  value={retentionDays}
                  onChange={(event) => setRetentionDays(event.target.value)}
                  className="font-mono"
                  placeholder="180"
                />
              </Field>
              <AppButton
                type="button"
                onClick={() => purgeRetention.mutate()}
                disabled={!hasToken || purgeRetention.isPending}
                variant="secondary"
              >
                Purge raw text
              </AppButton>
              {purgeRetention.data && (
                <p className="text-sm text-foreground">
                  Purged {purgeRetention.data.purged} document{purgeRetention.data.purged === 1 ? "" : "s"} older than {purgeRetention.data.older_than_days} days.
                </p>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </AppPage>
  );
}
