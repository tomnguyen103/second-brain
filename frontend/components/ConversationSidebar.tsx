"use client";

import type { MouseEvent, ReactNode } from "react";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { AnimatePresence, motion } from "framer-motion";
import {
  BookmarkSimple,
  ChartBar,
  ChatCircle,
  Check,
  Database,
  Flask,
  Gauge,
  Key,
  List,
  ListChecks,
  MagnifyingGlass,
  Moon,
  NewspaperClipping,
  Plus,
  ShieldCheck,
  Sun,
  X,
} from "@phosphor-icons/react";

import { api, getStoredApiToken, setStoredApiToken } from "@/lib/api/client";
import { queryClient } from "@/lib/query-client";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  icon: ReactNode;
  activePrefixes?: string[];
};

const navSections: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "Workspace",
    items: [
      { href: "/chat", label: "Chat", icon: <ChatCircle size={15} weight="bold" /> },
      { href: "/search", label: "Search", icon: <MagnifyingGlass size={15} weight="bold" /> },
      { href: "/capture", label: "Capture", icon: <BookmarkSimple size={15} weight="bold" /> },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        href: "/sources",
        label: "Sources",
        icon: <Database size={15} weight="bold" />,
        activePrefixes: ["/sources", "/ingest"],
      },
      { href: "/status", label: "Status", icon: <Gauge size={15} weight="bold" /> },
      { href: "/feedback", label: "Feedback", icon: <ChartBar size={15} weight="bold" /> },
      { href: "/admin", label: "Admin", icon: <ShieldCheck size={15} weight="bold" /> },
    ],
  },
  {
    label: "Flows",
    items: [
      { href: "/briefing", label: "Briefing", icon: <NewspaperClipping size={15} weight="bold" /> },
      { href: "/tasks", label: "Tasks", icon: <ListChecks size={15} weight="bold" /> },
      { href: "/research", label: "Research", icon: <Flask size={15} weight="bold" /> },
    ],
  },
];

