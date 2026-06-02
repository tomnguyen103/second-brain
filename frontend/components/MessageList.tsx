"use client";

import { motion, AnimatePresence } from "framer-motion";
import { ThumbsUp, ThumbsDown, Sparkle } from "@phosphor-icons/react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { ChatResponse } from "@/lib/api/types";
import { AnswerWithCitations } from "./AnswerWithCitations";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
}

/* ── Skeleton placeholder while request is in-flight ── */
function MessageSkeleton() {
  return (
    <div className="flex items-start gap-3 max-w-[75%]">
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-zinc-100 shrink-0 mt-0.5">
        <Sparkle size={12} weight="fill" className="text-amber-400" />
      </div>
      <div className="space-y-2 flex-1">
        <div className="h-3.5 rounded-md skeleton-shimmer w-3/4" />
        <div className="h-3.5 rounded-md skeleton-shimmer w-1/2" />
        <div className="h-3.5 rounded-md skeleton-shimmer w-5/6" />
      </div>
    </div>
  );
}

/* ── Feedback thumbs — isolated to avoid re-render of parent ── */
const FeedbackButtons = ({ messageId }: { messageId: number }) => {
  const { mutate, isPending, isSuccess } = useMutation({
    mutationFn: ({ rating }: { rating: 1 | -1 }) =>
      api.submitFeedback({ message_id: messageId, rating }),
  });

  if (isSuccess) {
    return <span className="text-[10px] text-zinc-400">Saved</span>;
  }

  return (
    <div className="flex gap-1">
      <button
        disabled={isPending}
        onClick={() => mutate({ rating: 1 })}
        className="p-1 rounded transition-colors text-zinc-300 hover:text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 active:scale-95"
        aria-label="Helpful"
      >
        <ThumbsUp size={12} />
      </button>
      <button
        disabled={isPending}
        onClick={() => mutate({ rating: -1 })}
        className="p-1 rounded transition-colors text-zinc-300 hover:text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 active:scale-95"
        aria-label="Not helpful"
      >
        <ThumbsDown size={12} />
      </button>
    </div>
  );
};

/* ── Empty state ── */
function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 select-none">
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-50 ring-1 ring-amber-100">
        <Sparkle size={20} weight="fill" className="text-amber-400" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-zinc-700">Ask your knowledge base</p>
        <p className="text-xs text-zinc-400 mt-0.5 max-w-[22ch]">
          Type a question and get cited answers from your notes.
        </p>
      </div>
    </div>
  );
}

/* ── Main component ── */
interface Props {
  messages: ChatMessage[];
  isLoading?: boolean;
}

export function MessageList({ messages, isLoading }: Props) {
  if (messages.length === 0 && !isLoading) {
    return <EmptyState />;
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
      <AnimatePresence initial={false}>
        {messages.map((msg, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 26 }}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {/* Assistant label */}
            {msg.role === "assistant" && (
              <div className="flex items-start gap-2.5 max-w-[82%]">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-50 ring-1 ring-amber-100 shrink-0 mt-1">
                  <Sparkle size={12} weight="fill" className="text-amber-500" />
                </div>
                <div className="bg-white border border-zinc-200/80 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm shadow-zinc-900/5">
                  <AnswerWithCitations
                    answer={msg.content}
                    citations={msg.response?.citations ?? []}
                  />
                  {msg.response && (
                    <div className="mt-2.5 flex flex-wrap items-center gap-2 border-t border-zinc-100 pt-2">
                      {msg.response.model && (
                        <span className="font-mono text-[10px] text-zinc-400">
                          {msg.response.model}
                        </span>
                      )}
                      <span className="font-mono text-[10px] text-zinc-300">
                        {msg.response.latency_ms}ms
                      </span>
                      {msg.response.citations.length > 0 && (
                        <span className="text-[10px] text-amber-600 bg-amber-50 rounded px-1.5 py-0.5 font-medium">
                          {msg.response.citations.length} source
                          {msg.response.citations.length > 1 ? "s" : ""}
                        </span>
                      )}
                      <div className="ml-auto">
                        <FeedbackButtons messageId={msg.response.message_id} />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* User bubble */}
            {msg.role === "user" && (
              <div className="max-w-[70%] bg-zinc-900 text-zinc-50 rounded-2xl rounded-tr-sm px-4 py-3">
                <p className="text-sm leading-[1.7]">{msg.content}</p>
              </div>
            )}
          </motion.div>
        ))}

        {/* Loading skeleton */}
        {isLoading && (
          <motion.div
            key="skeleton"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 26 }}
            className="flex justify-start"
          >
            <div className="max-w-[75%] w-64">
              <MessageSkeleton />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
