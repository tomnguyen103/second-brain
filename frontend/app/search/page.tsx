"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, BookOpen, MagnifyingGlass } from "@phosphor-icons/react";

import {
  AppButton,
  AppPage,
  EmptyState,
  Field,
  InlineError,
  LoadingRows,
  Panel,
  PanelHeader,
  StatusPill,
  TextInput,
} from "@/components/AppPage";
import { api } from "@/lib/api/client";
import type { SearchHit } from "@/lib/api/types";

function parseSourceIds(value: string): number[] | undefined {
  const ids = value
    .split(",")
    .map((sourceId) => parseInt(sourceId.trim(), 10))
    .filter((sourceId) => !Number.isNaN(sourceId));
  return ids.length ? ids : undefined;
}

function parseTags(value: string): string[] | undefined {
  const tags = value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  return tags.length ? tags : undefined;
}

function SearchResultRow({ hit, index }: { hit: SearchHit; index: number }) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03, type: "spring", stiffness: 300, damping: 26 }}
      className="group grid gap-3 px-4 py-4 transition-colors hover:bg-muted/45 sm:grid-cols-[2rem_minmax(0,1fr)]"
    >
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 font-mono text-[11px] font-bold text-primary ring-1 ring-primary/20">
        {index + 1}
      </div>
      <div className="min-w-0">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold leading-5 text-foreground">{hit.document_title}</h2>
            <p className="mt-1 truncate text-xs text-muted-foreground">{hit.source_name}</p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1.5">
            <StatusPill>{hit.method}</StatusPill>
            <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground ring-1 ring-border">
              {hit.score.toFixed(4)}
            </span>
          </div>
        </div>
        <p className="mt-2 line-clamp-3 text-sm leading-6 text-muted-foreground">{hit.snippet}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground ring-1 ring-border">
            chunk #{hit.chunk_id}
          </span>
          {hit.vector_score != null && (
            <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground ring-1 ring-border">
              vec {hit.vector_score.toFixed(3)}
            </span>
          )}
          {hit.fulltext_score != null && (
            <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground ring-1 ring-border">
              fts {hit.fulltext_score.toFixed(3)}
            </span>
          )}
        </div>
      </div>
    </motion.article>
  );
}

function SearchPageContent() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";
  const [inputValue, setInputValue] = useState(initialQ);
  const [query, setQuery] = useState(initialQ);
  const [sourceIds, setSourceIds] = useState("");
  const [tags, setTags] = useState("");
  const [focused, setFocused] = useState(false);

  const { data, isFetching, error } = useQuery({
    queryKey: ["search", query, sourceIds, tags],
    queryFn: () => api.search({
      q: query,
      top_k: 10,
      source_ids: parseSourceIds(sourceIds),
      tags: parseTags(tags),
    }),
    enabled: query.length > 0,
  });

  const handleSearch = () => {
    const nextQuery = inputValue.trim();
    if (nextQuery) setQuery(nextQuery);
  };

  return (
    <AppPage
      eyebrow="Search"
      title="Knowledge search"
      description="Run hybrid vector and full-text search across indexed notes, captures, PDFs, and research."
      actions={
        data && !isFetching ? (
          <StatusPill tone={data.hits.length ? "success" : "neutral"}>
            {data.hits.length} result{data.hits.length === 1 ? "" : "s"}
          </StatusPill>
        ) : undefined
      }
    >
      <Panel>
        <form
          className="grid gap-3 p-4"
          onSubmit={(event) => {
            event.preventDefault();
            handleSearch();
          }}
        >
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <Field label="Search query">
              <div className={`relative rounded-lg transition-all ${focused ? "ring-3 ring-primary/15" : ""}`}>
                <MagnifyingGlass size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <TextInput
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  onFocus={() => setFocused(true)}
                  onBlur={() => setFocused(false)}
                  placeholder="Search your knowledge base..."
                  autoFocus
                  className="pl-9"
                />
              </div>
            </Field>
            <AppButton type="submit" disabled={!inputValue.trim() || isFetching} className="w-full lg:w-auto">
              Search <ArrowRight size={14} weight="bold" />
            </AppButton>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Source IDs" hint="Comma-separated IDs, optional.">
              <TextInput
                value={sourceIds}
                onChange={(event) => setSourceIds(event.target.value)}
                placeholder="1, 2, 3"
                inputMode="numeric"
              />
            </Field>
            <Field label="Tags" hint="Comma-separated tags, optional.">
              <TextInput
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="ml, notes"
              />
            </Field>
          </div>
        </form>
      </Panel>

      <Panel className="overflow-hidden">
        <PanelHeader
          title={query ? `Results for "${query}"` : "Results"}
          description={query ? "Ranked by fused semantic and full-text signals." : "Enter a query to search your indexed workspace."}
        />
        {isFetching && <LoadingRows rows={5} />}

        {error && !isFetching && (
          <div className="p-4">
            <InlineError message={error instanceof Error ? error.message : "Search failed"} />
          </div>
        )}

        {data && !isFetching && (
          <AnimatePresence>
            {data.hits.length === 0 ? (
              <EmptyState
                icon={<BookOpen size={20} />}
                title={`No results for "${data.query}"`}
                body="Try broader wording, remove filters, or ingest more source material."
              />
            ) : (
              <div className="divide-y divide-border/80">
                {data.hits.map((hit, index) => (
                  <SearchResultRow key={hit.chunk_id} hit={hit} index={index} />
                ))}
              </div>
            )}
          </AnimatePresence>
        )}

        {!query && !isFetching && !data && (
          <EmptyState
            icon={<MagnifyingGlass size={20} weight="bold" />}
            title="Search your workspace"
            body="Use source IDs or tags when you want a narrow review set."
          />
        )}
      </Panel>
    </AppPage>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="flex flex-1 items-center justify-center"><span className="text-xs text-muted-foreground">Loading...</span></div>}>
      <SearchPageContent />
    </Suspense>
  );
}
