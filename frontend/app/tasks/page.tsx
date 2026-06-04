"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Circle, ListChecks, Plus, X } from "@phosphor-icons/react";

import { AppPage, EmptyState, InlineError, LoadingRows, Panel, PanelHeader, StatusPill } from "@/components/AppPage";
import { api } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { queryClient } from "@/lib/query-client";
import type { TaskStatus } from "@/lib/api/types";

const FILTERS: Array<{ label: string; value?: TaskStatus }> = [
  { label: "All" },
  { label: "Open", value: "open" },
  { label: "Done", value: "done" },
  { label: "Cancelled", value: "cancelled" },
];

function statusTone(status: TaskStatus): "neutral" | "success" | "warning" | "danger" {
  if (status === "done") return "success";
  if (status === "cancelled") return "danger";
  return "warning";
}

export default function TasksPage() {
  const [filter, setFilter] = useState<TaskStatus | undefined>("open");
  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");

  const tasks = useQuery({
    queryKey: ["tasks", filter],
    queryFn: () => api.listTasks({ status: filter, limit: 100 }),
  });

  const createTask = useMutation({
    mutationFn: () => api.createTask({ title: title.trim(), detail: detail.trim() || null }),
    onSuccess: () => {
      setTitle("");
      setDetail("");
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const updateTask = useMutation({
    mutationFn: ({ id, status }: { id: number; status: TaskStatus }) => api.updateTask(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  });

  return (
    <AppPage
      eyebrow="Tasks"
      title="Task list"
      description="Create and update the same tasks exposed through the MCP server."
    >
      <div className="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Create task" />
          <div className="space-y-3 p-4">
            {createTask.error && (
              <InlineError message={createTask.error instanceof Error ? createTask.error.message : "Task creation failed"} />
            )}
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
              Title
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                placeholder="Task title"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
              Detail
              <textarea
                value={detail}
                onChange={(event) => setDetail(event.target.value)}
                className="min-h-24 resize-y rounded-lg border border-input bg-background px-2.5 py-2 text-sm leading-6 text-foreground outline-none transition-colors focus:border-amber-400 focus:ring-3 focus:ring-amber-400/15"
                placeholder="Optional notes"
              />
            </label>
            <button
              type="button"
              onClick={() => createTask.mutate()}
              disabled={!title.trim() || createTask.isPending}
              className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-amber-500 px-3 text-sm font-semibold text-white transition-colors hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus size={14} weight="bold" /> {createTask.isPending ? "Creating" : "Create"}
            </button>
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            title="Tasks"
            actions={
              <div className="flex flex-wrap gap-1">
                {FILTERS.map((item) => {
                  const active = filter === item.value;
                  return (
                    <button
                      key={item.label}
                      onClick={() => setFilter(item.value)}
                      className={`h-7 rounded-lg px-2.5 text-xs font-semibold transition-colors ${
                        active ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      }`}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
            }
          />
          {tasks.isLoading && <LoadingRows rows={5} />}
          {tasks.error && !tasks.isLoading && (
            <div className="p-4">
              <InlineError message={tasks.error instanceof Error ? tasks.error.message : "Task list failed"} />
            </div>
          )}
          {tasks.data?.tasks.length === 0 && (
            <EmptyState
              icon={<ListChecks size={20} />}
              title="No tasks in this view"
              body="Create one or switch filters to review older work."
            />
          )}
          {tasks.data && tasks.data.tasks.length > 0 && (
            <div className="divide-y divide-border">
              {tasks.data.tasks.map((task) => (
                <div key={task.id} className="grid gap-3 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusPill tone={statusTone(task.status)}>{task.status}</StatusPill>
                      <p className="truncate text-sm font-semibold text-foreground">{task.title}</p>
                    </div>
                    {task.detail && <p className="mt-1 text-xs leading-5 text-muted-foreground">{task.detail}</p>}
                    <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                      #{task.id} / {formatDateTime(task.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => updateTask.mutate({ id: task.id, status: "open" })}
                      disabled={task.status === "open" || updateTask.isPending}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-30"
                      aria-label="Mark open"
                    >
                      <Circle size={15} />
                    </button>
                    <button
                      type="button"
                      onClick={() => updateTask.mutate({ id: task.id, status: "done" })}
                      disabled={task.status === "done" || updateTask.isPending}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-emerald-50 hover:text-emerald-700 disabled:opacity-30 dark:hover:bg-emerald-950/30 dark:hover:text-emerald-300"
                      aria-label="Mark done"
                    >
                      <Check size={15} weight="bold" />
                    </button>
                    <button
                      type="button"
                      onClick={() => updateTask.mutate({ id: task.id, status: "cancelled" })}
                      disabled={task.status === "cancelled" || updateTask.isPending}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-30"
                      aria-label="Cancel task"
                    >
                      <X size={15} weight="bold" />
                    </button>
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
