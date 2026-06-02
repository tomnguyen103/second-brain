"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";
import type { SearchHit } from "@/lib/api/types";

function SearchResult({ hit }: { hit: SearchHit }) {
  return (
    <Card className="hover:shadow-sm transition-shadow">
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-semibold">{hit.document_title}</CardTitle>
        <div className="flex flex-wrap gap-1.5 mt-1">
          <Badge variant="secondary" className="text-xs">{hit.source_name}</Badge>
          <Badge variant="outline" className="text-xs">{hit.method}</Badge>
          <span className="text-xs text-muted-foreground">
            score: {hit.score.toFixed(4)}
          </span>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-4">
          {hit.snippet}
        </p>
      </CardContent>
    </Card>
  );
}

export default function SearchPage() {
  const [inputValue, setInputValue] = useState("");
  const [query, setQuery] = useState("");
  const [sourceIds, setSourceIds] = useState<string>("");
  const [tags, setTags] = useState<string>("");

  const { data, isFetching, error } = useQuery({
    queryKey: ["search", query, sourceIds, tags],
    queryFn: () =>
      api.search({
        q: query,
        top_k: 10,
        source_ids: sourceIds
          ? sourceIds
              .split(",")
              .map((s) => parseInt(s.trim(), 10))
              .filter((n) => !isNaN(n))
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
    <div className="flex flex-col h-full">
      <header className="px-4 py-2 border-b">
        <span className="text-sm font-medium text-muted-foreground">Semantic Search</span>
      </header>

      <div className="px-4 pt-4 pb-3 border-b space-y-2">
        <div className="flex gap-2">
          <input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Search your knowledge base…"
            className="flex-1 h-9 rounded-md border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            aria-label="Search query"
          />
          <Button size="sm" onClick={handleSearch} disabled={!inputValue.trim() || isFetching}>
            <Search size={14} className="mr-1" />
            Search
          </Button>
        </div>
        <div className="flex gap-3 text-xs text-muted-foreground">
          <label className="flex items-center gap-1">
            Source IDs:
            <input
              value={sourceIds}
              onChange={(e) => setSourceIds(e.target.value)}
              placeholder="1,2,3"
              className="h-5 w-20 rounded border border-input bg-background px-1.5 outline-none focus:ring-1 focus:ring-ring"
            />
          </label>
          <label className="flex items-center gap-1">
            Tags:
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="ml,notes"
              className="h-5 w-24 rounded border border-input bg-background px-1.5 outline-none focus:ring-1 focus:ring-ring"
            />
          </label>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {isFetching && (
          <p className="text-sm text-muted-foreground animate-pulse">Searching…</p>
        )}
        {error && (
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : "Search failed"}
          </p>
        )}
        {data && !isFetching && (
          <>
            <p className="text-xs text-muted-foreground">
              {data.hits.length} result{data.hits.length !== 1 ? "s" : ""} for &ldquo;{data.query}&rdquo;
            </p>
            {data.hits.length === 0 ? (
              <p className="text-sm text-muted-foreground">No matching chunks found.</p>
            ) : (
              data.hits.map((hit) => <SearchResult key={hit.chunk_id} hit={hit} />)
            )}
          </>
        )}
        {!query && !isFetching && (
          <p className="text-sm text-muted-foreground">
            Enter a query above to search your ingested notes.
          </p>
        )}
      </div>
    </div>
  );
}
