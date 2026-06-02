"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, MagnifyingGlass, ChatCircle, Sun, Moon } from "@phosphor-icons/react";
import { api } from "@/lib/api/client";
import { Suspense } from "react";

function SidebarContent() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeCid = searchParams.get("cid");
  const { resolvedTheme, setTheme } = useTheme();

  const { data } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.listConversations(),
    refetchInterval: 15_000,
  });

  const isDark = resolvedTheme === "dark";

  return (
    <aside className="w-52 shrink-0 flex flex-col h-full overflow-hidden bg-[#111111] dark:bg-[#0a0a0b] border-r border-white/[0.06]">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-white/[0.06] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-zinc-100 text-sm font-semibold tracking-tight">Second Brain</span>
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" />
        </div>
        {/* Theme toggle */}
        <motion.button
          whileTap={{ scale: 0.88 }}
          onClick={() => setTheme(isDark ? "light" : "dark")}
          className="flex h-6 w-6 items-center justify-center rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-white/8 transition-all"
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? <Sun size={13} weight="bold" /> : <Moon size={13} weight="bold" />}
        </motion.button>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 px-2 pt-2 pb-1">
        {[
          { href: "/chat", label: "New Chat", icon: <Plus size={13} weight="bold" />, exact: true },
          { href: "/search", label: "Search", icon: <MagnifyingGlass size={13} weight="bold" />, exact: false },
        ].map(({ href, label, icon, exact }) => {
          const active = exact ? pathname === href && !activeCid : pathname.startsWith(href);
          return (
            <Link key={href} href={href}
              className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs transition-all duration-150 ${
                active ? "bg-white/10 text-white" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"
              }`}
            >
              {icon}{label}
            </Link>
          );
        })}
      </nav>

      <div className="mx-3 border-t border-white/[0.06] my-1" />

      {/* History */}
      <div className="flex-1 overflow-y-auto px-2 pb-3 min-h-0">
        {data && data.conversations.length > 0 && (
          <>
            <p className="px-2.5 py-1.5 text-[10px] font-semibold text-zinc-700 uppercase tracking-widest">
              Recent
            </p>
            <AnimatePresence initial={false}>
              {data.conversations.map((c, i) => (
                <motion.div key={c.id}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.035, type: "spring", stiffness: 340, damping: 28 }}
                >
                  <Link href={`/chat?cid=${c.id}`}
                    className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs truncate border-l-2 transition-all duration-150 ${
                      activeCid === String(c.id)
                        ? "border-amber-500 bg-white/8 text-white"
                        : "border-transparent text-zinc-600 hover:text-zinc-300 hover:bg-white/5"
                    }`}
                    title={c.title ?? `Conversation ${c.id}`}
                  >
                    <ChatCircle size={11} className="shrink-0 opacity-50" />
                    <span className="truncate">{c.title ?? `Chat ${c.id}`}</span>
                  </Link>
                </motion.div>
              ))}
            </AnimatePresence>
          </>
        )}
        {data?.conversations.length === 0 && (
          <p className="px-3 text-[11px] text-zinc-700 leading-relaxed">
            Conversations appear here after your first message.
          </p>
        )}
      </div>
    </aside>
  );
}

export function ConversationSidebar() {
  return (
    <Suspense fallback={<aside className="w-52 shrink-0 bg-[#111111] dark:bg-[#0a0a0b] border-r border-white/[0.06]" />}>
      <SidebarContent />
    </Suspense>
  );
}
