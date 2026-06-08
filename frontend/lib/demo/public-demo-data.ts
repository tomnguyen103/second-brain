import type {
  Briefing,
  DocumentSummary,
  EvalCandidate,
  FeedbackAnalyticsResponse,
  NegativeFeedbackItem,
  ResearchJob,
  SourceRecord,
  SourceSummary,
  TaskItem,
} from "@/lib/api/types";

export const DEMO_SOURCE_ID = 1;
export const DEMO_SOURCE_NAME = "Second Brain Public Demo Corpus";
export const DEMO_SOURCE_URI = "https://github.com/tomnguyen103/second-brain";
export const DEMO_DATE = "2026-06-07T15:00:00.000Z";

export const DEMO_SUGGESTED_PROMPTS = [
  "Compare regular RAG and Agentic RAG in Second Brain. When should I use each?",
  "What does the local-first runtime protect against?",
  "What MCP tools does Second Brain expose, and which actions are guarded?",
  "How does the feedback and eval workflow improve answer quality?",
  "What happens when evidence is weak or citations are missing?",
] as const;

export interface DemoCorpusDocument {
  summary: DocumentSummary;
  content: string;
}

const COMMON_TAGS = ["public-demo", "second-brain"];

function documentSummary(
  id: number,
  title: string,
  externalId: string,
  tags: string[],
): DocumentSummary {
  return {
    id,
    source_id: DEMO_SOURCE_ID,
    title,
    external_id: externalId,
    content_type: "text/plain",
    content_hash: `demo-${externalId}`,
    status: "embedded",
    tags: [...COMMON_TAGS, ...tags],
    chunk_count: 1,
    raw_text_available: true,
    ingested_at: DEMO_DATE,
    created_at: DEMO_DATE,
    updated_at: DEMO_DATE,
  };
}

export const DEMO_SOURCE_RECORD: SourceRecord = {
  id: DEMO_SOURCE_ID,
  type: "manual",
  name: DEMO_SOURCE_NAME,
  uri: DEMO_SOURCE_URI,
  created_at: DEMO_DATE,
  updated_at: DEMO_DATE,
};

