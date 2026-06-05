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
  isStreaming?: boolean;
}

function MessageSkeleton() {
  return (
    <div className="flex items-start gap-3 max-w-[72%]">
      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-50 dark:bg-amber-950/40 ring-1 ring-amber-100 dark:ring-amber-900/60 shrink-0 mt-0.5">
        <Sparkle size={13} weight="fill" className="text-amber-400 animate-pulse" />
      </div>
      <div className="space-y-2 flex-1 pt-1">
        <div className="h-3.5 rounded-lg skeleton-shimmer w-3/4" />
        <div className="h-3.5 rounded-lg skeleton-shimmer w-full" />
        <div className="h-3.5 rounded-lg skeleton-shimmer w-1/2" />
      </div>
    </div>
  );
}

const FeedbackButtons = ({ messageId }: { messageId: number }) => {
  const { mutate, isPending, isSuccess } = useMutation({
    mutationFn: ({ rating }: { rating: 1 | -1 }) =>
      api.submitFeedback({ message_id: messageId, rating }),
  });
  if (isSuccess) return <span className="text-[10px] text-zinc-400">Saved</span>;
  return (
    <div className="flex gap-0.5">
      {([1, -1] as const).map((r) => (
        <button key={r} disabled={isPending}
          onClick={() => mutate({ rating: r })}
          className="p-1 rounded-md transition-colors text-zinc-300 dark:text-zinc-600 hover:text-zinc-700 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-40 active:scale-95"
          aria-label={r === 1 ? "Helpful" : "Not helpful"}
        >
          {r === 1 ? <ThumbsUp size={12} /> : <ThumbsDown size={12} />}
        </button>
      ))}
    </div>
  );
};

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 select-none px-8">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 dark:bg-amber-950/40 ring-1 ring-amber-100 dark:ring-amber-900/60">
        <Sparkle size={22} weight="fill" className="text-amber-400" />
      </div>
      <div className="text-center space-y-1">
        <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 tracking-tight">
          Ask your knowledge base
        </p>
        <p className="text-xs text-zinc-400 dark:text-zinc-500 max-w-[26ch] leading-relaxed">
          Type a question to get cited answers from your notes.
        </p>
      </div>
    </div>
  );
}

interface Props { messages: ChatMessage[]; isLoading?: boolean; }

export function MessageList({ messages, isLoading }: Props) {
  if (messages.length === 0 && !isLoading) return <EmptyState />;

  return (
    <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">
      <AnimatePresence initial={false}>
        {messages.map((msg, i) => (
          <motion.div key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="flex items-start gap-2.5 max-w-[80%]">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-50 dark:bg-amber-950/40 ring-1 ring-amber-100 dark:ring-amber-900/60 shrink-0 mt-1">
                  <Sparkle size={13} weight="fill" className="text-amber-500 dark:text-amber-400" />
                </div>
                <div className="bg-white dark:bg-zinc-900 border border-zinc-200/70 dark:border-zinc-800 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm shadow-zinc-900/4 dark:shadow-none">
                  <AnswerWithCitations answer={msg.content} citations={msg.response?.citations ?? []} />
                  {msg.isStreaming && (
                    <span className="mt-2 inline-flex h-1.5 w-1.5 rounded-full bg-amber-400 align-middle animate-pulse" />
                  )}
                  {msg.response && (
                    <div className="flex flex-wrap items-center gap-2 mt-2.5 pt-2 border-t border-zinc-100 dark:border-zinc-800">
                      {msg.response.model && (
                        <span className="font-mono text-[10px] text-zinc-400 dark:text-zinc-600">
                          {msg.response.model}
                        </span>
                      )}
                      <span className="font-mono text-[10px] text-zinc-300 dark:text-zinc-700">
                        {msg.response.latency_ms}ms
                      </span>
                      {msg.response.citations.length > 0 && (
                        <span className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 rounded-md px-1.5 py-0.5 font-medium">
                          {msg.response.citations.length} source{msg.response.citations.length > 1 ? "s" : ""}
                        </span>
                      )}
                      {msg.response.retrieval.agentic && (
                        <span className="text-[10px] text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950/40 rounded-md px-1.5 py-0.5 font-medium">
                          agentic: {msg.response.retrieval.agentic.subqueries.length} searches / {msg.response.retrieval.agentic.selected_chunks} chunks
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
            {msg.role === "user" && (
              <div className="max-w-[68%] bg-zinc-900 dark:bg-zinc-800 text-zinc-50 rounded-2xl rounded-tr-sm px-4 py-3">
                <p className="text-sm leading-[1.7]">{msg.content}</p>
              </div>
            )}
          </motion.div>
        ))}

        {isLoading && (
          <motion.div key="skeleton"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 26 }}
            className="flex justify-start"
          >
            <div className="w-64"><MessageSkeleton /></div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
