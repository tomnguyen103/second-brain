import type { ApiClient, ChatStreamHandlers } from "@/lib/api/client-types";
import type {
  CaptureResponse,
  ChatRequest,
  ChatResponse,
  ConversationDetailResponse,
  ConversationListResponse,
  DataExportResponse,
  DocumentContentResponse,
  DocumentListResponse,
  FeedbackResponse,
  HealthResponse,
  IngestResponse,
  MessageOut,
  ResearchJob,
  SearchResponse,
  SourceListResponse,
  TaskStatus,
} from "@/lib/api/types";
import {
  DEMO_BRIEFINGS,
  DEMO_DATE,
  DEMO_DOCUMENTS,
  DEMO_EVAL_CANDIDATES,
  DEMO_FEEDBACK_ANALYTICS,
  DEMO_NEGATIVE_FEEDBACK,
  DEMO_RESEARCH_JOBS,
  DEMO_SOURCE_ID,
  DEMO_SOURCE_NAME,
  DEMO_SOURCE_RECORD,
  DEMO_SOURCE_SUMMARY,
  DEMO_SOURCE_URI,
  DEMO_SUGGESTED_PROMPTS,
  DEMO_TASKS,
} from "@/lib/demo/public-demo-data";
import {
  fallbackRankedDocuments,
  searchDemoDocuments,
  toCitation,
  toSearchHit,
  type RankedDemoDocument,
} from "@/lib/demo/static-search";

const READ_ONLY_MESSAGE =
  "This static portfolio demo is read-only. Chat, search, sources, status, feedback previews, tasks, research, and briefings use public-safe fixture data. Writes require the local app.";
const CONVERSATION_STORAGE_KEY = "second-brain.static-demo-conversations";
const MODEL = "static-demo-rag";

let conversationsCache: ConversationDetailResponse[] | null = null;
let nextConversationId = 9100;
let nextMessageId = 9300;
let nextFeedbackId = 3100;

