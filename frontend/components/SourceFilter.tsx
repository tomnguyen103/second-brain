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
  const [srcIn, setSrcIn] = useState("");
  const [tagIn, setTagIn] = useState("");

  const addSrc = () => {
    const id = parseInt(srcIn.trim(), 10);
    if (!isNaN(id) && !sourceIds.includes(id)) onChangeSourceIds([...sourceIds, id]);
    setSrcIn("");
  };
  const addTag = () => {
    const t = tagIn.trim();
    if (t && !tags.includes(t)) onChangeTags([...tags, t]);
    setTagIn("");
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5 px-5 pb-2.5">
      <AnimatePresence>
        {sourceIds.map((id) => (
          <motion.span key={`s${id}`}
            initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }} transition={{ type: "spring", stiffness: 400, damping: 22 }}
            className="inline-flex items-center gap-1 rounded-full bg-amber-50 dark:bg-amber-950/40 border border-amber-200/70 dark:border-amber-800/60 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-400"
          >
            <IdentificationCard size={10} />{id}
            <button onClick={() => onChangeSourceIds(sourceIds.filter((s) => s !== id))} className="ml-0.5 hover:opacity-70 transition-opacity"><X size={9} weight="bold" /></button>
          </motion.span>
        ))}
        {tags.map((t) => (
          <motion.span key={`t${t}`}
            initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }} transition={{ type: "spring", stiffness: 400, damping: 22 }}
            className="inline-flex items-center gap-1 rounded-full bg-muted border border-border px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
          >
            <Tag size={10} />{t}
            <button onClick={() => onChangeTags(tags.filter((x) => x !== t))} className="ml-0.5 hover:opacity-70 transition-opacity"><X size={9} weight="bold" /></button>
          </motion.span>
        ))}
      </AnimatePresence>
      <input value={srcIn} onChange={(e) => setSrcIn(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addSrc()}
        placeholder={sourceIds.length || tags.length ? "+ source" : "Filter source…"}
        className="h-6 w-24 rounded-full border border-border bg-transparent px-2.5 text-[11px] text-foreground placeholder:text-muted-foreground outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400/30 transition-all" />
      <input value={tagIn} onChange={(e) => setTagIn(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addTag()}
        placeholder="+ tag"
        className="h-6 w-20 rounded-full border border-border bg-transparent px-2.5 text-[11px] text-foreground placeholder:text-muted-foreground outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400/30 transition-all" />
    </div>
  );
}
