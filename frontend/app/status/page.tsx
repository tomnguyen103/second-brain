"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Brain,
  CheckCircle,
  Database,
  Gauge,
  HardDrives,
  Key,
  PlugsConnected,
  Queue,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react";

import { AppButton, AppPage, InlineError, LoadingRows, Panel, PanelHeader, StatusPill } from "@/components/AppPage";
import { api, getStoredApiToken } from "@/lib/api/client";
import type { AppStatusResponse } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

type Tone = "neutral" | "success" | "warning" | "danger";

function booleanTone(value: boolean): Tone {
  return value ? "success" : "danger";
}

function workerTone(status: string): Tone {
  if (status === "attention" || status === "unknown") return "danger";
  if (status === "pending" || status === "active") return "warning";
  return "success";
}

function StatusTile({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail?: string;
  tone?: Tone;
}) {
  return (
    <div className="rounded-lg border border-border/80 bg-background/70 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2 text-xs font-semibold text-muted-foreground">
          <span className="shrink-0">{icon}</span>
          <span className="truncate">{label}</span>
        </div>
        <StatusPill tone={tone}>{value}</StatusPill>
      </div>
      {detail && <p className="text-xs leading-5 text-foreground">{detail}</p>}
    </div>
  );
}

function formatMigration(status: AppStatusResponse | undefined): string {
  const current = status?.database.migration_current;
  const head = status?.database.migration_head;
  if (!current && !head) return "No migration metadata";
  if (current === head) return current ?? "Current";
  return `${current ?? "unknown"} -> ${head ?? "unknown"}`;
}

export default function StatusPage() {
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    const syncToken = () => setHasToken(Boolean(getStoredApiToken()));
    syncToken();
    window.addEventListener("second-brain-api-token-changed", syncToken);
    return () => window.removeEventListener("second-brain-api-token-changed", syncToken);
  }, []);

  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(),
    refetchInterval: 15_000,
    retry: 1,
  });
  const status = useQuery({
    queryKey: ["status"],
    queryFn: () => api.getStatus(),
    refetchInterval: 15_000,
    retry: false,
  });

  const refresh = () => {
    health.refetch();
    status.refetch();
  };
  const healthOk = health.isSuccess && health.data.status === "ok";
  const dbOk = status.data?.database.reachable ?? health.data?.db === "ok";
  const migrated = status.data?.database.migrated ?? false;
  const worker = status.data?.worker;
  const runtime = status.data?.runtime;
  const knowledge = status.data?.knowledge;

  return (
    <AppPage
      eyebrow="Status"
      title="Local runtime"
      description="Check the local API, database migration, worker queue, knowledge index, and model mode."
      actions={
        <AppButton type="button" variant="secondary" onClick={refresh} disabled={health.isFetching || status.isFetching}>
          <Gauge size={15} weight="bold" /> Refresh
        </AppButton>
      }
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="grid gap-5">
          <Panel>
            <PanelHeader title="Runtime checks" />
            {(health.isLoading || status.isLoading) && <LoadingRows rows={4} />}
            <div className="grid gap-3 p-4 md:grid-cols-2">
              <StatusTile
                icon={healthOk ? <CheckCircle size={16} weight="bold" /> : <XCircle size={16} weight="bold" />}
                label="Backend"
                value={healthOk ? "reachable" : "down"}
                detail={healthOk ? "API health endpoint responded." : "The frontend cannot confirm the local API."}
                tone={booleanTone(healthOk)}
              />
              <StatusTile
                icon={<Database size={16} weight="bold" />}
                label="Database"
                value={dbOk ? "reachable" : "down"}
                detail={dbOk ? formatMigration(status.data) : status.data?.database.error ?? "Database check failed."}
                tone={booleanTone(dbOk && migrated)}
              />
              <StatusTile
                icon={<Key size={16} weight="bold" />}
                label="API token"
                value={hasToken ? "saved" : "not set"}
                detail={hasToken ? "Browser will send the normal bearer token." : "Local dev may still be keyless if the backend has no token configured."}
                tone={hasToken ? "success" : "warning"}
              />
              <StatusTile
                icon={<Queue size={16} weight="bold" />}
                label="Worker queue"
                value={worker?.status ?? "unknown"}
                detail={worker ? `${worker.queued} queued, ${worker.running} running, ${worker.failed} failed.` : "Requires API status access."}
                tone={workerTone(worker?.status ?? "unknown")}
              />
            </div>
            {status.error && (
              <div className="px-4 pb-4">
                <InlineError message={status.error instanceof Error ? status.error.message : "Status check failed"} />
              </div>
            )}
          </Panel>

          <Panel>
            <PanelHeader title="Knowledge index" description="Counts from the local Postgres-backed corpus." />
            <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatusTile
                icon={<HardDrives size={16} weight="bold" />}
                label="Sources"
                value={String(knowledge?.source_count ?? 0)}
                detail="Indexed source records."
              />
              <StatusTile
                icon={<Database size={16} weight="bold" />}
                label="Documents"
                value={String(knowledge?.document_count ?? 0)}
                detail={`${knowledge?.embedded_document_count ?? 0} embedded.`}
              />
              <StatusTile
                icon={<PlugsConnected size={16} weight="bold" />}
                label="Chunks"
                value={String(knowledge?.chunk_count ?? 0)}
                detail="Retrievable text units."
              />
              <StatusTile
                icon={<Brain size={16} weight="bold" />}
                label="Embeddings"
                value={String(knowledge?.embedding_count ?? 0)}
                detail="Vector rows available."
              />
            </div>
          </Panel>
        </div>

        <div className="grid gap-5">
          <Panel>
            <PanelHeader title="Model mode" />
            <div className="space-y-3 p-4 text-sm">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">Generation</p>
                <p className="mt-1 font-semibold text-foreground">{runtime?.llm_provider ?? "unknown"}</p>
                <p className="mt-0.5 break-words text-xs leading-5 text-muted-foreground">{runtime?.llm_model ?? "Not reported"}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">Embeddings</p>
                <p className="mt-1 font-semibold text-foreground">{runtime?.embedding_provider ?? "unknown"}</p>
                <p className="mt-0.5 break-words text-xs leading-5 text-muted-foreground">{runtime?.embedding_model ?? "Not reported"}</p>
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                <StatusPill tone={runtime?.agentic_rag_enabled ? "warning" : "neutral"}>
                  Agentic {runtime?.agentic_rag_enabled ? "enabled" : "opt-in off"}
                </StatusPill>
                <StatusPill tone={runtime?.mcp_mutations_enabled ? "warning" : "neutral"}>
                  MCP mutations {runtime?.mcp_mutations_enabled ? "on" : "off"}
                </StatusPill>
              </div>
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Last activity" />
            <div className="space-y-3 p-4 text-xs leading-5 text-muted-foreground">
              <p>
                Latest document:{" "}
                <span className="font-medium text-foreground">
                  {knowledge?.latest_document_at ? formatDateTime(knowledge.latest_document_at) : "none"}
                </span>
              </p>
              <p>
                Latest finished job:{" "}
                <span className="font-medium text-foreground">
                  {worker?.latest_finished_at ? formatDateTime(worker.latest_finished_at) : "none"}
                </span>
              </p>
              {worker?.latest_error && (
                <div className="flex gap-2 rounded-lg bg-destructive/10 p-3 text-destructive">
                  <WarningCircle size={15} weight="bold" className="mt-0.5 shrink-0" />
                  <span>{worker.latest_error}</span>
                </div>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </AppPage>
  );
}
