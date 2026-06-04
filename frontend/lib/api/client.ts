import type {
  ChatRequest,
  ChatResponse,
  ConversationDetailResponse,
  ConversationListResponse,
  DataExportResponse,
  DeleteSourceResponse,
  EvalCandidateExportResponse,
  FeedbackAnalyticsResponse,
  FeedbackRequest,
  FeedbackResponse,
  Briefing,
  BriefingListResponse,
  NegativeFeedbackListResponse,
  DocumentListResponse,
  IngestRequest,
  IngestResponse,
  PurgeRetentionResponse,
  ResearchJob,
  ResearchJobListResponse,
  ResearchJobRequest,
  SearchResponse,
  SourceListResponse,
  TaskItem,
  TaskListResponse,
  TaskStatus,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    let message = text || res.statusText;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === "string") message = parsed.detail;
    } catch {
      // Keep the raw body when it is not JSON.
    }
    throw new Error(`${res.status} ${message}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  ingest(req: IngestRequest): Promise<IngestResponse> {
    return apiFetch("/ingest", { method: "POST", body: JSON.stringify(req) });
  },

  chat(req: ChatRequest): Promise<ChatResponse> {
    return apiFetch("/chat", { method: "POST", body: JSON.stringify(req) });
  },

  search(params: { q: string; top_k?: number; source_ids?: number[]; tags?: string[] }): Promise<SearchResponse> {
    const sp = new URLSearchParams({ q: params.q });
    if (params.top_k) sp.set("top_k", String(params.top_k));
    params.source_ids?.forEach((id) => sp.append("source_ids", String(id)));
    params.tags?.forEach((t) => sp.append("tags", t));
    return apiFetch(`/search?${sp}`);
  },

  listConversations(): Promise<ConversationListResponse> {
    return apiFetch("/conversations");
  },

  getConversation(id: number): Promise<ConversationDetailResponse> {
    return apiFetch(`/conversations/${id}`);
  },

  submitFeedback(req: FeedbackRequest): Promise<FeedbackResponse> {
    return apiFetch("/feedback", { method: "POST", body: JSON.stringify(req) });
  },

  getFeedbackAnalytics(days = 30): Promise<FeedbackAnalyticsResponse> {
    return apiFetch(`/feedback/analytics?days=${days}`);
  },

  listNegativeFeedback(params: { limit?: number; offset?: number; days?: number } = {}): Promise<NegativeFeedbackListResponse> {
    const sp = new URLSearchParams();
    if (params.limit) sp.set("limit", String(params.limit));
    if (params.offset) sp.set("offset", String(params.offset));
    if (params.days) sp.set("days", String(params.days));
    const suffix = sp.toString() ? `?${sp}` : "";
    return apiFetch(`/feedback/negative${suffix}`);
  },

  getFeedbackEvalCandidates(params: { limit?: number; offset?: number; days?: number } = {}): Promise<EvalCandidateExportResponse> {
    const sp = new URLSearchParams();
    if (params.limit) sp.set("limit", String(params.limit));
    if (params.offset) sp.set("offset", String(params.offset));
    if (params.days) sp.set("days", String(params.days));
    const suffix = sp.toString() ? `?${sp}` : "";
    return apiFetch(`/feedback/eval-candidates${suffix}`);
  },

  getLatestBriefing(): Promise<Briefing> {
    return apiFetch("/briefing");
  },

  listBriefings(limit = 20): Promise<BriefingListResponse> {
    return apiFetch(`/briefing/history?limit=${limit}`);
  },

  listTasks(params: { status?: TaskStatus; limit?: number } = {}): Promise<TaskListResponse> {
    const sp = new URLSearchParams();
    if (params.status) sp.set("status", params.status);
    if (params.limit) sp.set("limit", String(params.limit));
    const suffix = sp.toString() ? `?${sp}` : "";
    return apiFetch(`/tasks${suffix}`);
  },

  createTask(req: { title: string; detail?: string | null }): Promise<TaskItem> {
    return apiFetch("/tasks", { method: "POST", body: JSON.stringify(req) });
  },

  updateTask(id: number, req: { status: TaskStatus }): Promise<TaskItem> {
    return apiFetch(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(req) });
  },

  enqueueResearchJob(req: ResearchJobRequest): Promise<ResearchJob> {
    return apiFetch("/research/jobs", { method: "POST", body: JSON.stringify(req) });
  },

  listResearchJobs(limit = 20): Promise<ResearchJobListResponse> {
    return apiFetch(`/research/jobs?limit=${limit}`);
  },

  getResearchJob(id: number): Promise<ResearchJob> {
    return apiFetch(`/research/jobs/${id}`);
  },

  listSources(limit = 100): Promise<SourceListResponse> {
    return apiFetch(`/sources?limit=${limit}`);
  },

  listSourceDocuments(sourceId: number, limit = 100): Promise<DocumentListResponse> {
    return apiFetch(`/sources/${sourceId}/documents?limit=${limit}`);
  },

  exportSource(sourceId: number, adminToken: string): Promise<DataExportResponse> {
    return apiFetch(`/data/export?source_id=${sourceId}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
  },

  deleteSource(sourceId: number, adminToken: string): Promise<DeleteSourceResponse> {
    return apiFetch(`/data/sources/${sourceId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${adminToken}` },
    });
  },

  purgeRetention(params: { older_than_days?: number; adminToken: string }): Promise<PurgeRetentionResponse> {
    const suffix = params.older_than_days ? `?older_than_days=${params.older_than_days}` : "";
    return apiFetch(`/admin/retention/purge${suffix}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${params.adminToken}` },
    });
  },
};
