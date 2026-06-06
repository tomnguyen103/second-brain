"use client";

import { useState, useRef } from "react";
import { AnimatePresence } from "framer-motion";
import type { Citation } from "@/lib/api/types";
import { CitationCard } from "./CitationCard";

interface Props { answer: string; citations: Citation[]; }

export function AnswerWithCitations({ answer, citations }: Props) {
  const [active, setActive] = useState<Citation | null>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const ref = useRef<HTMLDivElement>(null);

  const map = new Map(citations.map((c) => [c.marker, c]));
  const parts = answer.split(/(\[\d+\])/g);

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>, citation: Citation) => {
    const r = e.currentTarget.getBoundingClientRect();
    const cr = ref.current?.getBoundingClientRect();
    if (!cr) return;
    const maxLeft = Math.max(0, cr.width - 320);
    setPos({ top: r.bottom - cr.top + 8, left: Math.max(0, Math.min(r.left - cr.left, maxLeft)) });
    setActive((p) => p?.marker === citation.marker ? null : citation);
  };

  return (
    <div ref={ref} className="relative">
      <p className="whitespace-pre-wrap text-sm leading-[1.75] text-foreground">
        {parts.map((part, i) => {
          const m = part.match(/^\[(\d+)\]$/);
          if (!m) return <span key={i}>{part}</span>;
          const c = map.get(Number(m[1]));
          if (!c) return <span key={i} className="text-muted-foreground">{part}</span>;
          return (
            <sup key={i}>
              <button
                onClick={(e) => handleClick(e, c)}
                className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-md bg-primary/10 px-1 font-mono text-[10px] font-semibold text-primary ring-1 ring-primary/20 transition-colors hover:bg-primary/20 focus:outline-none focus:ring-2 focus:ring-primary/30"
                aria-label={`Source ${m[1]}: ${c.document_title}`}
              >
                {m[1]}
              </button>
            </sup>
          );
        })}
      </p>
      <AnimatePresence>
        {active && (
          <div style={{ position: "absolute", top: pos.top, left: pos.left }}>
            <CitationCard citation={active} onClose={() => setActive(null)} />
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
