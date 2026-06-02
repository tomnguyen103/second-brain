"use client";

import { useState, useRef } from "react";
import { AnimatePresence } from "framer-motion";
import type { Citation } from "@/lib/api/types";
import { CitationCard } from "./CitationCard";

interface Props {
  answer: string;
  citations: Citation[];
}

export function AnswerWithCitations({ answer, citations }: Props) {
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [cardPos, setCardPos] = useState({ top: 0, left: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  const citationMap = new Map(citations.map((c) => [c.marker, c]));
  const parts = answer.split(/(\[\d+\])/g);

  const handleMarkerClick = (
    e: React.MouseEvent<HTMLButtonElement>,
    citation: Citation
  ) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();
    if (!containerRect) return;
    const top = rect.bottom - containerRect.top + 6;
    const left = Math.min(
      rect.left - containerRect.left,
      containerRect.width - 308
    );
    setCardPos({ top, left });
    setActiveCitation((prev) =>
      prev?.marker === citation.marker ? null : citation
    );
  };

  return (
    <div ref={containerRef} className="relative">
      <p className="text-sm leading-[1.75] whitespace-pre-wrap text-zinc-800">
        {parts.map((part, i) => {
          const match = part.match(/^\[(\d+)\]$/);
          if (!match) return <span key={i}>{part}</span>;

          const markerNum = Number(match[1]);
          const citation = citationMap.get(markerNum);
          if (!citation) return <span key={i} className="text-zinc-400">{part}</span>;

          return (
            <sup key={i}>
              <button
                onClick={(e) => handleMarkerClick(e, citation)}
                className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded bg-amber-50 text-amber-600 hover:bg-amber-100 text-[10px] font-mono font-semibold transition-colors cursor-pointer focus:outline-none focus:ring-1 focus:ring-amber-400 ring-offset-1"
                aria-label={`Source ${markerNum}: ${citation.document_title}`}
              >
                {markerNum}
              </button>
            </sup>
          );
        })}
      </p>

      <AnimatePresence>
        {activeCitation && (
          <div
            style={{ position: "absolute", top: cardPos.top, left: cardPos.left }}
          >
            <CitationCard
              citation={activeCitation}
              onClose={() => setActiveCitation(null)}
            />
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