function readOnlyReject<T>(): Promise<T> {
  return Promise.reject(new Error(READ_ONLY_MESSAGE));
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function nowIso(): string {
  return new Date().toISOString();
}

function conversationTitle(message: string): string {
  const trimmed = message.trim().replace(/\s+/g, " ");
  return trimmed.length > 72 ? `${trimmed.slice(0, 69)}...` : trimmed || "Static demo chat";
}

function rankedByDocumentIds(ids: number[]): RankedDemoDocument[] {
  return ids
    .map((id, index) => {
      const document = DEMO_DOCUMENTS.find((item) => item.summary.id === id);
      return document ? { document, score: 1 - index * 0.05 } : null;
    })
    .filter((item): item is RankedDemoDocument => item !== null);
}

function responseFromRankedDocuments(
  req: ChatRequest,
  ranked: RankedDemoDocument[],
  conversationId: number,
  messageId: number,
): ChatResponse {
  const question = req.message.toLowerCase();
  const agentic = Boolean(req.options?.agentic);
  let selected = ranked.length ? ranked.slice(0, 3) : fallbackRankedDocuments();

  let answer: string;
  if (question.includes("regular") && question.includes("agentic")) {
    selected = rankedByDocumentIds([101, 102, 107]);
    answer =
      "Regular RAG is the fast default: it runs one bounded hybrid retrieval pass, fuses full-text and pgvector candidates, and answers with validated citation markers [1]. Agentic RAG is opt-in and read-only: it plans focused subqueries, searches from several angles, merges evidence, and can retry weak evidence before returning through the same citation validator [2]. Use regular RAG for direct questions over a compact set of notes, and Agentic RAG for comparisons, decomposition, or questions that need evidence gathered from several angles [1][2].";
  } else if (question.includes("local") || question.includes("cost") || question.includes("runtime")) {
    selected = rankedByDocumentIds([103, 104]);
    answer =
      "Second Brain defaults to an on-demand local Docker Compose runtime, so Postgres with pgvector, the API, worker, and frontend run only when the owner needs them [1]. That posture avoids idle cloud uptime costs and keeps private knowledge off public demo infrastructure [1]. Optional cloud recipes remain for short demos, but they are not the default production runtime [1].";
  } else if (question.includes("mcp") || question.includes("tools") || question.includes("guard")) {
    selected = rankedByDocumentIds([105]);
    answer =
      "The MCP server exposes trusted local tools over stdio: search notes, list tasks, and send digest are available by default [1]. Durable mutations such as create task and research topic require explicit local opt-in before they can write data [1]. That keeps the portfolio story easy to inspect while preserving intentional action boundaries [1].";
  } else if (question.includes("feedback") || question.includes("eval") || question.includes("quality")) {
    selected = rankedByDocumentIds([106]);
    answer =
      "Feedback becomes reviewable eval coverage instead of automatic promotion [1]. Thumbs-down examples can be labeled and exported as YAML fragments for the source-controlled eval dataset, while MLflow and CI record quality metrics so retrieval, refusals, and prompt changes can be compared over time [1].";
  } else if (question.includes("weak") || question.includes("citation") || question.includes("missing")) {
    selected = rankedByDocumentIds([107, 102]);
    answer =
      "Second Brain expects answers to be grounded in retrieved evidence and validates visible citation markers [1]. If the model produces unsupported or uncited content, the backend can replace it with a safer failure message [1]. Both regular and Agentic RAG return through that citation validator, which keeps weak-context behavior consistent [1][2].";
  } else if (selected.length > 0) {
    answer =
      `From the public demo corpus, the closest evidence is "${selected[0].document.summary.title}" [1]. It shows that this portfolio build is a read-only static preview of the same local-first Second Brain workflow, with cited chat and search backed by public-safe fixture documents [1].`;
  } else {
    answer =
      "I can only answer from the public-safe static demo corpus. Try one of the suggested prompts about regular RAG, Agentic RAG, local-first runtime, MCP tools, feedback/evals, or citation safety.";
  }
  const citations = selected.map((item, index) => toCitation(item, index + 1, index));

  return {
    conversation_id: conversationId,
    message_id: messageId,
    answer,
    citations,
    usage: {
      prompt_tokens: req.message.length,
      completion_tokens: answer.length,
      total_tokens: req.message.length + answer.length,
    },
    model: MODEL,
    latency_ms: agentic ? 68 : 44,
    retrieval: {
      method: agentic ? "agentic_hybrid_static" : "hybrid_static",
      candidates_vector: 7,
      candidates_vector_raw: 7,
      candidates_fulltext: 7,
      fused_returned: citations.length,
      ...(agentic
        ? {
            agentic: {
              enabled: true,
              strategy: "static_demo_planner",
              subqueries: [
                req.message,
                "retrieve operating model",
                "retrieve safety and governance boundaries",
              ],
              subquery_hit_counts: [selected.length, 2, 2],
              deduped_chunks: selected.length,
              selected_chunks: selected.length,
              weak_evidence: citations.length === 0,
              planner_failed: false,
              verifier_used: true,
              fallback_used: false,
              step_budget: {
                max_subqueries: 4,
                recursion_limit: 8,
              },
            },
          }
        : {}),
    },
  };
}

function messageOut(params: {
  id: number;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  response?: ChatResponse;
}): MessageOut {
  return {
    id: params.id,
    role: params.role,
    content: params.content,
    model: params.response?.model ?? null,
    latency_ms: params.response?.latency_ms ?? null,
    created_at: params.createdAt,
    retrievals:
      params.response?.citations.map((citation, index) => ({
        chunk_id: citation.chunk_id,
        rank: index + 1,
        score: citation.score,
        vector_score: citation.vector_score,
        fulltext_score: citation.fulltext_score,
        method: citation.method,
      })) ?? [],
    citations: params.response?.citations ?? [],
  };
}

function createSeedConversation(
  id: number,
  userMessageId: number,
  assistantMessageId: number,
  prompt: string,
  agentic: boolean,
): ConversationDetailResponse {
  const response = responseFromRankedDocuments(
    {
      message: prompt,
      conversation_id: id,
      options: { agentic, include_chunks: true },
    },
    searchDemoDocuments({ q: prompt, topK: 4 }),
    id,
    assistantMessageId,
  );

  return {
    id,
    title: conversationTitle(prompt),
    created_at: "2026-06-07T13:00:00.000Z",
    updated_at: "2026-06-07T13:01:00.000Z",
    messages: [
      messageOut({
        id: userMessageId,
        role: "user",
        content: prompt,
        createdAt: "2026-06-07T13:00:00.000Z",
      }),
      messageOut({
        id: assistantMessageId,
        role: "assistant",
        content: response.answer,
        createdAt: "2026-06-07T13:01:00.000Z",
        response,
      }),
    ],
  };
}

function seedConversations(): ConversationDetailResponse[] {
  return [
    createSeedConversation(9001, 9201, 9202, DEMO_SUGGESTED_PROMPTS[0], true),
    createSeedConversation(9002, 9203, 9204, DEMO_SUGGESTED_PROMPTS[4], false),
  ];
}

function readStoredConversations(): ConversationDetailResponse[] {
  if (typeof window === "undefined") return seedConversations();
  const raw = window.localStorage.getItem(CONVERSATION_STORAGE_KEY);
  if (!raw) return seedConversations();
  try {
    const parsed = JSON.parse(raw) as ConversationDetailResponse[];
    return Array.isArray(parsed) && parsed.length ? parsed : seedConversations();
  } catch {
    return seedConversations();
  }
}

function writeStoredConversations(conversations: ConversationDetailResponse[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CONVERSATION_STORAGE_KEY, JSON.stringify(conversations));
}

function conversations(): ConversationDetailResponse[] {
  if (!conversationsCache) {
    conversationsCache = readStoredConversations();
    nextConversationId =
      Math.max(9100, ...conversationsCache.map((conversation) => conversation.id)) + 1;
    nextMessageId =
      Math.max(
        9300,
        ...conversationsCache.flatMap((conversation) =>
          conversation.messages.map((message) => message.id),
        ),
      ) + 1;
  }
  return conversationsCache;
}

function saveConversation(conversation: ConversationDetailResponse): void {
  const rows = conversations();
  const existingIndex = rows.findIndex((item) => item.id === conversation.id);
  if (existingIndex === -1) rows.unshift(conversation);
  else rows[existingIndex] = conversation;
  conversationsCache = rows;
  writeStoredConversations(rows);
}

function recordChat(req: ChatRequest): ChatResponse {
  const ranked = searchDemoDocuments({
    q: req.message,
    topK: req.top_k ?? 4,
    sourceIds: req.filters?.source_ids ?? undefined,
    tags: req.filters?.tags ?? undefined,
  });
  const createdAt = nowIso();
  let conversation = req.conversation_id
    ? conversations().find((item) => item.id === req.conversation_id)
    : undefined;

  if (!conversation) {
    conversation = {
      id: nextConversationId++,
      title: conversationTitle(req.message),
      created_at: createdAt,
      updated_at: createdAt,
      messages: [],
    };
  }

  const userMessageId = nextMessageId++;
  const assistantMessageId = nextMessageId++;
  const response = responseFromRankedDocuments(req, ranked, conversation.id, assistantMessageId);
  conversation.messages.push(
    messageOut({
      id: userMessageId,
      role: "user",
      content: req.message,
      createdAt,
    }),
    messageOut({
      id: assistantMessageId,
      role: "assistant",
      content: response.answer,
      createdAt: nowIso(),
      response,
    }),
  );
  conversation.updated_at = nowIso();
  saveConversation(conversation);
  return response;
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = globalThis.setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        globalThis.clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

function chunkAnswer(answer: string): string[] {
  const chunks: string[] = [];
  for (let index = 0; index < answer.length; index += 56) {
    chunks.push(answer.slice(index, index + 56));
  }
  return chunks;
}

function documentById(id: number) {
  return DEMO_DOCUMENTS.find((document) => document.summary.id === id);
}

export const demoApi = {
  async getHealth(): Promise<HealthResponse> {
    return { status: "ok", db: "static-fixture", embedder: "static-demo" };
  },

  async getStatus() {
    return {
      status: "ok",
      database: {
        reachable: true,
        migration_current: "static-export",
        migration_head: "static-export",
        migrated: true,
        error: null,
      },
      worker: {
        status: "idle",
        queued: 0,
        running: 0,
        done: 1,
        failed: 0,
        latest_finished_at: DEMO_RESEARCH_JOBS[0]?.finished_at ?? null,
        latest_error: null,
      },
      knowledge: {
        source_count: 1,
        document_count: DEMO_DOCUMENTS.length,
        embedded_document_count: DEMO_DOCUMENTS.length,
        chunk_count: DEMO_DOCUMENTS.length,
        embedding_count: DEMO_DOCUMENTS.length,
        latest_document_at: DEMO_DATE,
      },
      runtime: {
        llm_provider: "static-demo",
        llm_model: MODEL,
        embedding_provider: "static-fixture",
        embedding_model: "public-demo-corpus",
        agentic_rag_enabled: true,
        mcp_mutations_enabled: false,
      },
    };
  },

  capture(): Promise<CaptureResponse> {
    return readOnlyReject();
  },

  ingest(): Promise<IngestResponse> {
    return readOnlyReject();
  },

  ingestUpload(): Promise<IngestResponse> {
    return readOnlyReject();
  },

  async chat(req: ChatRequest): Promise<ChatResponse> {
    return recordChat(req);
  },

  async chatStream(req: ChatRequest, handlers: ChatStreamHandlers): Promise<void> {
    const response = recordChat(req);
    for (const chunk of chunkAnswer(response.answer)) {
      await delay(14, handlers.signal);
      if (!chunk) continue;
      handlers.onDelta({ text: chunk });
    }
    handlers.onComplete(response);
  },

  async search(params: {
    q: string;
    top_k?: number;
    source_ids?: number[];
    tags?: string[];
  }): Promise<SearchResponse> {
    const ranked = searchDemoDocuments({
      q: params.q,
      topK: params.top_k ?? 10,
      sourceIds: params.source_ids,
      tags: params.tags,
    });
    return {
      query: params.q,
      hits: ranked.map(toSearchHit),
      retrieval: {
        method: "hybrid_static",
        corpus: DEMO_SOURCE_NAME,
        source_count: 1,
        document_count: DEMO_DOCUMENTS.length,
      },
    };
  },

  async listConversations(): Promise<ConversationListResponse> {
    const rows = conversations().map((conversation) => ({
      id: conversation.id,
      title: conversation.title,
      created_at: conversation.created_at,
      updated_at: conversation.updated_at,
      message_count: conversation.messages.length,
    }));
    return { conversations: rows, total: rows.length };
  },

  async getConversation(id: number): Promise<ConversationDetailResponse> {
    const conversation = conversations().find((item) => item.id === id);
    if (!conversation) throw new Error(`404 Static demo conversation ${id} was not found`);
    return clone(conversation);
  },

  async submitFeedback(req): Promise<FeedbackResponse> {
    return {
      id: nextFeedbackId++,
      message_id: req.message_id,
      rating: req.rating,
      comment: req.comment ?? null,
      created_at: nowIso(),
    };
  },

  async getFeedbackAnalytics(days = 30) {
    return { ...clone(DEMO_FEEDBACK_ANALYTICS), window_days: days };
  },

  async listNegativeFeedback(params = {}) {
    const limit = params.limit ?? DEMO_NEGATIVE_FEEDBACK.length;
    const offset = params.offset ?? 0;
    const items = DEMO_NEGATIVE_FEEDBACK.slice(offset, offset + limit);
    return {
      items: clone(items),
      total: DEMO_NEGATIVE_FEEDBACK.length,
      limit,
      offset,
    };
  },

  async getFeedbackEvalCandidates() {
    return {
      generated_at: DEMO_DATE,
      source: "static-demo",
      total: DEMO_EVAL_CANDIDATES.length,
      cases: clone(DEMO_EVAL_CANDIDATES),
    };
  },

  promoteFeedbackEvalCandidate() {
    return readOnlyReject();
  },

  async getLatestBriefing() {
    return clone(DEMO_BRIEFINGS[0]);
  },

  async listBriefings(limit = 20) {
    const briefings = DEMO_BRIEFINGS.slice(0, limit);
    return { briefings: clone(briefings), total: DEMO_BRIEFINGS.length };
  },

  async listTasks(params: { status?: TaskStatus; limit?: number } = {}) {
    const filtered = params.status
      ? DEMO_TASKS.filter((task) => task.status === params.status)
      : DEMO_TASKS;
    const tasks = filtered.slice(0, params.limit ?? filtered.length);
    return { tasks: clone(tasks), total: filtered.length };
  },

  createTask() {
    return readOnlyReject();
  },

  updateTask() {
    return readOnlyReject();
  },

  enqueueResearchJob() {
    return readOnlyReject();
  },

  async listResearchJobs(limit = 20) {
    const jobs = DEMO_RESEARCH_JOBS.slice(0, limit);
    return { jobs: clone(jobs), total: DEMO_RESEARCH_JOBS.length };
  },

  async getResearchJob(id: number): Promise<ResearchJob> {
    const job = DEMO_RESEARCH_JOBS.find((item) => item.id === id);
    if (!job) throw new Error(`404 Static demo research job ${id} was not found`);
    return clone(job);
  },

  async listSources(limit = 100): Promise<SourceListResponse> {
    const sources = [DEMO_SOURCE_SUMMARY].slice(0, limit);
    return { sources: clone(sources), total: 1 };
  },

  async updateSource() {
    return readOnlyReject();
  },

  async listSourceDocuments(sourceId: number, limit = 100): Promise<DocumentListResponse> {
    if (sourceId !== DEMO_SOURCE_ID) {
      return { source: clone(DEMO_SOURCE_RECORD), documents: [], total: 0 };
    }
    const documents = DEMO_DOCUMENTS.map((document) => document.summary).slice(0, limit);
    return {
      source: clone(DEMO_SOURCE_RECORD),
      documents: clone(documents),
      total: DEMO_DOCUMENTS.length,
    };
  },

  async getDocumentContent(documentId: number): Promise<DocumentContentResponse> {
    const document = documentById(documentId);
    if (!document) throw new Error(`404 Static demo document ${documentId} was not found`);
    return {
      source: clone(DEMO_SOURCE_RECORD),
      document: clone(document.summary),
      content: document.content,
      content_source: "raw_text",
      truncated: false,
    };
  },

  async updateDocument() {
    return readOnlyReject();
  },

  async updateDocumentContent() {
    return readOnlyReject();
  },

  async deleteDocument() {
    return readOnlyReject();
  },

  async exportSource(sourceId: number): Promise<DataExportResponse> {
    if (sourceId !== DEMO_SOURCE_ID) throw new Error(`404 Static demo source ${sourceId} was not found`);
    return {
      source: {
        id: DEMO_SOURCE_ID,
        type: DEMO_SOURCE_RECORD.type,
        name: DEMO_SOURCE_NAME,
        uri: DEMO_SOURCE_URI,
        config: {
          demo: "static",
          allows_public_uploads: false,
        },
        created_at: DEMO_SOURCE_RECORD.created_at,
      },
      documents: DEMO_DOCUMENTS.map((document) => ({
        ...document.summary,
        content: document.content,
      })),
      document_count: DEMO_DOCUMENTS.length,
    };
  },

  async deleteSource() {
    return readOnlyReject();
  },

  async purgeRetention() {
    return readOnlyReject();
  },
} satisfies ApiClient;
