import type {
  ChatRequest,
  ChatResponse,
  ConversationDetailResponse,
  ConversationListResponse,
  FeedbackRequest,
  FeedbackResponse,
  SearchResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
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
};