function SidebarContent({ onNavigate, onClose }: { onNavigate?: () => void; onClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [apiTokenInput, setApiTokenInput] = useState("");
  const [hasApiToken, setHasApiToken] = useState(false);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const syncToken = () => {
      const token = getStoredApiToken();
      setApiTokenInput(token);
      setHasApiToken(Boolean(token));
    };
    syncToken();
    window.addEventListener("second-brain-api-token-changed", syncToken);
    return () => window.removeEventListener("second-brain-api-token-changed", syncToken);
  }, []);

  const isDark = mounted && resolvedTheme === "dark";
  const saveApiToken = () => {
    setStoredApiToken(apiTokenInput);
    setHasApiToken(Boolean(apiTokenInput.trim()));
    queryClient.invalidateQueries();
  };
  const clearApiToken = () => {
    setApiTokenInput("");
    setStoredApiToken("");
    setHasApiToken(false);
    queryClient.invalidateQueries();
  };
  const navigate = () => {
    onNavigate?.();
  };
  const startNewChat = (event?: MouseEvent<HTMLElement>) => {
    event?.preventDefault();
    window.dispatchEvent(new Event("second-brain-new-chat"));
    if (pathname !== "/chat") {
      router.push("/chat");
    }
    onNavigate?.();
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-card/95">
      <div className="border-b border-border/80 px-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <Link
            href="/chat"
            onClick={navigate}
            className="flex min-w-0 items-center gap-2 rounded-lg p-1 transition-colors hover:bg-muted"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
              <Database size={16} weight="bold" />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold leading-4 text-foreground">
                Second Brain
              </span>
              <span className="block truncate text-[11px] leading-4 text-muted-foreground">
                Local knowledge workspace
              </span>
            </span>
          </Link>
          <div className="flex shrink-0 items-center gap-1">
            <motion.button
              whileTap={{ scale: 0.9 }}
              onClick={() => setTheme(isDark ? "light" : "dark")}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/15"
              aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
            >
              {isDark ? <Sun size={15} weight="bold" /> : <Moon size={15} weight="bold" />}
            </motion.button>
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/15 md:hidden"
                aria-label="Close navigation"
              >
                <X size={15} weight="bold" />
              </button>
            )}
          </div>
        </div>
        <a
          href="/chat"
          onClick={startNewChat}
          className="mt-3 flex h-9 items-center justify-center gap-1.5 rounded-lg bg-foreground text-sm font-semibold text-background transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/20"
        >
          <Plus size={14} weight="bold" />
          New chat
        </a>
      </div>

      <nav className="flex flex-col gap-3 px-3 py-3" aria-label="Primary navigation">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/75">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = item.href === "/chat"
                  ? pathname === "/chat"
                  : (item.activePrefixes ?? [item.href]).some((prefix) =>
                      pathname.startsWith(prefix),
                    );
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={navigate}
                    className={cn(
                      "flex h-8 items-center gap-2 rounded-lg px-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/15",
                      active
                        ? "bg-primary/10 text-foreground ring-1 ring-primary/20"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <span className={cn("text-muted-foreground", active && "text-primary")}>{item.icon}</span>
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="mx-3 mt-auto mb-3 rounded-lg border border-border/80 bg-background/70 p-2">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <Key size={14} weight="bold" className={hasApiToken ? "text-primary" : "text-muted-foreground"} />
            <span className="truncate text-xs font-semibold text-foreground">API access</span>
          </div>
          <span className={cn(
            "rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1",
            hasApiToken
              ? "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:ring-emerald-900/60"
              : "bg-muted text-muted-foreground ring-border",
          )}>
            {hasApiToken ? "saved" : "local"}
          </span>
        </div>
        <form
          className="flex items-center gap-1.5"
          onSubmit={(event) => {
            event.preventDefault();
            saveApiToken();
          }}
        >
          <label className="sr-only" htmlFor="sidebar-api-token">API bearer token</label>
          <input
            id="sidebar-api-token"
            type="password"
            value={apiTokenInput}
            onChange={(event) => setApiTokenInput(event.target.value)}
            placeholder="Token"
            autoComplete="off"
            className="h-8 min-w-0 flex-1 rounded-lg border border-input bg-background px-2.5 text-xs text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-3 focus:ring-primary/15"
          />
          <button
            type="submit"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/15"
            aria-label="Save API token"
            title="Save API token"
          >
            <Check size={13} weight="bold" />
          </button>
          <button
            type="button"
            onClick={clearApiToken}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/15"
            aria-label="Clear API token"
            title="Clear API token"
          >
            <X size={13} weight="bold" />
          </button>
        </form>
      </div>
    </div>
  );
}

