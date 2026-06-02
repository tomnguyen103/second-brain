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
    setPos({ top: r.bottom - cr.top + 6, left: Math.min(r.left - cr.left, cr.width - 308) });
    setActive((p) => p?.marker === citation.marker ? null : citation);
  };

  return (
    <div ref={ref} className="relative">
      <p className="text-sm leading-[1.75] whitespace-pre-wrap text-foreground">
        {parts.map((part, i) => {
          const m = part.match(/^\[(\d+)\]$/);
          if (!m) return <span key={i}>{part}</span>;
          const c = map.get(Number(m[1]));
          if (!c) return <span key={i} className="text-muted-foreground">{part}</span>;
          return (
            <sup key={i}>
              <button
                onClick={(e) => handleClick(e, c)}
                className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/60 text-[10px] font-mono font-semibold transition-colors focus:outline-none focus:ring-1 focus:ring-amber-400 ring-offset-1 ring-offset-card"
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
