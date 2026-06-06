// Types generated from ADR-0007 and Phase 2 backend schemas.
// Regenerate with: npm run gen-types (requires backend running on localhost:8000)

export interface ChatFilters {
  source_ids?: number[] | null;
  tags?: string[] | null;
}

export interface ChatOptions {
  private_mode?: boolean;
  include_chunks?: boolean;
  agentic?: boolean;
}

export interface ChatRequest {
  message: string;
  conversation_id?: number | null;
  top_k?: number | null;
  filters?: ChatFilters;
  options?: ChatOptions;
}

export interface Citation {
  marker: number;
  chunk_id: number;
  document_id: number;
  document_title: string;
  source_id: number;
  source_name: string;
  snippet: string | null;
  score: number | null;
  vector_score: number | null;
  fulltext_score: number | null;
  method: "vector" | "fulltext" | "hybrid";
  char_start: number | null;
  char_end: number | null;
}

export interface Usage {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

export interface AgenticTrace {
  enabled: boolean;
  strategy: string;
  subqueries: string[];
  subquery_hit_counts: number[];
  deduped_chunks: number;
  selected_chunks: number;
  weak_evidence: boolean;
  planner_failed: boolean;
  verifier_used: boolean;
  fallback_used: boolean;
  step_budget: {
    max_subqueries: number;
    recursion_limit: number;
  };
}

export interface ChatRetrieval {
  method: string;
  candidates_vector?: number;
  candidates_vector_raw?: number;
  candidates_fulltext?: number;
  fused_returned: number;
  agentic?: AgenticTrace;
  [key: string]: unknown;
}

export interface ChatResponse {
  conversation_id: number;
  message_id: number;
  answer: string;
  citations: Citation[];
  usage: Usage;
  model: string | null;
  latency_ms: number;
  retrieval: ChatRetrieval;
}

export interface ChatStreamDelta {
  text: string;
}

export type ChatStreamComplete = ChatResponse;

export interface CaptureRequest {
  url: string;
  title?: string | null;
  notes?: string | null;
  selected_text?: string | null;
  tags?: string[];
}

export interface CaptureResponse {
  source_id: number;
  capture_url: string;
  document: IngestDocumentOut;
  summary: IngestResponse["summary"];
}

export interface SearchHit {
  chunk_id: number;
  document_id: number;
  document_title: string;
  source_id: number;
  source_name: string;
  snippet: string;
  score: number;
  vector_score: number | null;
  fulltext_score: number | null;
  method: string;
  char_start: number | null;
  char_end: number | null;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  retrieval: Record<string, unknown>;
}

export interface ConversationSummary {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
  total: number;
}

export interface RetrievalOut {
  chunk_id: number;
  rank: number;
  score: number | null;
  vector_score: number | null;
  fulltext_score: number | null;
  method: string;
}

export interface MessageOut {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  model: string | null;
  latency_ms: number | null;
  created_at: string;
  retrievals: RetrievalOut[];
  citations: Citation[];
}

export interface ConversationDetailResponse {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: MessageOut[];
}

export interface FeedbackRequest {
  message_id: number;
  rating: 1 | -1;
  comment?: string | null;
}

export interface FeedbackResponse {
  id: number;
  message_id: number;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface FeedbackTrendBucket {
  date: string;
  total: number;
  positive: number;
  negative: number;
  negative_rate: number;
}

export interface FeedbackModelStats {
  model: string;
  total: number;
  positive: number;
  negative: number;
  negative_rate: number;
  avg_latency_ms: number | null;
}

export interface FeedbackDocumentStats {
  document_id: number;
  document_title: string;
  source_id: number;
  source_name: string;
  negative: number;
}

export interface FeedbackAnalyticsResponse {
  window_days: number;
  total: number;
  positive: number;
  negative: number;
  negative_rate: number;
  latest_feedback_at: string | null;
  trend: FeedbackTrendBucket[];
  by_model: FeedbackModelStats[];
  top_negative_documents: FeedbackDocumentStats[];
}

export interface FeedbackRetrievalContext {
  chunk_id: number;
  rank: number;
  score: number | null;
  vector_score: number | null;
  fulltext_score: number | null;
  method: string;
}

export interface NegativeFeedbackItem {
  feedback_id: number;
  rating: -1;
  comment: string | null;
  feedback_created_at: string;
  conversation_id: number;
  conversation_title: string | null;
  message_id: number;
  message_created_at: string;
  question_message_id: number | null;
  question: string | null;
  answer: string;
  model: string | null;
  latency_ms: number | null;
  retrievals: FeedbackRetrievalContext[];
  citations: Citation[];
}

export interface NegativeFeedbackListResponse {
  items: NegativeFeedbackItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvalCandidate {
  id: string;
  question: string;
  expected_docs: string[];
  expected_keywords: string[];
  expect_refusal: boolean;
  metadata: Record<string, unknown>;
}

export interface EvalCandidateExportResponse {
  generated_at: string;
  source: string;
  total: number;
  cases: EvalCandidate[];
}

export interface EvalCaseReviewConfirmations {
  expected_docs: boolean;
  expected_keywords: boolean;
  expect_refusal: boolean;
}

export interface PromoteEvalCandidateRequest {
  id: string;
  question: string;
  expected_docs: string[];
  expected_keywords: string[];
  expect_refusal: boolean;
  confirmations: EvalCaseReviewConfirmations;
}

export interface PromoteEvalCandidateResponse {
  promoted_at: string;
  dataset_path: string;
  case: EvalCandidate;
}

export interface HealthResponse {
  status: string;
  db: string;
  embedder: string;
}

export interface AppStatusResponse {
  status: "ok" | "attention" | string;
  database: {
    reachable: boolean;
    migration_current: string | null;
    migration_head: string | null;
    migrated: boolean;
    error: string | null;
  };
  worker: {
    status: "idle" | "active" | "pending" | "attention" | "unknown" | string;
    queued: number;
    running: number;
    done: number;
    failed: number;
    latest_finished_at: string | null;
    latest_error: string | null;
  };
  knowledge: {
    source_count: number;
    document_count: number;
    embedded_document_count: number;
    chunk_count: number;
    embedding_count: number;
    latest_document_at: string | null;
  };
  runtime: {
    llm_provider: string;
    llm_model: string;
    embedding_provider: string;
    embedding_model: string;
    agentic_rag_enabled: boolean;
    mcp_mutations_enabled: boolean;
  };
}

export type SourceType =
  | "manual"
  | "notes_folder"
  | "github"
  | "rss"
  | "pdf_upload"
  | "file_upload"
  | "bookmark"
  | "research_note";

export interface IngestSource {
  type: SourceType;
  name: string;
  uri?: string | null;
  config?: Record<string, unknown>;
}

export interface IngestDocument {
  title: string;
  content: string;
  external_id?: string | null;
  content_type?: string | null;
  metadata?: Record<string, unknown>;
  tags?: string[];
}

export interface IngestRequest {
  source: IngestSource;
  documents: IngestDocument[];
}

export interface IngestDocumentOut {
  document_id: number | null;
  title: string;
  status: string;
  content_hash: string;
  chunk_count: number;
  embedded_count: number;
  duplicate_of: number | null;
  error: string | null;
}

export interface IngestResponse {
  source_id: number;
  documents: IngestDocumentOut[];
  summary: {
    received: number;
    embedded: number;
    duplicates: number;
    failed: number;
    chunks_created: number;
  };
}

export interface Briefing {
  id: number;
  generated_at: string;
  period_start: string;
  period_end: string;
  summary: string;
  body_markdown: string;
  document_count: number;
  model: string | null;
}

export interface BriefingListResponse {
  briefings: Briefing[];
  total: number;
}

export type TaskStatus = "open" | "done" | "cancelled";

export interface TaskItem {
  id: number;
  title: string;
  detail: string | null;
  status: TaskStatus;
  created_at: string;
}

export interface TaskListResponse {
  tasks: TaskItem[];
  total: number;
}

export type JobStatus = "queued" | "running" | "done" | "failed";

export interface ResearchSourceText {
  title?: string | null;
  text: string;
  uri?: string | null;
}

export interface ResearchJobRequest {
  topic: string;
  source_urls?: string[];
  source_texts?: ResearchSourceText[];
}

export interface ResearchJob {
  id: number;
  type: "research";
  topic: string | null;
  status: JobStatus;
  attempts: number;
  last_error: string | null;
  scheduled_at: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  result: Record<string, unknown> | null;
}

export interface ResearchJobListResponse {
  jobs: ResearchJob[];
  total: number;
}

export interface SourceRecord {
  id: number;
  type: SourceType | string;
  name: string;
  uri: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceSummary extends SourceRecord {
  document_count: number;
  chunk_count: number;
  latest_document_at: string | null;
}

export interface SourceListResponse {
  sources: SourceSummary[];
  total: number;
}

export interface DocumentSummary {
  id: number;
  source_id: number;
  title: string;
  external_id: string | null;
  content_type: string | null;
  content_hash: string;
  status: string;
  tags: string[];
  chunk_count: number;
  raw_text_available: boolean;
  ingested_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  source: SourceRecord;
  documents: DocumentSummary[];
  total: number;
}

export interface DocumentContentResponse {
  source: SourceRecord;
  document: DocumentSummary;
  content: string | null;
  content_source: "raw_text" | "chunks" | "unavailable" | string;
  truncated: boolean;
}

export interface DeleteSourceResponse {
  source_id: number;
  documents_deleted: number;
}

export interface DeleteDocumentResponse {
  document_id: number;
  source_id: number;
  chunks_deleted: number;
}

export interface PurgeRetentionResponse {
  older_than_days: number;
  purged: number;
}

export interface DataExportResponse {
  source: {
    id: number;
    type: string;
    name: string;
    uri: string | null;
    config: Record<string, unknown>;
    created_at: string | null;
  };
  documents: Array<Record<string, unknown>>;
  document_count: number;
}
