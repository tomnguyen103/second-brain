"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { queryClient } from "@/lib/query-client";
import type { ChatMessage } from "@/components/MessageList";
import { MessageList } from "@/components/MessageList";
import { ChatComposer } from "@/components/ChatComposer";
import { SourceFilter } from "@/components/SourceFilter";

function ChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const cidParam = searchParams.get("cid");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(
    cidParam ? parseInt(cidParam, 10) : null
  );
  const [sourceIds, setSourceIds] = useState<number[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: history } = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => api.getConversation(conversationId!),
    enabled: conversationId != null && messages.length === 0,
  });

  useEffect(() => {
    if (history && messages.length === 0) {
      setMessages(history.messages.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
      })));
    }
  }, [history]);

  const { mutate: sendMessage, isPending } = useMutation({
    mutationFn: (payload: { message: string; privateMode: boolean }) =>
      api.chat({
        message: payload.message,
        conversation_id: conversationId,
        filters: {
          source_ids: sourceIds.length ? sourceIds : undefined,
          tags: tags.length ? tags : undefined,
        },
        options: { private_mode: payload.privateMode, include_chunks: true },
      }),
    onMutate: ({ message }) => {
      setMessages((p) => [...p, { role: "user", content: message }]);
    },
    onSuccess: (data) => {
      setMessages((p) => [...p, { role: "assistant", content: data.answer, response: data }]);
      if (!conversationId) {
        setConversationId(data.conversation_id);
        router.replace(`/chat?cid=${data.conversation_id}`, { scroll: false });
      }
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (err) => {
      setMessages((p) => [...p, {
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
      }]);
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isPending]);

  return (
    <div className="flex flex-col h-full bg-background">
      <header className="shrink-0 px-5 py-3 border-b border-border bg-card/50 backdrop-blur-sm flex items-center">
        <span className="text-xs font-medium text-muted-foreground tracking-tight">
          {conversationId ? `Conversation #${conversationId}` : "New conversation"}
        </span>
      </header>
      <MessageList messages={messages} isLoading={isPending} />
      <div ref={bottomRef} />
      <SourceFilter sourceIds={sourceIds} tags={tags} onChangeSourceIds={setSourceIds} onChangeTags={setTags} />
      <ChatComposer onSend={(msg, pm) => sendMessage({ message: msg, privateMode: pm })} disabled={isPending} />
    </div>
  );
}

export default function ChatPageWrapper() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center"><span className="text-xs text-muted-foreground">Loading…</span></div>}>
      <ChatPage />
    </Suspense>
  );
}
