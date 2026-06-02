"use client";

import { useState, useRef } from "react";
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

  // Split answer on [n] markers and render spans + superscript links
  const parts = answer.split(/(\[\d+\])/g);

  const handleMarkerClick = (
    e: React.MouseEvent<HTMLElement>,
    citation: Citation
  ) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();
    if (!containerRect) return;
    const top = rect.bottom - containerRect.top + 4;
    const left = Math.min(
      rect.left - containerRect.left,
      containerRect.width - 320 - 8
    );
    setCardPos({ top, left });
    setActiveCitation((prev) =>
      prev?.marker === citation.marker ? null : citation
    );
  };

  return (
    <div ref={containerRef} className="relative">
      <p className="text-sm leading-relaxed whitespace-pre-wrap">
        {parts.map((part, i) => {
          const match = part.match(/^\[(\d+)\]$/);
          if (!match) return <span key={i}>{part}</span>;
          const markerNum = Number(match[1]);
          const citation = citationMap.get(markerNum);
          if (!citation) return <span key={i}>{part}</span>;
          return (
            <sup key={i}>
              <button
                className="text-primary underline decoration-dotted hover:decoration-solid cursor-pointer text-xs font-medium px-0.5 rounded focus:outline-none focus:ring-1 focus:ring-primary"
                onClick={(e) => handleMarkerClick(e, citation)}
                aria-label={`Source ${markerNum}: ${citation.document_title}`}
              >
                [{markerNum}]
              </button>
            </sup>
          );
        })}
      </p>

      {activeCitation && (
        <div style={{ position: "absolute", top: cardPos.top, left: cardPos.left }}>
          <CitationCard
            citation={activeCitation}
            onClose={() => setActiveCitation(null)}
          />
        </div>
      )}
    </div>
  );
}
