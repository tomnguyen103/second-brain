"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, MagnifyingGlass, ChatCircle } from "@phosphor-icons/react";
import { api } from "@/lib/api/client";
import { Suspense } from "react";

const SIDEBAR_ITEM = {
  initial: { opacity: 0, x: -6 },
  animate: { opacity: 1, x: 0 },
};

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
    <aside className="w-52 shrink-0 flex flex-col h-full overflow-hidden bg-[#111111] border-r border-white/[0.06]">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-white/[0.06]">
        <span className="text-zinc-100 text-sm font-semibold tracking-tight">
          Second Brain
        </span>
        <div className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block ml-1.5 mb-0.5" />
      </div>

      {/* Primary nav */}
      <nav className="flex flex-col gap-0.5 px-2 pt-3 pb-2">
        <Link
          href="/chat"
          className={`group flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs transition-all duration-150 ${
            pathname === "/chat" && !activeCid
              ? "bg-white/10 text-white"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-white/5"
          }`}
        >
          <Plus size={14} weight="bold" />
          New Chat
        </Link>
        <Link
          href="/search"
          className={`group flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs transition-all duration-150 ${
            pathname === "/search"
              ? "bg-white/10 text-white"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-white/5"
          }`}
        >
          <MagnifyingGlass size={14} weight="bold" />
          Search
        </Link>
      </nav>

      {/* Divider */}
      <div className="mx-4 border-t border-white/[0.06] mb-2" />

      {/* History */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 min-h-0">
        {data && data.conversations.length > 0 && (
          <>
            <p className="px-2.5 pb-2 text-[10px] font-medium text-zinc-600 uppercase tracking-widest">
              History
            </p>
            <AnimatePresence initial={false}>
              {data.conversations.map((c, i) => (
                <motion.div
                  key={c.id}
                  variants={SIDEBAR_ITEM}
                  initial="initial"
                  animate="animate"
                  transition={{
                    delay: i * 0.04,
                    type: "spring",
                    stiffness: 320,
                    damping: 28,
                  }}
                >
                  <Link
                    href={`/chat?cid=${c.id}`}
                    className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs truncate transition-all duration-150 border-l-2 ${
                      activeCid === String(c.id)
                        ? "border-amber-500 bg-white/8 text-white"
                        : "border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-white/5"
                    }`}
                    title={c.title ?? `Conversation ${c.id}`}
                  >
                    <ChatCircle size={12} className="shrink-0 opacity-60" />
                    <span className="truncate">
                      {c.title ?? `Chat ${c.id}`}
                    </span>
                  </Link>
                </motion.div>
              ))}
            </AnimatePresence>
          </>
        )}

        {data && data.conversations.length === 0 && (
          <p className="px-2.5 text-[11px] text-zinc-700 leading-relaxed">
            Conversations appear here after your first message.
          </p>
        )}
      </div>
    </aside>
  );
}

export function ConversationSidebar() {
  return (
    <Suspense
      fallback={
        <aside className="w-52 shrink-0 bg-[#111111] border-r border-white/[0.06]" />
      }
    >
      <SidebarContent />
    </Suspense>
  );
}
