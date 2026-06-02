"use client";

import type { Citation } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  citation: Citation;
  onClose: () => void;
}

export function CitationCard({ citation, onClose }: Props) {
  return (
    <Card className="absolute z-50 w-80 shadow-lg border bg-popover text-popover-foreground">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-semibold leading-tight">
            [{citation.marker}] {citation.document_title}
          </CardTitle>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground shrink-0 text-xs"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="flex items-center gap-2 mt-1">
          <Badge variant="secondary" className="text-xs">
            {citation.source_name}
          </Badge>
          <Badge variant="outline" className="text-xs">
            {citation.method}
          </Badge>
          {citation.score != null && (
            <span className="text-xs text-muted-foreground">
              score: {citation.score.toFixed(4)}
            </span>
          )}
        </div>
      </CardHeader>
      {citation.snippet && (
        <CardContent className="pt-0">
          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-6">
            {citation.snippet}
          </p>
        </CardContent>
      )}
    </Card>
  );
}
