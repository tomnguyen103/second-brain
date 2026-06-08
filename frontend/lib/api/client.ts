import type {
  AppStatusResponse,
  CaptureRequest,
  CaptureResponse,
  ChatRequest,
  ChatResponse,
  ChatStreamComplete,
  ChatStreamDelta,
  ConversationDetailResponse,
  ConversationListResponse,
  DataExportResponse,
  DeleteDocumentResponse,
  DeleteSourceResponse,
  DocumentContentResponse,
  EvalCandidateExportResponse,
  FeedbackAnalyticsResponse,
  FeedbackRequest,
  FeedbackResponse,
  Briefing,
  BriefingListResponse,
  HealthResponse,
  NegativeFeedbackListResponse,
  DocumentListResponse,
  DocumentSummary,
  IngestRequest,
  IngestResponse,
  PromoteEvalCandidateRequest,
  PromoteEvalCandidateResponse,
  PurgeRetentionResponse,
  ResearchJob,
  ResearchJobListResponse,
  ResearchJobRequest,
  SearchResponse,
  SourceListResponse,
  SourceRecord,
  TaskItem,
  TaskListResponse,
  TaskStatus,
} from "./types";
import type { ApiClient, ChatStreamHandlers } from "./client-types";
import { demoApi } from "./demo-client";
import { STATIC_DEMO_MODE } from "@/lib/demo/config";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_TOKEN_STORAGE_KEY = "second-brain.api-token";

export function getStoredApiToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(API_TOKEN_STORAGE_KEY) ?? "";
}

export function setStoredApiToken(token: string): void {
  if (typeof window === "undefined") return;
  const trimmed = token.trim();
  if (trimmed) {
    window.localStorage.setItem(API_TOKEN_STORAGE_KEY, trimmed);
  } else {
    window.localStorage.removeItem(API_TOKEN_STORAGE_KEY);
  }
  window.dispatchEvent(new Event("second-brain-api-token-changed"));
}

export class ChatStreamUnavailableError extends Error {
  constructor(message = "Streaming chat is unavailable") {
    super(message);
    this.name = "ChatStreamUnavailableError";
  }
}

export function isChatStreamUnavailableError(
  error: unknown,
): error is ChatStreamUnavailableError {
  return error instanceof ChatStreamUnavailableError;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = buildHeaders(init?.headers, init?.body);
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
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

function isFormDataBody(body?: BodyInit | null): boolean {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

function buildHeaders(
  initHeaders?: HeadersInit,
  body?: BodyInit | null,
): Headers {
  const headers = new Headers(initHeaders);
  if (!headers.has("Content-Type") && !isFormDataBody(body)) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Authorization")) {
    const token = getStoredApiToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

function parseSseBlock(block: string): { event: string; data: unknown } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) as unknown };
  } catch {
    return null;
  }
}

async function streamChat(
  req: ChatRequest,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(req),
    signal: handlers.signal,
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
    if ([404, 409, 501].includes(res.status)) {
      throw new ChatStreamUnavailableError(message);
    }
    throw new Error(`${res.status} ${message}`);
  }

  if (!res.body) {
    throw new ChatStreamUnavailableError(
      "This browser cannot read streaming responses",
    );
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");

    let separator = buffer.indexOf("\n\n");
    while (separator !== -1) {
      const block = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      const parsed = parseSseBlock(block);
      if (parsed?.event === "delta") {
        handlers.onDelta(parsed.data as ChatStreamDelta);
      } else if (parsed?.event === "complete") {
        completed = true;
        handlers.onComplete(parsed.data as ChatStreamComplete);
      } else if (parsed?.event === "error") {
        const data = parsed.data as { message?: unknown };
        throw new Error(
          typeof data.message === "string"
            ? data.message
            : "Streaming chat failed",
        );
      }
      separator = buffer.indexOf("\n\n");
    }

    if (done) break;
  }

  if (buffer.trim()) {
    const parsed = parseSseBlock(buffer.trim());
    if (parsed?.event === "complete") {
      completed = true;
      handlers.onComplete(parsed.data as ChatStreamComplete);
    }
  }

  if (!completed) {
    throw new Error("Streaming chat ended before completion");
  }
}

