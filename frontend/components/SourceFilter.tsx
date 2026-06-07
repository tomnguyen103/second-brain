"use client";

import { useId, useState } from "react";
import { IdentificationCard, Tag, X } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "framer-motion";

interface Props {
  sourceIds: number[];
  tags: string[];
  onChangeSourceIds: (ids: number[]) => void;
  onChangeTags: (tags: string[]) => void;
}

export function SourceFilter({ sourceIds, tags, onChangeSourceIds, onChangeTags }: Props) {
  const sourceInputId = useId();
  const tagInputId = useId();
  const [srcIn, setSrcIn] = useState("");
  const [tagIn, setTagIn] = useState("");

  const addSrc = () => {
    const id = parseInt(srcIn.trim(), 10);
    if (!Number.isNaN(id) && !sourceIds.includes(id)) onChangeSourceIds([...sourceIds, id]);
    setSrcIn("");
  };
  const addTag = () => {
    const t = tagIn.trim();
    if (t && !tags.includes(t)) onChangeTags([...tags, t]);
    setTagIn("");
  };

  return (
    <div className="bg-background px-4 pt-3">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center gap-1.5">
        <span className="mr-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          Scope
        </span>
        <AnimatePresence>
          {sourceIds.map((id) => (
            <motion.span
              key={`s${id}`}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ type: "spring", stiffness: 400, damping: 22 }}
              className="inline-flex h-7 items-center gap-1 rounded-lg bg-primary/10 px-2 text-[11px] font-semibold text-primary ring-1 ring-primary/25"
            >
              <IdentificationCard size={11} />
              source {id}
              <button
                type="button"
                onClick={() => onChangeSourceIds(sourceIds.filter((sourceId) => sourceId !== id))}
                className="ml-0.5 rounded-sm hover:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                aria-label={`Remove source ${id}`}
              >
                <X size={10} weight="bold" />
              </button>
            </motion.span>
          ))}
          {tags.map((tag) => (
            <motion.span
              key={`t${tag}`}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ type: "spring", stiffness: 400, damping: 22 }}
              className="inline-flex h-7 items-center gap-1 rounded-lg bg-muted px-2 text-[11px] font-semibold text-muted-foreground ring-1 ring-border"
            >
              <Tag size={11} />
              {tag}
              <button
                type="button"
                onClick={() => onChangeTags(tags.filter((item) => item !== tag))}
                className="ml-0.5 rounded-sm hover:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                aria-label={`Remove tag ${tag}`}
              >
                <X size={10} weight="bold" />
              </button>
            </motion.span>
          ))}
        </AnimatePresence>

        <label htmlFor={sourceInputId} className="sr-only">Add source ID filter</label>
        <input
          id={sourceInputId}
          value={srcIn}
          onChange={(event) => setSrcIn(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addSrc();
            }
          }}
          placeholder="+ source"
          inputMode="numeric"
          className="h-7 w-24 rounded-lg border border-input bg-background px-2.5 text-[11px] text-foreground outline-none transition-colors placeholder:text-muted-foreground hover:bg-surface-hover/60 focus:border-primary focus:ring-3 focus:ring-primary/25"
        />
        <label htmlFor={tagInputId} className="sr-only">Add tag filter</label>
        <input
          id={tagInputId}
          value={tagIn}
          onChange={(event) => setTagIn(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addTag();
            }
          }}
          placeholder="+ tag"
          className="h-7 w-24 rounded-lg border border-input bg-background px-2.5 text-[11px] text-foreground outline-none transition-colors placeholder:text-muted-foreground hover:bg-surface-hover/60 focus:border-primary focus:ring-3 focus:ring-primary/25"
        />
      </div>
    </div>
  );
}
