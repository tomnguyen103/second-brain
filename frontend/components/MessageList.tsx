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
    <div className="flex max-w-2xl items-start gap-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/25">
        <Sparkle size={13} weight="fill" className="animate-pulse text-primary" />
      </div>
      <div className="flex-1 space-y-2 pt-1">
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
  if (isSuccess) return <span className="text-[10px] text-muted-foreground">Saved</span>;
  return (
    <div className="flex gap-0.5">
      {([1, -1] as const).map((r) => (
        <button key={r} type="button" disabled={isPending}
          onClick={() => mutate({ rating: r })}
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground disabled:opacity-40 active:scale-95"
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
    <div className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg rounded-lg border border-border bg-card p-6 text-center">
        <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/25">
          <Sparkle size={21} weight="fill" className="text-primary" />
        </div>
        <p className="mt-4 text-base font-semibold text-foreground">
          Ask your local knowledge
        </p>
        <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-muted-foreground">
          Get a cited answer from your notes, captures, PDFs, and research without leaving the local workspace.
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-1.5 text-[11px] font-semibold text-muted-foreground">
          <span className="rounded-md bg-muted px-2 py-1 ring-1 ring-border">citations</span>
          <span className="rounded-md bg-muted px-2 py-1 ring-1 ring-border">source filters</span>
          <span className="rounded-md bg-muted px-2 py-1 ring-1 ring-border">private mode</span>
        </div>
      </div>
    </div>
  );
}

interface Props { messages: ChatMessage[]; isLoading?: boolean; }

export function MessageList({ messages, isLoading }: Props) {
  if (messages.length === 0 && !isLoading) return <EmptyState />;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-5 md:px-6">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
        <AnimatePresence initial={false}>
        {messages.map((msg, i) => (
          <motion.div key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="flex max-w-[min(44rem,100%)] items-start gap-2.5">
                <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/25">
                  <Sparkle size={13} weight="fill" className="text-primary" />
                </div>
                <article className="rounded-lg rounded-tl-sm border border-border bg-card px-4 py-3">
                  <AnswerWithCitations answer={msg.content} citations={msg.response?.citations ?? []} />
                  {msg.isStreaming && (
                    <span className="mt-2 inline-flex h-1.5 w-1.5 animate-pulse rounded-full bg-primary align-middle" />
                  )}
                  {msg.response && (
                    <div className="mt-2.5 flex flex-wrap items-center gap-2 border-t border-grid pt-2">
                      {msg.response.model && (
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {msg.response.model}
                        </span>
                      )}
                      <span className="font-mono text-[10px] text-muted-foreground/75">
                        {msg.response.latency_ms}ms
                      </span>
                      {msg.response.citations.length > 0 && (
                        <span className="rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary ring-1 ring-primary/25">
                          {msg.response.citations.length} source{msg.response.citations.length > 1 ? "s" : ""}
                        </span>
                      )}
                      {msg.response.retrieval.agentic && (
                        <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground ring-1 ring-border">
                          agentic: {msg.response.retrieval.agentic.subqueries.length} searches / {msg.response.retrieval.agentic.selected_chunks} chunks
                        </span>
                      )}
                      <div className="ml-auto">
                        <FeedbackButtons messageId={msg.response.message_id} />
                      </div>
                    </div>
                  )}
                </article>
              </div>
            )}
            {msg.role === "user" && (
              <div className="max-w-[min(38rem,88%)] rounded-lg rounded-tr-sm bg-primary px-4 py-3 text-primary-foreground shadow-sm shadow-primary/20">
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
            <div className="w-full max-w-2xl"><MessageSkeleton /></div>
          </motion.div>
        )}
        </AnimatePresence>
      </div>
    </div>
  );
}
