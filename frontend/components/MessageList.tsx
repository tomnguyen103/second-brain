"use client";

import type { ChatResponse } from "@/lib/api/types";
import { AnswerWithCitations } from "./AnswerWithCitations";
import { Badge } from "@/components/ui/badge";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
}

interface Props {
  messages: ChatMessage[];
}

function FeedbackButtons({ messageId }: { messageId: number }) {
  const { mutate, isPending, isSuccess } = useMutation({
    mutationFn: ({ rating }: { rating: 1 | -1 }) =>
      api.submitFeedback({ message_id: messageId, rating }),
  });

  if (isSuccess) {
    return <span className="text-xs text-muted-foreground">Thanks!</span>;
  }

  return (
    <div className="flex gap-1 mt-2">
      <button
        disabled={isPending}
        onClick={() => mutate({ rating: 1 })}
        className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-50"
        aria-label="Thumbs up"
      >
        <ThumbsUp size={13} />
      </button>
      <button
        disabled={isPending}
        onClick={() => mutate({ rating: -1 })}
        className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-50"
        aria-label="Thumbs down"
      >
        <ThumbsDown size={13} />
      </button>
    </div>
  );
}

export function MessageList({ messages }: Props) {
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-muted-foreground text-sm">Ask anything about your notes.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {messages.map((msg, i) => (
        <div
          key={i}
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
              msg.role === "user"
                ? "bg-primary text-primary-foreground rounded-br-sm"
                : "bg-muted text-foreground rounded-bl-sm"
            }`}
          >
            {msg.role === "user" ? (
              <p className="text-sm">{msg.content}</p>
            ) : (
              <div>
                <AnswerWithCitations
                  answer={msg.content}
                  citations={msg.response?.citations ?? []}
                />
                {msg.response && (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {msg.response.model && (
                      <Badge variant="outline" className="text-xs">
                        {msg.response.model}
                      </Badge>
                    )}
                    <Badge variant="outline" className="text-xs">
                      {msg.response.latency_ms}ms
                    </Badge>
                    {msg.response.citations.length > 0 && (
                      <Badge variant="secondary" className="text-xs">
                        {msg.response.citations.length} source
                        {msg.response.citations.length > 1 ? "s" : ""}
                      </Badge>
                    )}
                    <FeedbackButtons messageId={msg.response.message_id} />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