export const liveApi = {
  getHealth(): Promise<HealthResponse> {
    return apiFetch("/health");
  },

  getStatus(): Promise<AppStatusResponse> {
    return apiFetch("/status");
  },

  capture(req: CaptureRequest): Promise<CaptureResponse> {
    return apiFetch("/capture", { method: "POST", body: JSON.stringify(req) });
  },

  ingest(req: IngestRequest): Promise<IngestResponse> {
    return apiFetch("/ingest", { method: "POST", body: JSON.stringify(req) });
  },

  ingestUpload(formData: FormData): Promise<IngestResponse> {
    return apiFetch("/ingest/upload", { method: "POST", body: formData });
  },

  chat(req: ChatRequest): Promise<ChatResponse> {
    return apiFetch("/chat", { method: "POST", body: JSON.stringify(req) });
  },

  chatStream: streamChat,

  search(params: {
    q: string;
    top_k?: number;
    source_ids?: number[];
    tags?: string[];
  }): Promise<SearchResponse> {
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

  listNegativeFeedback(
    params: { limit?: number; offset?: number; days?: number } = {},
  ): Promise<NegativeFeedbackListResponse> {
    const sp = new URLSearchParams();
    if (params.limit) sp.set("limit", String(params.limit));
    if (params.offset) sp.set("offset", String(params.offset));
    if (params.days) sp.set("days", String(params.days));
    const suffix = sp.toString() ? `?${sp}` : "";
    return apiFetch(`/feedback/negative${suffix}`);
  },

  getFeedbackEvalCandidates(
    params: { limit?: number; offset?: number; days?: number } = {},
  ): Promise<EvalCandidateExportResponse> {
    const sp = new URLSearchParams();
    if (params.limit) sp.set("limit", String(params.limit));
    if (params.offset) sp.set("offset", String(params.offset));
    if (params.days) sp.set("days", String(params.days));
    const suffix = sp.toString() ? `?${sp}` : "";
    return apiFetch(`/feedback/eval-candidates${suffix}`);
  },

  promoteFeedbackEvalCandidate(
    feedbackId: number,
    req: PromoteEvalCandidateRequest,
    adminToken: string,
  ): Promise<PromoteEvalCandidateResponse> {
    return apiFetch(`/feedback/eval-candidates/${feedbackId}/promote`, {
      method: "POST",
      headers: { "X-Second-Brain-Admin-Token": adminToken },
      body: JSON.stringify(req),
    });
  },

  getLatestBriefing(): Promise<Briefing> {
    return apiFetch("/briefing");
  },

  listBriefings(limit = 20): Promise<BriefingListResponse> {
    return apiFetch(`/briefing/history?limit=${limit}`);
  },

  listTasks(
    params: { status?: TaskStatus; limit?: number } = {},
  ): Promise<TaskListResponse> {
    const sp = new URLSearchParams();
    if (params.status) sp.set("status", params.status);
    if (params.limit) sp.set("limit", String(params.limit));
    const suffix = sp.toString() ? `?${sp}` : "";
    return apiFetch(`/tasks${suffix}`);
  },

  createTask(req: {
    title: string;
    detail?: string | null;
  }): Promise<TaskItem> {
    return apiFetch("/tasks", { method: "POST", body: JSON.stringify(req) });
  },

  updateTask(id: number, req: { status: TaskStatus }): Promise<TaskItem> {
    return apiFetch(`/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(req),
    });
  },

  enqueueResearchJob(req: ResearchJobRequest): Promise<ResearchJob> {
    return apiFetch("/research/jobs", {
      method: "POST",
      body: JSON.stringify(req),
    });
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

  updateSource(
    sourceId: number,
    req: { name: string },
    adminToken: string,
  ): Promise<SourceRecord> {
    return apiFetch(`/sources/${sourceId}`, {
      method: "PATCH",
      headers: { "X-Second-Brain-Admin-Token": adminToken },
      body: JSON.stringify(req),
    });
  },

  listSourceDocuments(
    sourceId: number,
    limit = 100,
  ): Promise<DocumentListResponse> {
    return apiFetch(`/sources/${sourceId}/documents?limit=${limit}`);
  },

  getDocumentContent(documentId: number): Promise<DocumentContentResponse> {
    return apiFetch(`/documents/${documentId}/content`);
  },

  updateDocument(
    documentId: number,
    req: { title: string },
    adminToken: string,
  ): Promise<DocumentSummary> {
    return apiFetch(`/documents/${documentId}`, {
      method: "PATCH",
      headers: { "X-Second-Brain-Admin-Token": adminToken },
      body: JSON.stringify(req),
    });
  },

  updateDocumentContent(
    documentId: number,
    req: { content: string },
    adminToken: string,
  ): Promise<DocumentContentResponse> {
    return apiFetch(`/documents/${documentId}/content`, {
      method: "PATCH",
      headers: { "X-Second-Brain-Admin-Token": adminToken },
      body: JSON.stringify(req),
    });
  },

  deleteDocument(
    documentId: number,
    adminToken: string,
  ): Promise<DeleteDocumentResponse> {
    return apiFetch(`/documents/${documentId}`, {
      method: "DELETE",
      headers: { "X-Second-Brain-Admin-Token": adminToken },
    });
  },

  exportSource(
    sourceId: number,
    adminToken: string,
  ): Promise<DataExportResponse> {
    return apiFetch(`/data/export?source_id=${sourceId}`, {
      headers: { "X-Second-Brain-Admin-Token": adminToken },
    });
  },

  deleteSource(
    sourceId: number,
    adminToken: string,
  ): Promise<DeleteSourceResponse> {
    return apiFetch(`/data/sources/${sourceId}`, {
      method: "DELETE",
      headers: { "X-Second-Brain-Admin-Token": adminToken },
    });
  },

  purgeRetention(params: {
    older_than_days?: number;
    adminToken: string;
  }): Promise<PurgeRetentionResponse> {
    const suffix = params.older_than_days
      ? `?older_than_days=${params.older_than_days}`
      : "";
    return apiFetch(`/admin/retention/purge${suffix}`, {
      method: "POST",
      headers: { "X-Second-Brain-Admin-Token": params.adminToken },
    });
  },
} satisfies ApiClient;

export type { ApiClient, ChatStreamHandlers } from "./client-types";

export const api: ApiClient = STATIC_DEMO_MODE ? demoApi : liveApi;
