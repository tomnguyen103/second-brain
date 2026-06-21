"use client";

import type { MouseEvent, ReactNode, RefObject } from "react";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useInfiniteQuery } from "@tanstack/react-query";
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
import type { ConversationSummary } from "@/lib/api/types";
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

const HISTORY_PAGE_SIZE = 12;

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

  const isDark = mounted ? resolvedTheme !== "light" : true;
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
    <div className="flex h-full flex-col overflow-hidden bg-card">
      <div className="border-b border-grid px-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <Link
            href="/chat"
            onClick={navigate}
            className="flex min-w-0 items-center gap-2 rounded-lg p-1 transition-colors hover:bg-surface-hover"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground ring-1 ring-primary/30">
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
              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25"
              aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
            >
              {isDark ? <Sun size={15} weight="bold" /> : <Moon size={15} weight="bold" />}
            </motion.button>
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25 md:hidden"
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
          className="mt-3 flex h-9 items-center justify-center gap-1.5 rounded-lg bg-primary text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25"
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
                      "flex h-8 items-center gap-2 rounded-lg px-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25",
                      active
                        ? "bg-primary/10 text-foreground ring-1 ring-primary/25"
                        : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
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

      <div className="mx-3 mb-3 mt-auto rounded-lg border border-border bg-background p-2">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <Key size={14} weight="bold" className={hasApiToken ? "text-primary" : "text-muted-foreground"} />
            <span className="truncate text-xs font-semibold text-foreground">API access</span>
          </div>
          <span className={cn(
            "rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1",
            hasApiToken
              ? "bg-live/10 text-live ring-live/30"
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
            className="h-8 min-w-0 flex-1 rounded-lg border border-input bg-background px-2.5 text-xs text-foreground outline-none transition-colors placeholder:text-muted-foreground hover:bg-surface-hover/60 focus:border-primary focus:ring-3 focus:ring-primary/25"
          />
          <button
            type="submit"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25"
            aria-label="Save API token"
            title="Save API token"
          >
            <Check size={13} weight="bold" />
          </button>
          <button
            type="button"
            onClick={clearApiToken}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25"
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

  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteQuery({
    queryKey: ["conversations"],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api.listConversations({ limit: HISTORY_PAGE_SIZE, offset: pageParam }),
    getNextPageParam: (lastPage) => {
      const nextOffset = lastPage.offset + lastPage.conversations.length;
      return nextOffset < lastPage.total ? nextOffset : undefined;
    },
    refetchInterval: 15_000,
  });
  const conversations = useMemo(
    () => data?.pages.flatMap((page) => page.conversations) ?? [],
    [data?.pages],
  );
  const latestPage = data?.pages[data.pages.length - 1];
  const total = latestPage?.total ?? 0;

  const historyItems = useMemo(() => {
    const groups = new Map<string, {
      conversation: ConversationSummary;
      duplicateCount: number;
    }>();

    for (const conversation of conversations) {
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

    return Array.from(groups.values());
  }, [conversations, activeConversationId]);

  return (
    <aside className="hidden h-full w-80 shrink-0 p-4 xl:block" aria-label="Recent conversations">
      <section className="max-h-[50vh] overflow-hidden rounded-lg border border-border bg-card">
        <div className="flex items-center justify-between gap-3 border-b border-grid px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold leading-5 text-foreground">Recent conversations</h2>
            <p className="mt-0.5 text-xs leading-5 text-muted-foreground">Conversation history</p>
          </div>
          {latestPage && (
            <span className="rounded-md bg-muted px-2 py-1 font-mono text-[10px] font-semibold text-muted-foreground ring-1 ring-border">
              {conversations.length}/{total}
            </span>
          )}
        </div>

        <div className="max-h-[calc(50vh-4rem)] overflow-y-auto p-2">
          {isLoading && (
            <p className="rounded-lg bg-background px-3 py-3 text-xs leading-5 text-muted-foreground ring-1 ring-border">
              Loading conversation history...
            </p>
          )}
          {error && !isLoading && (
            <p className="rounded-lg bg-destructive/10 px-3 py-3 text-xs leading-5 text-destructive ring-1 ring-destructive/25">
              Conversation history failed.
            </p>
          )}
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
                      "mb-1 flex min-w-0 items-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25",
                      activeCid === String(conversation.id)
                        ? "bg-primary/10 text-foreground ring-1 ring-primary/25"
                        : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
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
          {hasNextPage && (
            <button
              type="button"
              onClick={() => {
                void fetchNextPage();
              }}
              disabled={isFetchingNextPage}
              className="mt-2 flex h-8 w-full items-center justify-center rounded-lg border border-border bg-background px-3 text-xs font-semibold text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isFetchingNextPage ? "Loading..." : "Load more"}
            </button>
          )}
          {!isLoading && total === 0 && (
            <p className="rounded-lg bg-background px-3 py-3 text-xs leading-5 text-muted-foreground ring-1 ring-border">
              Conversations appear here after your first cited answer.
            </p>
          )}
        </div>
      </section>
    </aside>
  );
}

function MobileTopBar({
  onOpen,
  mobileOpen,
  menuButtonRef,
}: {
  onOpen: () => void;
  mobileOpen: boolean;
  menuButtonRef: RefObject<HTMLButtonElement | null>;
}) {
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
    <div className="fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between border-b border-grid bg-background px-3 md:hidden">
      <button
        ref={menuButtonRef}
        type="button"
        onClick={onOpen}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25"
        aria-label="Open navigation"
        aria-controls="mobile-navigation"
        aria-expanded={mobileOpen}
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
        className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/25"
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
  returnFocusRef,
}: {
  mobileOpen: boolean;
  onCloseMobile: () => void;
  returnFocusRef: RefObject<HTMLButtonElement | null>;
}) {
  const panelRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!mobileOpen) return;

    const previousOverflow = document.body.style.overflow;
    const returnFocusElement = returnFocusRef.current;
    document.body.style.overflow = "hidden";

    const focusableSelector = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(",");
    const focusFirstControl = () => {
      const panel = panelRef.current;
      const firstControl = panel?.querySelector<HTMLElement>(focusableSelector);
      (firstControl ?? panel)?.focus();
    };
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseMobile();
        return;
      }
      if (event.key !== "Tab") return;

      const panel = panelRef.current;
      if (!panel) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(focusableSelector))
        .filter((element) => !element.hasAttribute("disabled"));
      if (focusable.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    const timer = window.setTimeout(focusFirstControl, 0);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      returnFocusElement?.focus();
    };
  }, [mobileOpen, onCloseMobile, returnFocusRef]);

  return (
    <>
      <aside className="hidden h-full w-64 shrink-0 border-r border-grid bg-card md:block">
        <SidebarContent />
      </aside>

      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.button
              key="mobile-nav-backdrop"
              type="button"
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onCloseMobile}
              aria-label="Close navigation"
            />
            <motion.aside
              id="mobile-navigation"
              ref={panelRef}
              key="mobile-nav"
              role="dialog"
              aria-modal="true"
              aria-label="Primary navigation"
              tabIndex={-1}
              className="fixed inset-y-0 left-0 z-50 w-[min(18rem,calc(100vw-1rem))] border-r border-grid bg-card shadow-2xl shadow-black/40 md:hidden"
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
  const menuButtonRef = useRef<HTMLButtonElement | null>(null);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <>
      <MobileTopBar
        onOpen={() => setMobileOpen(true)}
        mobileOpen={mobileOpen}
        menuButtonRef={menuButtonRef}
      />
      <Suspense fallback={<aside className="hidden h-full w-64 shrink-0 border-r border-grid bg-card md:block" />}>
        <SidebarFrame
          mobileOpen={mobileOpen}
          onCloseMobile={closeMobile}
          returnFocusRef={menuButtonRef}
        />
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