export const DEMO_DOCUMENTS: DemoCorpusDocument[] = [
  {
    summary: documentSummary(101, "Regular RAG operating model", "public-demo-regular-rag", [
      "rag",
      "hybrid-search",
      "pgvector",
    ]),
    content:
      "Regular RAG in Second Brain is the fast default path for direct questions. It runs one bounded hybrid retrieval pass over the selected sources, combining PostgreSQL full-text search with pgvector semantic search. Candidates are fused, the strongest chunks are sent to the configured LLM, and the final answer must include validated citation markers. Use regular RAG when the question can be answered from a compact set of retrieved notes without extra planning.",
  },
  {
    summary: documentSummary(102, "Agentic RAG operating model", "public-demo-agentic-rag", [
      "rag",
      "agentic-rag",
      "langgraph",
    ]),
    content:
      "Agentic RAG in Second Brain is an opt-in read-only retrieval workflow built with LangGraph. It plans multiple focused subqueries, searches existing notes for each subquery, merges the evidence, and can retry weak evidence before returning an answer through the same citation validator as regular RAG. Use Agentic RAG for comparison, decomposition, or questions that need evidence gathered from several angles. The agentic path does not mutate notes, tasks, or source data.",
  },
  {
    summary: documentSummary(103, "Local-first runtime posture", "public-demo-local-first", [
      "local-first",
      "docker-compose",
      "runtime",
    ]),
    content:
      "Second Brain defaults to a local-first Docker Compose runtime. The owner starts PostgreSQL with pgvector, the FastAPI backend, the worker, and the Next.js frontend only when needed. This avoids paying for idle cloud uptime and keeps normal use on the owner's machine. Optional cloud deployment recipes remain for short demos, but they are not the default production posture. Uploaded private knowledge should not be stored in a public demo database.",
  },
  {
    summary: documentSummary(104, "Source management and governance", "public-demo-source-governance", [
      "sources",
      "governance",
      "admin",
    ]),
    content:
      "The web workspace includes a Sources management home where source folders and files can be inspected, renamed, edited, exported, or deleted through guarded workflows. Destructive actions require the admin token, and raw-text retention can be purged without removing searchable chunks until source erasure is requested. The public demo corpus is intentionally small and public-safe so visitors can query the app without uploading private documents.",
  },
  {
    summary: documentSummary(105, "MCP tools and action boundaries", "public-demo-mcp-tools", [
      "mcp",
      "tools",
      "actions",
    ]),
    content:
      "Second Brain exposes MCP tools over stdio for trusted local clients. Search notes, list tasks, and send digest are available by default. Mutating actions such as create task and research topic require explicit local opt-in before they can write durable data. This boundary keeps the demo and normal runtime inspectable: read-only retrieval is easy to show, while mutations stay guarded and intentional.",
  },
  {
    summary: documentSummary(106, "Feedback and eval workflow", "public-demo-feedback-eval", [
      "feedback",
      "eval",
      "mlflow",
    ]),
    content:
      "Second Brain turns feedback into reviewable eval coverage instead of promoting cases automatically. Thumbs-down feedback can be reviewed, labeled, and exported as YAML fragments for the source-controlled eval dataset. The eval harness records metrics with MLflow and CI runs a deterministic quality gate. This makes retrieval quality, refusal behavior, and prompt changes easier to compare over time.",
  },
  {
    summary: documentSummary(107, "Citation safety and weak-context behavior", "public-demo-citation-safety", [
      "citations",
      "safety",
      "rag",
    ]),
    content:
      "Chat answers in Second Brain are expected to be grounded in retrieved evidence. The backend validates citation markers and can replace unsupported or uncited model responses with a safer failure message. Retrieval also tracks weak context so the app can refuse when evidence is too thin. Regular RAG and Agentic RAG both return through the citation validator, which keeps the visible answer format consistent.",
  },
];

export const DEMO_SOURCE_SUMMARY: SourceSummary = {
  ...DEMO_SOURCE_RECORD,
  document_count: DEMO_DOCUMENTS.length,
  chunk_count: DEMO_DOCUMENTS.reduce((total, doc) => total + doc.summary.chunk_count, 0),
  latest_document_at: DEMO_DATE,
};

export const DEMO_TASKS: TaskItem[] = [
  {
    id: 701,
    title: "Review portfolio demo access posture",
    detail: "Keep the hosted static data public-safe and use the passcode gate only as casual access control.",
    status: "open",
    created_at: "2026-06-07T13:05:00.000Z",
  },
  {
    id: 702,
    title: "Seed public demo corpus locally",
    detail: "Run python -m app.demo.seed_public before showing the full backend-powered local demo.",
    status: "done",
    created_at: "2026-06-07T12:10:00.000Z",
  },
];

export const DEMO_RESEARCH_JOBS: ResearchJob[] = [
  {
    id: 801,
    type: "research",
    topic: "Static portfolio demo deployment options",
    status: "done",
    attempts: 1,
    last_error: null,
    scheduled_at: "2026-06-07T12:22:00.000Z",
    started_at: "2026-06-07T12:23:00.000Z",
    finished_at: "2026-06-07T12:24:00.000Z",
    created_at: "2026-06-07T12:22:00.000Z",
    result: {
      status: "stored",
      document_id: 107,
      evidence_count: 3,
    },
  },
];

