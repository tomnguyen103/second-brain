// Types generated from ADR-0007 and Phase 2 backend schemas.
// Regenerate with: npm run gen-types (requires backend running on localhost:8000)

export interface ChatFilters {
  source_ids?: number[] | null;
  tags?: string[] | null;
}

export interface ChatOptions {
  private_mode?: boolean;
  include_chunks?: boolean;
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

export interface ChatResponse {
  conversation_id: number;
  message_id: number;
  answer: string;
  citations: Citation[];
  usage: Usage;
  model: string | null;
  latency_ms: number;
  retrieval: {
    method: string;
    candidates_vector: number;
    candidates_fulltext: number;
    fused_returned: number;
  };
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

export interface HealthResponse {
  status: string;
  db: string;
  embedder: string;
}
