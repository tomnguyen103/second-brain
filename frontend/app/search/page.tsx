"use client";

import { useState, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { MagnifyingGlass, BookOpen, ArrowRight } from "@phosphor-icons/react";
import { api } from "@/lib/api/client";
import type { SearchHit } from "@/lib/api/types";

/* ── Single result row ── */
function SearchResultRow({ hit, index }: { hit: SearchHit; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        delay: index * 0.04,
        type: "spring",
        stiffness: 300,
        damping: 26,
      }}
      className="group px-6 py-4 flex items-start gap-4 hover:bg-white transition-colors duration-100 cursor-default"
    >
      {/* Rank badge */}
      <div className="shrink-0 mt-0.5 flex h-6 w-6 items-center justify-center rounded-md bg-amber-50 ring-1 ring-amber-100">
        <span className="font-mono text-[11px] font-semibold text-amber-600">
          {index + 1}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-3 mb-1">
          <p className="text-sm font-semibold text-zinc-900 tracking-tight leading-snug">
            {hit.document_title}
          </p>
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-[10px] text-zinc-400 bg-zinc-100 rounded px-1.5 py-0.5 font-medium">
              {hit.source_name}
            </span>
            <span className="font-mono text-[10px] text-zinc-400">
              {hit.score.toFixed(4)}
            </span>
          </div>
        </div>
        <p className="text-xs text-zinc-500 leading-relaxed line-clamp-3">
          {hit.snippet}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <span className="text-[10px] text-zinc-400 bg-zinc-100 rounded-full px-2 py-0.5">
            {hit.method}
          </span>
          {hit.vector_score != null && (
            <span className="font-mono text-[10px] text-zinc-400">
              vec {hit.vector_score.toFixed(3)}
            </span>
          )}
          {hit.fulltext_score != null && (
            <span className="font-mono text-[10px] text-zinc-400">
              fts {hit.fulltext_score.toFixed(3)}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

/* ── Skeleton row ── */
function SearchSkeleton() {
  return (
    <div className="px-6 py-4 flex items-start gap-4">
      <div className="h-6 w-6 rounded-md skeleton-shimmer shrink-0 mt-0.5" />
      <div className="flex-1 space-y-2">
        <div className="h-4 rounded skeleton-shimmer w-2/5" />
        <div className="h-3 rounded skeleton-shimmer w-full" />
        <div className="h-3 rounded skeleton-shimmer w-3/4" />
      </div>
    </div>
  );
}

/* ── Empty state ── */
function SearchEmpty({ query }: { query: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-zinc-100">
        <BookOpen size={20} className="text-zinc-400" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-zinc-700">No results for &ldquo;{query}&rdquo;</p>
        <p className="text-xs text-zinc-400 mt-0.5">
          Try a different query or ingest more notes.
        </p>
      </div>
    </div>
  );
}

/* ── Main page ── */
function SearchPageContent() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";
  const [inputValue, setInputValue] = useState(initialQ);
  const [query, setQuery] = useState(initialQ);
  const [sourceIds, setSourceIds] = useState("");
  const [tags, setTags] = useState("");

  const { data, isFetching, error } = useQuery({
    queryKey: ["search", query, sourceIds, tags],
    queryFn: () =>
      api.search({
        q: query,
        top_k: 10,
        source_ids: sourceIds
          ? sourceIds.split(",").map((s) => parseInt(s.trim(), 10)).filter((n) => !isNaN(n))
          : undefined,
        tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : undefined,
      }),
    enabled: query.length > 0,
  });

  const handleSearch = () => {
    const q = inputValue.trim();
    if (q) setQuery(q);
  };

  return (
    <div className="flex flex-col h-full bg-zinc-50">
      <header className="px-6 py-3 border-b border-zinc-200 bg-white">
        <span className="text-sm font-medium text-zinc-500 tracking-tight">
          Semantic Search
        </span>
      </header>

      {/* Search bar */}
      <div className="px-6 pt-5 pb-4 bg-white border-b border-zinc-200">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <MagnifyingGlass
              size={15}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400"
            />
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search your knowledge base…"
              autoFocus
              className="w-full h-10 rounded-xl border border-zinc-200 bg-zinc-50 pl-9 pr-4 text-sm text-zinc-900 placeholder:text-zinc-400 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-400/30 transition-all"
              aria-label="Search query"
            />
          </div>
          <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={handleSearch}
            disabled={!inputValue.trim() || isFetching}
            className="flex items-center gap-1.5 h-10 px-4 rounded-xl bg-amber-500 text-white text-sm font-medium hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm shadow-amber-200"
          >
            Search
            <ArrowRight size={14} weight="bold" />
          </motion.button>
        </div>

        {/* Filter row */}
        <div className="flex flex-wrap gap-3 mt-3">
          <label className="flex items-center gap-2 text-xs text-zinc-500">
            Source IDs:
            <input
              value={sourceIds}
              onChange={(e) => setSourceIds(e.target.value)}
              placeholder="1,2,3"
              className="h-6 w-20 rounded-lg border border-zinc-200 bg-transparent px-2 text-xs text-zinc-600 outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400/30 transition-all"
            />
          </label>
          <label className="flex items-center gap-2 text-xs text-zinc-500">
            Tags:
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="ml,notes"
              className="h-6 w-24 rounded-lg border border-zinc-200 bg-transparent px-2 text-xs text-zinc-600 outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400/30 transition-all"
            />
          </label>
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto divide-y divide-zinc-100">
        {isFetching && (
          <>
            {[0, 1, 2].map((i) => <SearchSkeleton key={i} />)}
          </>
        )}

        {error && !isFetching && (
          <div className="px-6 py-8 text-center">
            <p className="text-sm text-red-500">
              {error instanceof Error ? error.message : "Search failed"}
            </p>
          </div>
        )}

        {data && !isFetching && (
          <AnimatePresence>
            {data.hits.length === 0 ? (
              <SearchEmpty query={data.query} />
            ) : (
              <>
                <div className="px-6 py-2.5 bg-zinc-50/80">
                  <span className="text-[11px] text-zinc-400 font-medium">
                    {data.hits.length} result{data.hits.length !== 1 ? "s" : ""} for{" "}
                    <span className="text-zinc-600">&ldquo;{data.query}&rdquo;</span>
                  </span>
                </div>
                {data.hits.map((hit, i) => (
                  <SearchResultRow key={hit.chunk_id} hit={hit} index={i} />
                ))}
              </>
            )}
          </AnimatePresence>
        )}

        {!query && !isFetching && !data && (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-50 ring-1 ring-amber-100">
              <MagnifyingGlass size={20} weight="bold" className="text-amber-400" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-zinc-700">Search your notes</p>
              <p className="text-xs text-zinc-400 mt-0.5">
                Hybrid vector + full-text search across ingested documents.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center"><div className="text-xs text-zinc-400">Loading…</div></div>}>
      <SearchPageContent />
    </Suspense>
  );
}