export const DEMO_BRIEFINGS: Briefing[] = [
  {
    id: 901,
    generated_at: "2026-06-07T14:30:00.000Z",
    period_start: "2026-06-06T14:30:00.000Z",
    period_end: "2026-06-07T14:30:00.000Z",
    summary: "Public demo corpus is ready for cited chat and search.",
    body_markdown:
      "The current demo corpus highlights regular RAG, Agentic RAG, local-first runtime posture, MCP action boundaries, source governance, feedback review, and citation safety. The hosted Netlify build is static and read-only, while the local app keeps the full FastAPI, Postgres, worker, MCP, and eval workflow available on demand.",
    document_count: DEMO_DOCUMENTS.length,
    model: "static-demo-fixture",
  },
];

export const DEMO_FEEDBACK_ANALYTICS: FeedbackAnalyticsResponse = {
  window_days: 30,
  total: 9,
  positive: 7,
  negative: 2,
  negative_rate: 2 / 9,
  latest_feedback_at: "2026-06-07T14:00:00.000Z",
  trend: [
    { date: "2026-05-29", total: 1, positive: 1, negative: 0, negative_rate: 0 },
    { date: "2026-05-30", total: 0, positive: 0, negative: 0, negative_rate: 0 },
    { date: "2026-05-31", total: 2, positive: 1, negative: 1, negative_rate: 0.5 },
    { date: "2026-06-01", total: 1, positive: 1, negative: 0, negative_rate: 0 },
    { date: "2026-06-02", total: 1, positive: 1, negative: 0, negative_rate: 0 },
    { date: "2026-06-03", total: 1, positive: 1, negative: 0, negative_rate: 0 },
    { date: "2026-06-04", total: 0, positive: 0, negative: 0, negative_rate: 0 },
    { date: "2026-06-05", total: 1, positive: 0, negative: 1, negative_rate: 1 },
    { date: "2026-06-06", total: 1, positive: 1, negative: 0, negative_rate: 0 },
    { date: "2026-06-07", total: 1, positive: 1, negative: 0, negative_rate: 0 },
  ],
  by_model: [
    {
      model: "static-demo-rag",
      total: 9,
      positive: 7,
      negative: 2,
      negative_rate: 2 / 9,
      avg_latency_ms: 54,
    },
  ],
  top_negative_documents: [
    {
      document_id: 107,
      document_title: "Citation safety and weak-context behavior",
      source_id: DEMO_SOURCE_ID,
      source_name: DEMO_SOURCE_NAME,
      negative: 1,
    },
    {
      document_id: 106,
      document_title: "Feedback and eval workflow",
      source_id: DEMO_SOURCE_ID,
      source_name: DEMO_SOURCE_NAME,
      negative: 1,
    },
  ],
};

export const DEMO_EVAL_CANDIDATES: EvalCandidate[] = [
  {
    id: "feedback-3001",
    question: "What happens when evidence is weak or citations are missing?",
    expected_docs: ["Citation safety and weak-context behavior"],
    expected_keywords: ["validated citation markers", "weak context", "safer failure message"],
    expect_refusal: true,
    metadata: {
      feedback_id: 3001,
      demo_visibility: "public-safe",
    },
  },
];

export const DEMO_NEGATIVE_FEEDBACK: NegativeFeedbackItem[] = [
  {
    feedback_id: 3001,
    rating: -1,
    comment: "Good candidate for checking weak-context refusal wording.",
    feedback_created_at: "2026-06-05T14:20:00.000Z",
    conversation_id: 9002,
    conversation_title: "Citation safety and weak context",
    message_id: 9204,
    message_created_at: "2026-06-05T14:18:00.000Z",
    question_message_id: 9203,
    question: "What happens when evidence is weak or citations are missing?",
    answer:
      "Second Brain expects chat answers to be grounded in retrieved evidence and can replace unsupported responses with a safer failure message when evidence is too thin [1].",
    model: "static-demo-rag",
    latency_ms: 52,
    retrievals: [
      {
        chunk_id: 1007,
        rank: 1,
        score: 0.98,
        vector_score: 0.91,
        fulltext_score: 0.95,
        method: "hybrid",
      },
    ],
    citations: [],
  },
];
