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

  // Load existing conversation history when a cid is in the URL
  const { data: history } = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => api.getConversation(conversationId!),
    enabled: conversationId != null && messages.length === 0,
  });

  useEffect(() => {
    if (history && messages.length === 0) {
      const loaded: ChatMessage[] = history.messages.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
      }));
      setMessages(loaded);
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
      setMessages((prev) => [...prev, { role: "user", content: message }]);
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer, response: data },
      ]);
      if (!conversationId) {
        setConversationId(data.conversation_id);
        router.replace(`/chat?cid=${data.conversation_id}`, { scroll: false });
      }
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (err) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
        },
      ]);
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-full">
      <header className="px-4 py-2 border-b flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">Chat</span>
      </header>

      <MessageList messages={messages} />
      <div ref={bottomRef} />

      <SourceFilter
        sourceIds={sourceIds}
        tags={tags}
        onChangeSourceIds={setSourceIds}
        onChangeTags={setTags}
      />
      <ChatComposer
        onSend={(msg, privateMode) => sendMessage({ message: msg, privateMode })}
        disabled={isPending}
      />
    </div>
  );
}

export default function ChatPageWrapper() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">Loading…</div>}>
      <ChatPage />
    </Suspense>
  );
}