function ConversationHistoryContent() {
  const searchParams = useSearchParams();
  const activeCid = searchParams.get("cid");
  const activeConversationId = activeCid ? Number.parseInt(activeCid, 10) : null;

  const { data } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.listConversations(),
    refetchInterval: 15_000,
  });

  const historyItems = useMemo(() => {
    const groups = new Map<string, {
      conversation: NonNullable<typeof data>["conversations"][number];
      duplicateCount: number;
    }>();

    for (const conversation of data?.conversations ?? []) {
      const title = conversation.title?.trim();
      const key = title ? title.toLowerCase() : `id:${conversation.id}`;
      const existing = groups.get(key);
      if (!existing) {
        groups.set(key, { conversation, duplicateCount: 1 });
        continue;
      }
      existing.duplicateCount += 1;
      if (conversation.id === activeConversationId) {
        existing.conversation = conversation;
      }
    }

    return Array.from(groups.values()).slice(0, 12);
  }, [data?.conversations, activeConversationId]);

  return (
    <aside className="hidden h-full w-80 shrink-0 p-4 xl:block" aria-label="Recent conversations">
      <section className="max-h-[50vh] overflow-hidden rounded-lg bg-card/95 ring-1 ring-border/90 shadow-sm shadow-zinc-950/[0.025]">
        <div className="flex items-center justify-between gap-3 border-b border-border/80 px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold leading-5 text-foreground">Recent conversations</h2>
            <p className="mt-0.5 text-xs leading-5 text-muted-foreground">Conversation history</p>
          </div>
          {data?.total != null && (
            <span className="rounded-md bg-muted px-2 py-1 font-mono text-[10px] font-semibold text-muted-foreground ring-1 ring-border">
              {data.total}
            </span>
          )}
        </div>

        <div className="max-h-[calc(50vh-4rem)] overflow-y-auto p-2">
          {historyItems.length > 0 && (
            <AnimatePresence initial={false}>
              {historyItems.map(({ conversation, duplicateCount }, index) => (
                <motion.div
                  key={conversation.id}
                  initial={{ opacity: 0, x: 4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.02, type: "spring", stiffness: 340, damping: 28 }}
                >
                  <Link
                    href={`/chat?cid=${conversation.id}`}
                    className={cn(
                      "mb-1 flex min-w-0 items-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/15",
                      activeCid === String(conversation.id)
                        ? "bg-primary/10 text-foreground ring-1 ring-primary/20"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                    title={conversation.title ?? `Conversation ${conversation.id}`}
                  >
                    <ChatCircle size={13} className="shrink-0 opacity-70" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {conversation.title ?? `Chat ${conversation.id}`}
                      </span>
                      <span className="block truncate font-mono text-[10px] text-muted-foreground/75">
                        #{conversation.id} / {conversation.message_count} msg
                      </span>
                    </span>
                    {duplicateCount > 1 && (
                      <span
                        className="shrink-0 rounded-md border border-border px-1 text-[9px] leading-4 text-muted-foreground"
                        title={`${duplicateCount} conversations with this title`}
                      >
                        x{duplicateCount}
                      </span>
                    )}
                  </Link>
                </motion.div>
              ))}
            </AnimatePresence>
          )}
          {data?.conversations.length === 0 && (
            <p className="rounded-lg bg-muted/40 px-3 py-3 text-xs leading-5 text-muted-foreground">
              Conversations appear here after your first cited answer.
            </p>
          )}
        </div>
      </section>
    </aside>
  );
}

function MobileTopBar({ onOpen }: { onOpen: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const startNewChat = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    window.dispatchEvent(new Event("second-brain-new-chat"));
    if (pathname !== "/chat") {
      router.push("/chat");
    }
  };

  return (
    <div className="fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between border-b border-border/80 bg-background/95 px-3 backdrop-blur md:hidden">
      <button
        type="button"
        onClick={onOpen}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/15"
        aria-label="Open navigation"
      >
        <List size={18} weight="bold" />
      </button>
      <Link href="/chat" className="min-w-0 text-center">
        <span className="block text-sm font-semibold leading-4 text-foreground">Second Brain</span>
        <span className="block text-[11px] leading-4 text-muted-foreground">Local-first workspace</span>
      </Link>
      <Link
        href="/chat"
        onClick={startNewChat}
        className="flex h-9 w-9 items-center justify-center rounded-lg bg-foreground text-background transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/20"
        aria-label="New chat"
      >
        <Plus size={15} weight="bold" />
      </Link>
    </div>
  );
}

function SidebarFrame({
  mobileOpen,
  onCloseMobile,
}: {
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  return (
    <>
      <aside className="hidden h-full w-64 shrink-0 border-r border-border/80 bg-card/95 md:block">
        <SidebarContent />
      </aside>

      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.button
              key="mobile-nav-backdrop"
              type="button"
              className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-sm md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onCloseMobile}
              aria-label="Close navigation"
            />
            <motion.aside
              key="mobile-nav"
              className="fixed inset-y-0 left-0 z-50 w-[min(18rem,calc(100vw-1rem))] border-r border-border/80 bg-card shadow-2xl shadow-zinc-950/20 md:hidden"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 340, damping: 34 }}
            >
              <SidebarContent onNavigate={onCloseMobile} onClose={onCloseMobile} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

export function ConversationSidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      <MobileTopBar onOpen={() => setMobileOpen(true)} />
      <Suspense fallback={<aside className="hidden h-full w-64 shrink-0 border-r border-border/80 bg-card md:block" />}>
        <SidebarFrame mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />
      </Suspense>
    </>
  );
}

export function ConversationHistoryRail() {
  return (
    <Suspense fallback={<aside className="hidden h-full w-80 shrink-0 p-4 xl:block" />}>
      <ConversationHistoryContent />
    </Suspense>
  );
}
