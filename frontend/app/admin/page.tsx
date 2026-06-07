"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowClockwise,
  CheckCircle,
  Database,
  DownloadSimple,
  HardDrives,
  Key,
  Trash,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react";

import {
  AppButton,
  AppPage,
  Field,
  InlineError,
  LoadingRows,
  Panel,
  PanelHeader,
  SelectControl,
  StatusPill,
  TextInput,
} from "@/components/AppPage";
import { api, getStoredApiToken } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { queryClient } from "@/lib/query-client";

type Tone = "neutral" | "success" | "warning" | "danger";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function formatNumber(value: number | null | undefined): string {
  return new Intl.NumberFormat().format(value ?? 0);
}

function sourceTypeLabel(type: string): string {
  return type.replace(/_/g, " ");
}

function positiveInteger(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const numeric = Number(value);
  return Number.isInteger(numeric) && numeric > 0 ? numeric : undefined;
}

function GovernanceTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  tone?: Tone;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2 text-xs font-semibold text-muted-foreground">
          <span className="shrink-0">{icon}</span>
          <span className="truncate">{label}</span>
        </div>
        <StatusPill tone={tone}>{value}</StatusPill>
      </div>
      <p className="text-xs leading-5 text-foreground">{detail}</p>
    </div>
  );
}

