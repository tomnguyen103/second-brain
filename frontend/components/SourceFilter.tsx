"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";

interface Props {
  sourceIds: number[];
  tags: string[];
  onChangeSourceIds: (ids: number[]) => void;
  onChangeTags: (tags: string[]) => void;
}

export function SourceFilter({
  sourceIds,
  tags,
  onChangeSourceIds,
  onChangeTags,
}: Props) {
  const [sourceInput, setSourceInput] = useState("");
  const [tagInput, setTagInput] = useState("");

  const addSourceId = () => {
    const id = parseInt(sourceInput.trim(), 10);
    if (!isNaN(id) && !sourceIds.includes(id)) {
      onChangeSourceIds([...sourceIds, id]);
    }
    setSourceInput("");
  };

  const addTag = () => {
    const t = tagInput.trim();
    if (t && !tags.includes(t)) {
      onChangeTags([...tags, t]);
    }
    setTagInput("");
  };

  if (sourceIds.length === 0 && tags.length === 0) {
    return (
      <div className="flex flex-wrap gap-2 items-center px-4 pb-2 text-xs text-muted-foreground">
        <span>Filter by</span>
        <input
          value={sourceInput}
          onChange={(e) => setSourceInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addSourceId()}
          placeholder="source ID…"
          className="h-5 w-20 rounded border border-input bg-background px-1.5 text-xs outline-none focus:ring-1 focus:ring-ring"
        />
        <input
          value={tagInput}
          onChange={(e) => setTagInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addTag()}
          placeholder="tag…"
          className="h-5 w-20 rounded border border-input bg-background px-1.5 text-xs outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2 items-center px-4 pb-2">
      {sourceIds.map((id) => (
        <Badge key={id} variant="secondary" className="gap-1 text-xs">
          source:{id}
          <button onClick={() => onChangeSourceIds(sourceIds.filter((s) => s !== id))}>
            <X size={10} />
          </button>
        </Badge>
      ))}
      {tags.map((t) => (
        <Badge key={t} variant="secondary" className="gap-1 text-xs">
          #{t}
          <button onClick={() => onChangeTags(tags.filter((x) => x !== t))}>
            <X size={10} />
          </button>
        </Badge>
      ))}
      <input
        value={sourceInput}
        onChange={(e) => setSourceInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && addSourceId()}
        placeholder="+ source ID"
        className="h-5 w-20 rounded border border-input bg-background px-1.5 text-xs outline-none focus:ring-1 focus:ring-ring"
      />
      <input
        value={tagInput}
        onChange={(e) => setTagInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && addTag()}
        placeholder="+ tag"
        className="h-5 w-20 rounded border border-input bg-background px-1.5 text-xs outline-none focus:ring-1 focus:ring-ring"
      />
    </div>
  );
}
