import type {
  AppStatusResponse,
  Briefing,
  BriefingListResponse,
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
  DocumentListResponse,
  DocumentSummary,
  EvalCandidateExportResponse,
  FeedbackAnalyticsResponse,
  FeedbackRequest,
  FeedbackResponse,
  HealthResponse,
  IngestRequest,
  IngestResponse,
  NegativeFeedbackListResponse,
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

export interface ChatStreamHandlers {
  onDelta: (delta: ChatStreamDelta) => void;
  onComplete: (complete: ChatStreamComplete) => void;
  signal?: AbortSignal;
}

export interface ApiClient {
  getHealth(): Promise<HealthResponse>;
  getStatus(): Promise<AppStatusResponse>;
  capture(req: CaptureRequest): Promise<CaptureResponse>;
  ingest(req: IngestRequest): Promise<IngestResponse>;
  ingestUpload(formData: FormData): Promise<IngestResponse>;
  chat(req: ChatRequest): Promise<ChatResponse>;
  chatStream(req: ChatRequest, handlers: ChatStreamHandlers): Promise<void>;
  search(params: {
    q: string;
    top_k?: number;
    source_ids?: number[];
    tags?: string[];
  }): Promise<SearchResponse>;
  listConversations(): Promise<ConversationListResponse>;
  getConversation(id: number): Promise<ConversationDetailResponse>;
  submitFeedback(req: FeedbackRequest): Promise<FeedbackResponse>;
  getFeedbackAnalytics(days?: number): Promise<FeedbackAnalyticsResponse>;
  listNegativeFeedback(params?: {
    limit?: number;
    offset?: number;
    days?: number;
  }): Promise<NegativeFeedbackListResponse>;
  getFeedbackEvalCandidates(params?: {
    limit?: number;
    offset?: number;
    days?: number;
  }): Promise<EvalCandidateExportResponse>;
  promoteFeedbackEvalCandidate(
    feedbackId: number,
    req: PromoteEvalCandidateRequest,
    adminToken: string,
  ): Promise<PromoteEvalCandidateResponse>;
  getLatestBriefing(): Promise<Briefing>;
  listBriefings(limit?: number): Promise<BriefingListResponse>;
  listTasks(params?: {
    status?: TaskStatus;
    limit?: number;
  }): Promise<TaskListResponse>;
  createTask(req: { title: string; detail?: string | null }): Promise<TaskItem>;
  updateTask(id: number, req: { status: TaskStatus }): Promise<TaskItem>;
  enqueueResearchJob(req: ResearchJobRequest): Promise<ResearchJob>;
  listResearchJobs(limit?: number): Promise<ResearchJobListResponse>;
  getResearchJob(id: number): Promise<ResearchJob>;
  listSources(limit?: number): Promise<SourceListResponse>;
  updateSource(
    sourceId: number,
    req: { name: string },
    adminToken: string,
  ): Promise<SourceRecord>;
  listSourceDocuments(
    sourceId: number,
    limit?: number,
  ): Promise<DocumentListResponse>;
  getDocumentContent(documentId: number): Promise<DocumentContentResponse>;
  updateDocument(
    documentId: number,
    req: { title: string },
    adminToken: string,
  ): Promise<DocumentSummary>;
  updateDocumentContent(
    documentId: number,
    req: { content: string },
    adminToken: string,
  ): Promise<DocumentContentResponse>;
  deleteDocument(
    documentId: number,
    adminToken: string,
  ): Promise<DeleteDocumentResponse>;
  exportSource(sourceId: number, adminToken: string): Promise<DataExportResponse>;
  deleteSource(sourceId: number, adminToken: string): Promise<DeleteSourceResponse>;
  purgeRetention(params: {
    older_than_days?: number;
    adminToken: string;
  }): Promise<PurgeRetentionResponse>;
}