export default function AdminPage() {
  const [adminToken, setAdminToken] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [retentionDays, setRetentionDays] = useState("180");
  const [hasApiToken, setHasApiToken] = useState(false);

  useEffect(() => {
    const syncToken = () => setHasApiToken(Boolean(getStoredApiToken()));
    syncToken();
    window.addEventListener("second-brain-api-token-changed", syncToken);
    return () =>
      window.removeEventListener("second-brain-api-token-changed", syncToken);
  }, []);

  const status = useQuery({
    queryKey: ["status"],
    queryFn: () => api.getStatus(),
    refetchInterval: 15_000,
    retry: false,
  });

  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: () => api.listSources(200),
    retry: false,
  });

  const sourceRows = useMemo(
    () => sources.data?.sources ?? [],
    [sources.data?.sources],
  );
  const selectedSourceId = positiveInteger(sourceId);
  const selectedSource = sourceRows.find(
    (source) => source.id === selectedSourceId,
  );
  const hasAdminToken = adminToken.trim().length > 0;
  const retentionDaysValue = positiveInteger(retentionDays);
  const retentionDaysValid = !retentionDays.trim() || retentionDaysValue != null;
  const deleteConfirmed =
    selectedSource != null && deleteConfirm.trim() === String(selectedSource.id);

  const totals = useMemo(
    () =>
      sourceRows.reduce(
        (acc, source) => ({
          documents: acc.documents + source.document_count,
          chunks: acc.chunks + source.chunk_count,
        }),
        { documents: 0, chunks: 0 },
      ),
    [sourceRows],
  );

  const exportSource = useMutation({
    mutationFn: () => api.exportSource(selectedSource!.id, adminToken.trim()),
  });

  const deleteSource = useMutation({
    mutationFn: () => api.deleteSource(selectedSource!.id, adminToken.trim()),
    onSuccess: async () => {
      setSourceId("");
      setDeleteConfirm("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sources"] }),
        queryClient.invalidateQueries({ queryKey: ["source-documents"] }),
        queryClient.invalidateQueries({ queryKey: ["status"] }),
      ]);
    },
  });

  const purgeRetention = useMutation({
    mutationFn: () =>
      api.purgeRetention({
        older_than_days: retentionDaysValue,
        adminToken: adminToken.trim(),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["status"] });
    },
  });

  function refresh() {
    void status.refetch();
    void sources.refetch();
  }

  function chooseSource(nextSourceId: string) {
    setSourceId(nextSourceId);
    setDeleteConfirm("");
    exportSource.reset();
    deleteSource.reset();
  }

  const databaseOk =
    status.data?.database.reachable && status.data.database.migrated;
  const workerStatus = status.data?.worker.status ?? "unknown";

  return (
    <AppPage
      eyebrow="Admin"
      title="Governance and data safety"
      description="Operate export, erasure, and retention controls with a separate admin guard."
      actions={
        <AppButton
          type="button"
          variant="secondary"
          onClick={refresh}
          disabled={status.isFetching || sources.isFetching}
        >
          <ArrowClockwise size={15} weight="bold" /> Refresh
        </AppButton>
      }
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <GovernanceTile
          icon={
            hasApiToken ? (
              <CheckCircle size={16} weight="bold" />
            ) : (
              <XCircle size={16} weight="bold" />
            )
          }
          label="API bearer"
          value={hasApiToken ? "saved" : "not set"}
          detail={
            hasApiToken
              ? "Normal personal-data requests include the browser bearer token."
              : "Production routes may reject data-ops until the API bearer is saved."
          }
          tone={hasApiToken ? "success" : "warning"}
        />
        <GovernanceTile
          icon={<Key size={16} weight="bold" />}
          label="Admin header"
          value={hasAdminToken ? "entered" : "empty"}
          detail="Sensitive actions send this value only as X-Second-Brain-Admin-Token."
          tone={hasAdminToken ? "success" : "warning"}
        />
        <GovernanceTile
          icon={<Database size={16} weight="bold" />}
          label="Database"
          value={databaseOk ? "current" : "check"}
          detail={
            databaseOk
              ? `Migration ${status.data?.database.migration_current ?? "current"}.`
              : status.data?.database.error ?? "Status endpoint has not confirmed migration state."
          }
          tone={databaseOk ? "success" : "warning"}
        />
        <GovernanceTile
          icon={<HardDrives size={16} weight="bold" />}
          label="Corpus"
          value={`${formatNumber(sourceRows.length)} sources`}
          detail={`${formatNumber(totals.documents)} documents, ${formatNumber(totals.chunks)} chunks visible to the admin console.`}
        />
      </div>

      {(status.error || sources.error) && (
        <div className="grid gap-3 md:grid-cols-2">
          {status.error && (
            <InlineError
              message={errorMessage(status.error, "Status check failed")}
            />
          )}
          {sources.error && (
            <InlineError
              message={errorMessage(sources.error, "Source list failed")}
            />
          )}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
        <div className="grid gap-5">
          <Panel>
            <PanelHeader
              title="Operation setup"
              description="Choose the protected token and source before running data actions."
            />
            <div className="space-y-4 p-4">
              <Field
                label="Admin token"
                hint="Stored only in this page state; refresh clears it."
              >
                <TextInput
                  type="password"
                  value={adminToken}
                  onChange={(event) => setAdminToken(event.target.value)}
                  placeholder="SECOND_BRAIN_ADMIN_TOKEN"
                />
              </Field>

              <Field label="Source">
                <SelectControl
                  value={sourceId}
                  onChange={(event) => chooseSource(event.target.value)}
                  disabled={sources.isLoading || sourceRows.length === 0}
                >
                  <option value="">Choose a source</option>
                  {sourceRows.map((source) => (
                    <option key={source.id} value={source.id}>
                      #{source.id} {source.name} ({source.document_count} docs)
                    </option>
                  ))}
                </SelectControl>
              </Field>

              {sources.isLoading && <LoadingRows rows={3} />}

              {selectedSource ? (
                <div className="rounded-lg border border-border bg-background p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill>#{selectedSource.id}</StatusPill>
                    <StatusPill>{selectedSource.document_count} docs</StatusPill>
                    <StatusPill>{selectedSource.chunk_count} chunks</StatusPill>
                  </div>
                  <p className="mt-3 text-sm font-semibold text-foreground">
                    {selectedSource.name}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    {sourceTypeLabel(selectedSource.type)} / latest document{" "}
                    {formatDateTime(selectedSource.latest_document_at)}
                  </p>
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-border p-3 text-xs leading-5 text-muted-foreground">
                  Select a source to preview the exact export/delete target.
                </div>
              )}
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Runtime guardrails"
              description="Current state from the authenticated status endpoint."
            />
            <div className="space-y-3 p-4 text-xs leading-5 text-muted-foreground">
              <div className="flex items-center justify-between gap-3">
                <span>Worker queue</span>
                <StatusPill
                  tone={
                    workerStatus === "attention" || workerStatus === "unknown"
                      ? "warning"
                      : "success"
                  }
                >
                  {workerStatus}
                </StatusPill>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>LLM mode</span>
                <span className="font-semibold text-foreground">
                  {status.data?.runtime.llm_provider ?? "unknown"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>Last document</span>
                <span className="text-right font-semibold text-foreground">
                  {formatDateTime(status.data?.knowledge.latest_document_at)}
                </span>
              </div>
            </div>
          </Panel>
        </div>

        <div className="grid gap-5">
          <div className="grid gap-5 2xl:grid-cols-2">
            <Panel>
              <PanelHeader
                title="Source export"
                description="Return the selected source and documents as JSON."
              />
              <div className="space-y-3 p-4">
                {exportSource.error && (
                  <InlineError
                    message={errorMessage(exportSource.error, "Export failed")}
                  />
                )}
                <AppButton
                  type="button"
                  onClick={() => exportSource.mutate()}
                  disabled={
                    !hasAdminToken || !selectedSource || exportSource.isPending
                  }
                  variant="secondary"
                >
                  <DownloadSimple size={15} weight="bold" />{" "}
                  {exportSource.isPending ? "Exporting" : "Export source"}
                </AppButton>
                <div className="rounded-lg bg-muted/40 p-3 text-xs leading-5 text-muted-foreground">
                  {selectedSource
                    ? `${selectedSource.name} will export ${selectedSource.document_count} document${selectedSource.document_count === 1 ? "" : "s"}.`
                    : "Choose a source to enable export."}
                </div>
              </div>
            </Panel>

            <Panel>
              <PanelHeader
                title="Source deletion"
                description="Delete the selected source and its indexed subtree."
              />
              <div className="space-y-3 p-4">
                {deleteSource.error && (
                  <InlineError
                    message={errorMessage(deleteSource.error, "Delete failed")}
                  />
                )}
                <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs leading-5 text-destructive">
                  <WarningCircle
                    size={15}
                    weight="bold"
                    className="mt-0.5 shrink-0"
                  />
                  <span>
                    {selectedSource
                      ? `${selectedSource.name} will remove ${selectedSource.document_count} document${selectedSource.document_count === 1 ? "" : "s"} plus chunks and embeddings.`
                      : "Choose a source before enabling deletion."}
                  </span>
                </div>
                <Field label="Type selected source ID">
                  <TextInput
                    value={deleteConfirm}
                    onChange={(event) => setDeleteConfirm(event.target.value)}
                    className="font-mono focus-visible:border-destructive focus-visible:ring-destructive/15"
                    placeholder={
                      selectedSource ? String(selectedSource.id) : "Source ID"
                    }
                  />
                </Field>
                <AppButton
                  type="button"
                  onClick={() => deleteSource.mutate()}
                  disabled={
                    !hasAdminToken ||
                    !selectedSource ||
                    !deleteConfirmed ||
                    deleteSource.isPending
                  }
                  variant="dangerSoft"
                >
                  <Trash size={15} weight="bold" />{" "}
                  {deleteSource.isPending ? "Deleting" : "Delete source"}
                </AppButton>
                {deleteSource.data && (
                  <p className="text-sm text-foreground">
                    Deleted source #{deleteSource.data.source_id} and{" "}
                    {deleteSource.data.documents_deleted} document
                    {deleteSource.data.documents_deleted === 1 ? "" : "s"}.
                  </p>
                )}
              </div>
            </Panel>
          </div>

          <Panel>
            <PanelHeader
              title="Retention purge"
              description="Null retained raw text past the selected age while leaving searchable chunks intact."
            />
            <div className="grid gap-4 p-4 2xl:grid-cols-[16rem_minmax(0,1fr)]">
              <div className="space-y-3">
                <Field label="Older than days">
                  <TextInput
                    value={retentionDays}
                    onChange={(event) => {
                      setRetentionDays(event.target.value);
                      purgeRetention.reset();
                    }}
                    className="font-mono"
                    placeholder="180"
                  />
                </Field>
                <AppButton
                  type="button"
                  onClick={() => purgeRetention.mutate()}
                  disabled={
                    !hasAdminToken ||
                    !retentionDaysValid ||
                    purgeRetention.isPending
                  }
                  variant="secondary"
                >
                  {purgeRetention.isPending ? "Purging" : "Purge raw text"}
                </AppButton>
              </div>
              <div className="space-y-3">
                {!retentionDaysValid && (
                  <InlineError message="Retention days must be a positive whole number." />
                )}
                {purgeRetention.error && (
                  <InlineError
                    message={errorMessage(
                      purgeRetention.error,
                      "Retention purge failed",
                    )}
                  />
                )}
                <div className="rounded-lg bg-muted/40 p-3 text-xs leading-5 text-muted-foreground">
                  Scope: all documents with retained raw text older than{" "}
                  <span className="font-semibold text-foreground">
                    {retentionDaysValue ?? "the configured TTL"}
                  </span>{" "}
                  days. The indexed chunks remain available for search and chat
                  until source erasure.
                </div>
                {purgeRetention.data && (
                  <p className="text-sm text-foreground">
                    Purged {purgeRetention.data.purged} document
                    {purgeRetention.data.purged === 1 ? "" : "s"} older than{" "}
                    {purgeRetention.data.older_than_days} days.
                  </p>
                )}
              </div>
            </div>
          </Panel>

          {exportSource.data && (
            <Panel>
              <PanelHeader
                title="Export result"
                description={`${exportSource.data.source.name} / ${exportSource.data.document_count} document${exportSource.data.document_count === 1 ? "" : "s"}`}
              />
              <div className="p-4">
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-background p-4 text-xs leading-5 text-muted-foreground ring-1 ring-border">
                  {JSON.stringify(exportSource.data, null, 2)}
                </pre>
              </div>
            </Panel>
          )}
        </div>
      </div>

      <Panel>
        <PanelHeader
          title="Local-first checkpoint"
          description="Keep destructive operations manual, source-scoped, audited by the backend, and separate from normal bearer-token access."
        />
        <div className="grid gap-3 p-4 text-xs leading-5 text-muted-foreground md:grid-cols-3">
          <div className="rounded-lg bg-muted/35 p-3">
            Export before erasure when you need a reviewable data snapshot.
          </div>
          <div className="rounded-lg bg-muted/35 p-3">
            Use retention purge for privacy cleanup; use source deletion for
            full erasure.
          </div>
          <div className="rounded-lg bg-muted/35 p-3">
            Do not paste the admin token unless you are actively running one of
            these operations.
          </div>
        </div>
      </Panel>
    </AppPage>
  );
}
