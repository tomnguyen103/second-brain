"use client";

import { useState, useRef, useEffect, useMemo, Suspense, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, isChatStreamUnavailableError } from "@/lib/api/client";
import { queryClient } from "@/lib/query-client";
import type { ChatMessage } from "@/components/MessageList";
import type { ChatRequest, ChatResponse } from "@/lib/api/types";
import { MessageList } from "@/components/MessageList";
import { ChatComposer } from "@/components/ChatComposer";
import { SourceFilter } from "@/components/SourceFilter";

const STREAM_STATUS_LABELS: Record<string, string> = {
  context_ready: "Context ready",
  generating_answer: "Generating answer",
  validating_citations: "Validating citations",
};

function ChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const cidParam = searchParams.get("cid");
  const routeConversationId = useMemo(() => {
    if (!cidParam) return null;
    const parsed = Number.parseInt(cidParam, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }, [cidParam]);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(routeConversationId);
  const [isSending, setIsSending] = useState(false);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [sourceIds, setSourceIds] = useState<number[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const agenticAvailable = process.env.NEXT_PUBLIC_AGENTIC_RAG_ENABLED === "true";
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const routeConversationIdRef = useRef(routeConversationId);
  const preserveMessagesForRouteIdRef = useRef<number | null>(null);

  const resetChatState = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    preserveMessagesForRouteIdRef.current = null;
    setIsSending(false);
    setStreamStatus(null);
    setMessages([]);
    setConversationId(null);
  }, []);

  const startNewChat = useCallback(() => {
    resetChatState();
    router.replace("/chat", { scroll: false });
  }, [resetChatState, router]);

  useEffect(() => {
    window.addEventListener("second-brain-new-chat", startNewChat);
    return () => window.removeEventListener("second-brain-new-chat", startNewChat);
  }, [startNewChat]);

  useEffect(() => {
    if (routeConversationIdRef.current === routeConversationId) return;
    routeConversationIdRef.current = routeConversationId;

    const shouldPreserveMessages =
      routeConversationId != null && preserveMessagesForRouteIdRef.current === routeConversationId;
    preserveMessagesForRouteIdRef.current = null;

    if (!shouldPreserveMessages) {
      resetChatState();
    }
    setConversationId(routeConversationId);
  }, [routeConversationId, resetChatState]);

  const { data: history } = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => api.getConversation(conversationId!),
    enabled: conversationId != null && messages.length === 0,
  });

  const historyMessages = useMemo<ChatMessage[]>(() => {
    if (!history || history.id !== conversationId) return [];
    return history.messages.map((m) => {
      if (m.role === "assistant") {
        // Rehydrate the live-chat shape so replayed history gets clickable [n]
        // citations, the source count, and working feedback thumbs.
        return {
          role: "assistant" as const,
          content: m.content,
          response: {
            conversation_id: history.id,
            message_id: m.id,
            answer: m.content,
            citations: m.citations,
            usage: { prompt_tokens: null, completion_tokens: null, total_tokens: null },
            model: m.model,
            latency_ms: m.latency_ms ?? 0,
            retrieval: {
              method: "",
              candidates_vector: 0,
              candidates_fulltext: 0,
              fused_returned: m.citations.length,
            },
          },
        };
      }
      return { role: "user" as const, content: m.content };
    });
  }, [history, conversationId]);

  const displayMessages = messages.length > 0 ? messages : historyMessages;
  const hasStreamingMessage = displayMessages.some((m) => m.isStreaming);

  const finishAssistant = (data: ChatResponse, requestConversationId: number | null) => {
    setMessages((prev) => {
      const idx = prev.findLastIndex((m) => m.role === "assistant" && m.isStreaming);
      if (idx === -1) {
        return [...prev, { role: "assistant", content: data.answer, response: data }];
      }
      const next = [...prev];
      next[idx] = { role: "assistant", content: data.answer, response: data };
      return next;
    });
    if (!requestConversationId) {
      preserveMessagesForRouteIdRef.current = data.conversation_id;
      setConversationId(data.conversation_id);
      router.replace(`/chat?cid=${data.conversation_id}`, { scroll: false });
    }
    setStreamStatus(null);
    queryClient.invalidateQueries({ queryKey: ["conversations"] });
  };

  const showAssistantError = (err: unknown) => {
    setStreamStatus(null);
    const content = `Error: ${err instanceof Error ? err.message : "Unknown error"}`;
    setMessages((prev) => {
      const idx = prev.findLastIndex((m) => m.role === "assistant" && m.isStreaming);
      if (idx === -1) return [...prev, { role: "assistant", content }];
      const next = [...prev];
      next[idx] = { role: "assistant", content };
      return next;
    });
  };

  const sendMessage = async (payload: {
    message: string;
    privateMode: boolean;
    agenticMode: boolean;
  }) => {
    if (isSending) return;

    const req: ChatRequest = {
      message: payload.message,
      conversation_id: conversationId,
      filters: {
        source_ids: sourceIds.length ? sourceIds : undefined,
        tags: tags.length ? tags : undefined,
      },
      options: {
        private_mode: payload.privateMode,
        include_chunks: true,
        agentic: payload.agenticMode && agenticAvailable,
      },
    };

    const base = messages.length > 0 ? messages : historyMessages;
    setMessages([...base, { role: "user", content: payload.message }]);
    setIsSending(true);
    setStreamStatus(payload.agenticMode && agenticAvailable ? "Planning searches" : "Preparing context");

    const controller = new AbortController();
    abortRef.current = controller;
    const finishIfActive = (data: ChatResponse) => {
      if (controller.signal.aborted || abortRef.current !== controller) return;
      finishAssistant(data, req.conversation_id ?? null);
    };
    try {
      if (req.options?.agentic) {
        setStreamStatus("Planning searches");
        const data = await api.chat(req);
        finishIfActive(data);
        return;
      }

      await api.chatStream(req, {
        signal: controller.signal,
        onDelta: ({ text }) => {
          if (controller.signal.aborted || abortRef.current !== controller) return;
          if (!text) return;
          setMessages((prev) => {
            const idx = prev.findLastIndex((m) => m.role === "assistant" && m.isStreaming);
            if (idx === -1) {
              return [...prev, { role: "assistant", content: text, isStreaming: true }];
            }
            const next = [...prev];
            next[idx] = { ...next[idx], content: next[idx].content + text };
            return next;
          });
        },
        onStatus: ({ stage }) => {
          if (controller.signal.aborted || abortRef.current !== controller) return;
          setStreamStatus(STREAM_STATUS_LABELS[stage] ?? "Working");
        },
        onComplete: finishIfActive,
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      if (isChatStreamUnavailableError(err)) {
        try {
          const data = await api.chat(req);
          finishIfActive(data);
        } catch (fallbackErr) {
          if (controller.signal.aborted || abortRef.current !== controller) return;
          showAssistantError(fallbackErr);
        }
      } else {
        showAssistantError(err);
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        if (!controller.signal.aborted) setIsSending(false);
        setStreamStatus(null);
      }
    }
  };

  const lastMessageContent = displayMessages[displayMessages.length - 1]?.content;
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayMessages.length, lastMessageContent, isSending]);

  useEffect(() => () => abortRef.current?.abort(), []);

  return (
    <div className="flex h-full flex-col bg-background">
      <header className="shrink-0 border-b border-grid bg-background px-4 py-3 md:px-6">
        <div className="mx-auto flex w-full max-w-5xl flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Cited chat
            </p>
            <h1 className="mt-0.5 truncate text-lg font-semibold leading-6 text-foreground">
              {conversationId ? `Conversation #${conversationId}` : "New conversation"}
            </h1>
          </div>
          <div className="flex max-w-full flex-wrap items-center gap-1.5 text-[11px] font-semibold text-muted-foreground">
            <span className="rounded-md bg-muted px-2 py-1 ring-1 ring-border">
              local-first workspace
            </span>
            {agenticAvailable && (
              <span className="rounded-md bg-primary/10 px-2 py-1 text-primary ring-1 ring-primary/25">
                agentic opt-in
              </span>
            )}
          </div>
        </div>
      </header>
      <MessageList
        messages={displayMessages}
        isLoading={isSending && !hasStreamingMessage}
        statusMessage={streamStatus}
      />
      <div ref={bottomRef} />
      <footer className="shrink-0 border-t border-grid bg-background">
        <SourceFilter sourceIds={sourceIds} tags={tags} onChangeSourceIds={setSourceIds} onChangeTags={setTags} />
        <ChatComposer
          onSend={(msg, pm, am) => {
            void sendMessage({ message: msg, privateMode: pm, agenticMode: am });
          }}
          disabled={isSending}
          agenticAvailable={agenticAvailable}
        />
      </footer>
    </div>
  );
}

export default function ChatPageWrapper() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center"><span className="text-xs text-muted-foreground">Loading...</span></div>}>
      <ChatPage />
    </Suspense>
  );
}
