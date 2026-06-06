"use client";

import { motion } from "framer-motion";
import { X, BookOpenText } from "@phosphor-icons/react";
import type { Citation } from "@/lib/api/types";

interface Props { citation: Citation; onClose: () => void; }

export function CitationCard({ citation, onClose }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 4, scale: 0.97 }}
      transition={{ type: "spring", stiffness: 420, damping: 26 }}
      className="absolute z-50 w-[min(20rem,calc(100vw-2rem))] overflow-hidden rounded-lg border border-border bg-card shadow-xl shadow-zinc-900/10 dark:shadow-zinc-950/50"
    >
      <div className="h-[2px] w-full bg-primary" />
      <div className="p-4">
        <div className="flex items-start gap-3 mb-3">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
            <BookOpenText size={13} weight="bold" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-foreground leading-snug truncate">{citation.document_title}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">{citation.source_name}</p>
          </div>
          <button onClick={onClose}
            className="shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
            aria-label="Close"
          >
            <X size={12} />
          </button>
        </div>
        {citation.snippet && (
          <p className="mb-3 line-clamp-5 pl-10 text-[11px] leading-relaxed text-muted-foreground">
            &ldquo;{citation.snippet}&rdquo;
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2 pl-10">
          <span className="inline-flex items-center rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary ring-1 ring-primary/20">
            [{citation.marker}]
          </span>
          <span className="inline-flex items-center rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            {citation.method}
          </span>
          {citation.score != null && (
            <span className="font-mono text-[10px] text-muted-foreground">{citation.score.toFixed(4)}</span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
