"use client";

import { motion } from "framer-motion";
import { X, BookOpenText } from "@phosphor-icons/react";
import type { Citation } from "@/lib/api/types";

interface Props {
  citation: Citation;
  onClose: () => void;
}

export function CitationCard({ citation, onClose }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 4, scale: 0.97 }}
      transition={{ type: "spring", stiffness: 420, damping: 26 }}
      className="absolute z-50 w-76 bg-white border border-zinc-200/80 rounded-xl shadow-lg shadow-zinc-900/8 overflow-hidden"
      style={{ width: 300 }}
    >
      {/* Amber accent bar */}
      <div className="h-0.5 w-full bg-gradient-to-r from-amber-400 to-amber-300" />

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start gap-3 mb-3">
          <div className="mt-0.5 shrink-0 flex h-6 w-6 items-center justify-center rounded-md bg-amber-50 text-amber-600">
            <BookOpenText size={13} weight="bold" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-zinc-900 leading-snug truncate">
              {citation.document_title}
            </p>
            <p className="text-[10px] text-zinc-400 mt-0.5">{citation.source_name}</p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 mt-0.5 p-0.5 rounded hover:bg-zinc-100 text-zinc-400 hover:text-zinc-600 transition-colors"
            aria-label="Close"
          >
            <X size={12} />
          </button>
        </div>

        {/* Snippet */}
        {citation.snippet && (
          <p className="text-[11px] text-zinc-500 leading-relaxed line-clamp-5 mb-3 pl-9">
            &ldquo;{citation.snippet}&rdquo;
          </p>
        )}

        {/* Meta row */}
        <div className="flex items-center gap-2 pl-9">
          <span className="inline-flex items-center rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 ring-1 ring-amber-200/60">
            [{citation.marker}]
          </span>
          <span className="inline-flex items-center rounded-md bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500">
            {citation.method}
          </span>
          {citation.score != null && (
            <span className="font-mono text-[10px] text-zinc-400">
              {citation.score.toFixed(4)}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
