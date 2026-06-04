"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChartBar,
  ChatCircle,
  Database,
  FilePlus,
  Flask,
  ListChecks,
  MagnifyingGlass,
  Moon,
  NewspaperClipping,
  Plus,
  ShieldCheck,
  Sun,
} from "@phosphor-icons/react";
import { api } from "@/lib/api/client";
import { Suspense, useState, useEffect } from "react";

function SidebarContent() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeCid = searchParams.get("cid");
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const { data } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.listConversations(),
    refetchInterval: 15_000,
  });

  // Theme is unknown during SSR / first client render; reading it before mount
  // produces an icon/aria-label that differs between server and client and
  // triggers a hydration mismatch that de-opts this subtree. Gate on `mounted`.
  const isDark = mounted && resolvedTheme === "dark";

  return (
    <aside className="w-56 shrink-0 flex flex-col h-full overflow-hidden bg-card border-r border-border">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-foreground text-sm font-semibold tracking-tight">Second Brain</span>
          <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" />
        </div>
        {/* Theme toggle */}
        <motion.button
          whileTap={{ scale: 0.88 }}
          onClick={() => setTheme(isDark ? "light" : "dark")}
          className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
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
          { href: "/ingest", label: "Ingest", icon: <FilePlus size={13} weight="bold" />, exact: false },
          { href: "/briefing", label: "Briefing", icon: <NewspaperClipping size={13} weight="bold" />, exact: false },
          { href: "/feedback", label: "Feedback", icon: <ChartBar size={13} weight="bold" />, exact: false },
          { href: "/tasks", label: "Tasks", icon: <ListChecks size={13} weight="bold" />, exact: false },
          { href: "/research", label: "Research", icon: <Flask size={13} weight="bold" />, exact: false },
          { href: "/sources", label: "Sources", icon: <Database size={13} weight="bold" />, exact: false },
          { href: "/admin", label: "Admin", icon: <ShieldCheck size={13} weight="bold" />, exact: false },
        ].map(({ href, label, icon, exact }) => {
          const active = exact ? pathname === href && !activeCid : pathname.startsWith(href);
          return (
            <Link key={href} href={href}
              className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs transition-all duration-150 ${
                active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground hover:bg-accent"
              }`}
            >
              {icon}{label}
            </Link>
          );
        })}
      </nav>

      <div className="mx-3 border-t border-border my-1" />

      {/* History */}
      <div className="flex-1 overflow-y-auto px-2 pb-3 min-h-0">
        {data && data.conversations.length > 0 && (
          <>
            <p className="px-2.5 py-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
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
                        ? "border-primary bg-accent text-accent-foreground"
                        : "border-transparent text-muted-foreground hover:text-foreground hover:bg-accent"
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
          <p className="px-3 text-[11px] text-muted-foreground leading-relaxed">
            Conversations appear here after your first message.
          </p>
        )}
      </div>
    </aside>
  );
}

export function ConversationSidebar() {
  return (
    <Suspense fallback={<aside className="w-56 shrink-0 bg-card border-r border-border" />}>
      <SidebarContent />
    </Suspense>
  );
}
