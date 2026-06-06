"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Circle, ListChecks, Plus, X } from "@phosphor-icons/react";

import { AppButton, AppPage, EmptyState, Field, InlineError, LoadingRows, Panel, PanelHeader, StatusPill, TextArea, TextInput } from "@/components/AppPage";
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
            <Field label="Title">
              <TextInput
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Task title"
              />
            </Field>
            <Field label="Detail">
              <TextArea
                value={detail}
                onChange={(event) => setDetail(event.target.value)}
                className="min-h-24"
                placeholder="Optional notes"
              />
            </Field>
            <AppButton
              type="button"
              onClick={() => createTask.mutate()}
              disabled={!title.trim() || createTask.isPending}
              className="w-full"
            >
              <Plus size={14} weight="bold" /> {createTask.isPending ? "Creating" : "Create"}
            </AppButton>
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
                    <AppButton
                      key={item.label}
                      onClick={() => setFilter(item.value)}
                      variant="quiet"
                      size="sm"
                      className={`${
                        active ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      }`}
                    >
                      {item.label}
                    </AppButton>
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
                    <AppButton
                      type="button"
                      onClick={() => updateTask.mutate({ id: task.id, status: "open" })}
                      disabled={task.status === "open" || updateTask.isPending}
                      variant="quiet"
                      size="icon"
                      aria-label="Mark open"
                    >
                      <Circle size={15} />
                    </AppButton>
                    <AppButton
                      type="button"
                      onClick={() => updateTask.mutate({ id: task.id, status: "done" })}
                      disabled={task.status === "done" || updateTask.isPending}
                      variant="quiet"
                      size="icon"
                      className="hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-950/30 dark:hover:text-emerald-300"
                      aria-label="Mark done"
                    >
                      <Check size={15} weight="bold" />
                    </AppButton>
                    <AppButton
                      type="button"
                      onClick={() => updateTask.mutate({ id: task.id, status: "cancelled" })}
                      disabled={task.status === "cancelled" || updateTask.isPending}
                      variant="dangerSoft"
                      size="icon"
                      aria-label="Cancel task"
                    >
                      <X size={15} weight="bold" />
                    </AppButton>
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
