import type { Citation, SearchHit } from "@/lib/api/types";
import { DEMO_DOCUMENTS, DEMO_SOURCE_ID, DEMO_SOURCE_NAME, type DemoCorpusDocument } from "./public-demo-data";

const STOP_WORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "be",
  "by",
  "can",
  "does",
  "for",
  "from",
  "how",
  "in",
  "is",
  "it",
  "of",
  "on",
  "or",
  "the",
  "this",
  "to",
  "use",
  "what",
  "when",
  "with",
]);

export interface RankedDemoDocument {
  document: DemoCorpusDocument;
  score: number;
}

function tokens(value: string): string[] {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, " ")
    .split(/\s+/)
    .filter((token) => token.length > 1 && !STOP_WORDS.has(token));
}

function matchesFilters(
  document: DemoCorpusDocument,
  sourceIds?: number[],
  tags?: string[],
): boolean {
  if (sourceIds?.length && !sourceIds.includes(DEMO_SOURCE_ID)) return false;
  if (!tags?.length) return true;
  const docTags = new Set(document.summary.tags.map((tag) => tag.toLowerCase()));
  return tags.every((tag) => docTags.has(tag.toLowerCase()));
}

function scoreDocument(document: DemoCorpusDocument, queryTerms: string[]): number {
  if (queryTerms.length === 0) return 0.1;

  const titleTerms = tokens(document.summary.title);
  const tagTerms = document.summary.tags.flatMap(tokens);
  const contentTerms = tokens(document.content);

  let score = 0;
  for (const term of queryTerms) {
    if (titleTerms.includes(term)) score += 4;
    if (tagTerms.includes(term)) score += 3;
    if (contentTerms.includes(term)) score += 1;
  }

  if (queryTerms.includes("agentic") && document.summary.title.includes("Agentic")) score += 6;
  if (queryTerms.includes("regular") && document.summary.title.includes("Regular")) score += 6;
  if (queryTerms.includes("local-first") && document.summary.title.includes("Local-first")) score += 6;
  if (queryTerms.includes("mcp") && document.summary.title.includes("MCP")) score += 6;
  if (queryTerms.includes("feedback") && document.summary.title.includes("Feedback")) score += 6;
  if (queryTerms.includes("citation") && document.summary.title.includes("Citation")) score += 6;
  if (queryTerms.includes("weak") && document.summary.title.includes("Citation")) score += 4;

  return score;
}

export function searchDemoDocuments(params: {
  q: string;
  topK?: number;
  sourceIds?: number[];
  tags?: string[];
}): RankedDemoDocument[] {
  const queryTerms = tokens(params.q);
  const topK = params.topK ?? 5;

  return DEMO_DOCUMENTS
    .filter((document) => matchesFilters(document, params.sourceIds, params.tags))
    .map((document) => ({ document, score: scoreDocument(document, queryTerms) }))
    .filter((ranked) => ranked.score > 0 || queryTerms.length === 0)
    .sort((a, b) => {
      const scoreDiff = b.score - a.score;
      if (scoreDiff !== 0) return scoreDiff;
      return a.document.summary.id - b.document.summary.id;
    })
    .slice(0, topK);
}

export function toSearchHit(ranked: RankedDemoDocument, index: number): SearchHit {
  const score = Number((0.72 + Math.min(ranked.score, 20) / 100 - index * 0.015).toFixed(4));
  return {
    chunk_id: 1000 + ranked.document.summary.id - 100,
    document_id: ranked.document.summary.id,
    document_title: ranked.document.summary.title,
    source_id: DEMO_SOURCE_ID,
    source_name: DEMO_SOURCE_NAME,
    snippet: ranked.document.content,
    score,
    vector_score: Number((score - 0.07).toFixed(4)),
    fulltext_score: Number((score - 0.03).toFixed(4)),
    method: "hybrid",
    char_start: 0,
    char_end: Math.min(ranked.document.content.length, 420),
  };
}

export function toCitation(
  ranked: RankedDemoDocument,
  marker: number,
  index = marker - 1,
): Citation {
  const hit = toSearchHit(ranked, index);
  return {
    marker,
    chunk_id: hit.chunk_id,
    document_id: hit.document_id,
    document_title: hit.document_title,
    source_id: hit.source_id,
    source_name: hit.source_name,
    snippet: hit.snippet,
    score: hit.score,
    vector_score: hit.vector_score,
    fulltext_score: hit.fulltext_score,
    method: "hybrid",
    char_start: hit.char_start,
    char_end: hit.char_end,
  };
}

export function fallbackRankedDocuments(): RankedDemoDocument[] {
  return DEMO_DOCUMENTS.slice(0, 3).map((document, index) => ({
    document,
    score: 0.3 - index * 0.05,
  }));
}
