"use client";

import { useState, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { MagnifyingGlass, BookOpen, ArrowRight } from "@phosphor-icons/react";
import { api } from "@/lib/api/client";
import type { SearchHit } from "@/lib/api/types";

function SearchResultRow({ hit, index }: { hit: SearchHit; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, type: "spring", stiffness: 300, damping: 26 }}
      className="group px-5 py-4 flex items-start gap-3.5 hover:bg-muted/50 transition-colors duration-100"
    >
      <div className="shrink-0 mt-0.5 flex h-6 w-6 items-center justify-center rounded-md bg-amber-50 dark:bg-amber-950/40 ring-1 ring-amber-100 dark:ring-amber-900/60">
        <span className="font-mono text-[11px] font-bold text-amber-600 dark:text-amber-400">{index + 1}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2 mb-1">
          <p className="text-sm font-semibold text-foreground tracking-tight leading-snug">{hit.document_title}</p>
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-[10px] bg-muted text-muted-foreground rounded px-1.5 py-0.5 font-medium">{hit.source_name}</span>
            <span className="font-mono text-[10px] text-muted-foreground">{hit.score.toFixed(4)}</span>
          </div>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">{hit.snippet}</p>
        <div className="flex items-center gap-2 mt-1.5">
          <span className="text-[10px] bg-muted text-muted-foreground rounded-full px-2 py-0.5">{hit.method}</span>
          {hit.vector_score != null && <span className="font-mono text-[10px] text-muted-foreground/70">vec {hit.vector_score.toFixed(3)}</span>}
          {hit.fulltext_score != null && <span className="font-mono text-[10px] text-muted-foreground/70">fts {hit.fulltext_score.toFixed(3)}</span>}
        </div>
      </div>
    </motion.div>
  );
}

function SearchPageContent() {
  const sp = useSearchParams();
  const initialQ = sp.get("q") ?? "";
  const [inputValue, setInputValue] = useState(initialQ);
  const [query, setQuery] = useState(initialQ);
  const [sourceIds, setSourceIds] = useState("");
  const [tags, setTags] = useState("");
  const [focused, setFocused] = useState(false);

  const { data, isFetching, error } = useQuery({
    queryKey: ["search", query, sourceIds, tags],
    queryFn: () => api.search({
      q: query, top_k: 10,
      source_ids: sourceIds ? sourceIds.split(",").map((s) => parseInt(s.trim(), 10)).filter((n) => !isNaN(n)) : undefined,
      tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : undefined,
    }),
    enabled: query.length > 0,
  });

  const handleSearch = () => { const q = inputValue.trim(); if (q) setQuery(q); };

  return (
    <div className="flex flex-col h-full bg-background">
      <header className="shrink-0 px-5 py-3 border-b border-border bg-card/50 backdrop-blur-sm">
        <span className="text-xs font-medium text-muted-foreground tracking-tight">Semantic Search</span>
      </header>

      <div className="shrink-0 px-5 pt-4 pb-3 border-b border-border bg-card/30">
        <div className="flex items-center gap-2">
          <div className={`relative flex-1 flex items-center rounded-xl border bg-card transition-all duration-200 ${
            focused ? "border-amber-400/70 ring-2 ring-amber-400/15" : "border-border"
          }`}>
            <MagnifyingGlass size={15} className="absolute left-3.5 text-muted-foreground" />
            <input value={inputValue} onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
              placeholder="Search your knowledge base…" autoFocus
              className="w-full h-10 bg-transparent pl-9 pr-4 text-sm text-foreground placeholder:text-muted-foreground outline-none"
              aria-label="Search query"
            />
          </div>
          <motion.button whileTap={{ scale: 0.95 }} onClick={handleSearch}
            disabled={!inputValue.trim() || isFetching}
            className="flex items-center gap-1.5 h-10 px-4 rounded-xl bg-amber-500 hover:bg-amber-600 dark:hover:bg-amber-400 text-white text-sm font-semibold transition-colors disabled:opacity-40 shadow-sm shadow-amber-200/50 dark:shadow-none"
          >
            Search <ArrowRight size={14} weight="bold" />
          </motion.button>
        </div>
        <div className="flex gap-4 mt-2.5">
          {[["Source IDs", sourceIds, setSourceIds, "1,2,3"], ["Tags", tags, setTags, "ml,notes"]].map(([label, val, setter, ph]) => (
            <label key={label as string} className="flex items-center gap-2 text-xs text-muted-foreground">
              {label as string}:
              <input value={val as string} onChange={(e) => (setter as (v: string) => void)(e.target.value)}
                placeholder={ph as string}
                className="h-6 w-20 rounded-lg border border-border bg-transparent px-2 text-xs text-foreground outline-none focus:border-amber-400 transition-colors"
              />
            </label>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-border">
        {isFetching && [0,1,2].map((i) => (
          <div key={i} className="px-5 py-4 flex items-start gap-3.5">
            <div className="h-6 w-6 rounded-md skeleton-shimmer shrink-0" />
            <div className="flex-1 space-y-2 pt-1">
              <div className="h-3.5 rounded skeleton-shimmer w-2/5" />
              <div className="h-3 rounded skeleton-shimmer w-full" />
              <div className="h-3 rounded skeleton-shimmer w-3/4" />
            </div>
          </div>
        ))}

        {error && !isFetching && (
          <div className="px-5 py-10 text-center">
            <p className="text-sm text-destructive">{error instanceof Error ? error.message : "Search failed"}</p>
          </div>
        )}

        {data && !isFetching && (
          <AnimatePresence>
            {data.hits.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-muted">
                  <BookOpen size={20} className="text-muted-foreground" />
                </div>
                <div className="text-center">
                  <p className="text-sm font-semibold text-foreground">No results for &ldquo;{data.query}&rdquo;</p>
                  <p className="text-xs text-muted-foreground mt-0.5">Try a different query or ingest more notes.</p>
                </div>
              </div>
            ) : (
              <>
                <div className="px-5 py-2 bg-muted/30">
                  <span className="text-[11px] text-muted-foreground">
                    {data.hits.length} result{data.hits.length !== 1 ? "s" : ""} for{" "}
                    <span className="text-foreground font-medium">&ldquo;{data.query}&rdquo;</span>
                  </span>
                </div>
                {data.hits.map((hit, i) => <SearchResultRow key={hit.chunk_id} hit={hit} index={i} />)}
              </>
            )}
          </AnimatePresence>
        )}

        {!query && !isFetching && !data && (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-50 dark:bg-amber-950/40 ring-1 ring-amber-100 dark:ring-amber-900/60">
              <MagnifyingGlass size={20} weight="bold" className="text-amber-400" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-foreground">Search your notes</p>
              <p className="text-xs text-muted-foreground mt-0.5">Hybrid vector + full-text across ingested documents.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center"><span className="text-xs text-muted-foreground">Loading…</span></div>}>
      <SearchPageContent />
    </Suspense>
  );
}
