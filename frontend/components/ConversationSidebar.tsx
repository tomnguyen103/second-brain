"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { MessageSquare, Search, Plus } from "lucide-react";
import { Suspense } from "react";

function SidebarContent() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeCid = searchParams.get("cid");

  const { data } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.listConversations(),
    refetchInterval: 15_000,
  });

  return (
    <aside className="w-56 shrink-0 border-r bg-muted/30 flex flex-col h-full overflow-hidden">
      <div className="p-3 border-b flex items-center justify-between">
        <span className="font-semibold text-sm">Second Brain</span>
        <Link
          href="/chat"
          className="p-1 rounded hover:bg-muted text-muted-foreground"
          aria-label="New chat"
        >
          <Plus size={16} />
        </Link>
      </div>

      <nav className="flex flex-col gap-0.5 p-2">
        <Link
          href="/chat"
          className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors ${
            pathname === "/chat" && !activeCid
              ? "bg-accent text-accent-foreground"
              : "hover:bg-muted text-muted-foreground hover:text-foreground"
          }`}
        >
          <MessageSquare size={14} />
          New Chat
        </Link>
        <Link
          href="/search"
          className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors ${
            pathname === "/search"
              ? "bg-accent text-accent-foreground"
              : "hover:bg-muted text-muted-foreground hover:text-foreground"
          }`}
        >
          <Search size={14} />
          Search
        </Link>
      </nav>

      {data && data.conversations.length > 0 && (
        <>
          <div className="px-3 pt-3 pb-1">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              History
            </span>
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-2">
            {data.conversations.map((c) => (
              <Link
                key={c.id}
                href={`/chat?cid=${c.id}`}
                className={`block px-2 py-1.5 rounded text-xs truncate transition-colors ${
                  activeCid === String(c.id)
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-muted text-muted-foreground hover:text-foreground"
                }`}
                title={c.title ?? `Conversation ${c.id}`}
              >
                {c.title ?? `Chat ${c.id}`}
              </Link>
            ))}
          </div>
        </>
      )}
    </aside>
  );
}

export function ConversationSidebar() {
  return (
    <Suspense fallback={<aside className="w-56 shrink-0 border-r bg-muted/30" />}>
      <SidebarContent />
    </Suspense>
  );
}
