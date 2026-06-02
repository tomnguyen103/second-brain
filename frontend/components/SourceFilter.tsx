"use client";

import { useState } from "react";
import { X, Tag, IdentificationCard } from "@phosphor-icons/react";
import { motion, AnimatePresence } from "framer-motion";

interface Props {
  sourceIds: number[];
  tags: string[];
  onChangeSourceIds: (ids: number[]) => void;
  onChangeTags: (tags: string[]) => void;
}

export function SourceFilter({ sourceIds, tags, onChangeSourceIds, onChangeTags }: Props) {
  const [sourceInput, setSourceInput] = useState("");
  const [tagInput, setTagInput] = useState("");

  const addSourceId = () => {
    const id = parseInt(sourceInput.trim(), 10);
    if (!isNaN(id) && !sourceIds.includes(id)) onChangeSourceIds([...sourceIds, id]);
    setSourceInput("");
  };

  const addTag = () => {
    const t = tagInput.trim();
    if (t && !tags.includes(t)) onChangeTags([...tags, t]);
    setTagInput("");
  };

  const hasFilters = sourceIds.length > 0 || tags.length > 0;

  return (
    <div className="flex flex-wrap items-center gap-1.5 px-6 pb-3">
      {/* Active filter chips */}
      <AnimatePresence>
        {sourceIds.map((id) => (
          <motion.span
            key={`src-${id}`}
            initial={{ opacity: 0, scale: 0.88 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.88 }}
            transition={{ type: "spring", stiffness: 400, damping: 22 }}
            className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200/70 px-2 py-0.5 text-[11px] font-medium text-amber-700"
          >
            <IdentificationCard size={11} />
            {id}
            <button
              onClick={() => onChangeSourceIds(sourceIds.filter((s) => s !== id))}
              className="hover:text-amber-900 transition-colors ml-0.5"
            >
              <X size={9} weight="bold" />
            </button>
          </motion.span>
        ))}
        {tags.map((t) => (
          <motion.span
            key={`tag-${t}`}
            initial={{ opacity: 0, scale: 0.88 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.88 }}
            transition={{ type: "spring", stiffness: 400, damping: 22 }}
            className="inline-flex items-center gap-1 rounded-full bg-zinc-100 border border-zinc-200 px-2 py-0.5 text-[11px] font-medium text-zinc-600"
          >
            <Tag size={11} />
            {t}
            <button
              onClick={() => onChangeTags(tags.filter((x) => x !== t))}
              className="hover:text-zinc-900 transition-colors ml-0.5"
            >
              <X size={9} weight="bold" />
            </button>
          </motion.span>
        ))}
      </AnimatePresence>

      {/* Inputs */}
      <input
        value={sourceInput}
        onChange={(e) => setSourceInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && addSourceId()}
        placeholder={hasFilters ? "+ source" : "Filter by source ID…"}
        className="h-6 w-24 rounded-full border border-zinc-200 bg-transparent px-2.5 text-[11px] text-zinc-600 placeholder:text-zinc-400 outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400/40 transition-all"
      />
      <input
        value={tagInput}
        onChange={(e) => setTagInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && addTag()}
        placeholder={hasFilters ? "+ tag" : "or tag…"}
        className="h-6 w-20 rounded-full border border-zinc-200 bg-transparent px-2.5 text-[11px] text-zinc-600 placeholder:text-zinc-400 outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400/40 transition-all"
      />
    </div>
  );
}
