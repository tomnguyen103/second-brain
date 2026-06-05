"use client";

import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Brain, PaperPlaneTilt, Lock, LockOpen } from "@phosphor-icons/react";

interface Props {
  onSend: (message: string, privateMode: boolean, agenticMode: boolean) => void;
  disabled?: boolean;
  agenticAvailable?: boolean;
}

export function ChatComposer({ onSend, disabled, agenticAvailable = false }: Props) {
  const [text, setText] = useState("");
  const [privateMode, setPrivateMode] = useState(false);
  const [agenticMode, setAgenticMode] = useState(false);
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const canSend = text.trim().length > 0 && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim(), privateMode, agenticMode && agenticAvailable);
    setText("");
  };

  return (
    <div className="px-4 pb-4 pt-2 bg-background border-t border-border">
      {privateMode && (
        <div className="flex items-center gap-1.5 mb-2 px-1">
          <Lock size={11} className="text-amber-500" />
          <p className="text-[11px] text-amber-500 font-medium">
            Private mode — Ollama only, no data sent externally
          </p>
        </div>
      )}
      {agenticMode && agenticAvailable && (
        <div className="flex items-center gap-1.5 mb-2 px-1">
          <Brain size={11} className="text-sky-500" />
          <p className="text-[11px] text-sky-500 font-medium">
            Agentic mode - plans multiple note searches before answering
          </p>
        </div>
      )}

      {/* Composer card */}
      <div className={`flex items-end gap-2 rounded-2xl border bg-card px-3 py-2.5 transition-all duration-200 ${
        focused
          ? "border-amber-400/70 ring-3 ring-amber-400/15 shadow-sm"
          : "border-border shadow-sm dark:shadow-none"
      }`}>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="Ask anything about your notes…"
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50 leading-[1.65] min-h-[26px] max-h-40"
          aria-label="Chat message"
        />

        <div className="flex items-center gap-1.5 shrink-0 pb-0.5">
          {agenticAvailable && (
            <motion.button whileTap={{ scale: 0.9 }}
              onClick={() => setAgenticMode((p) => !p)}
              className={`flex h-8 w-8 items-center justify-center rounded-xl border transition-all ${
                agenticMode
                  ? "bg-sky-50 dark:bg-sky-950/40 border-sky-300 dark:border-sky-800 text-sky-600 dark:text-sky-400"
                  : "border-border text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
              aria-label="Toggle agentic RAG"
              aria-pressed={agenticMode}
              title={agenticMode ? "Agentic RAG ON" : "Agentic RAG OFF"}
            >
              <Brain size={14} weight={agenticMode ? "bold" : "regular"} />
            </motion.button>
          )}

          <motion.button whileTap={{ scale: 0.9 }}
            onClick={() => setPrivateMode((p) => !p)}
            className={`flex h-8 w-8 items-center justify-center rounded-xl border transition-all ${
              privateMode
                ? "bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800 text-amber-600 dark:text-amber-400"
                : "border-border text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
            title={privateMode ? "Private ON (Ollama)" : "Private OFF (Gemini)"}
          >
            {privateMode ? <Lock size={14} weight="bold" /> : <LockOpen size={14} />}
          </motion.button>

          <motion.button whileTap={{ scale: 0.91 }}
            onClick={submit}
            disabled={!canSend}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500 hover:bg-amber-600 dark:bg-amber-500 dark:hover:bg-amber-400 text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed shadow-sm shadow-amber-200/60 dark:shadow-none"
            aria-label="Send"
          >
            <PaperPlaneTilt size={14} weight="bold" />
          </motion.button>
        </div>
      </div>

      <p className="mt-1.5 px-1 text-[10px] text-muted-foreground/60">
        Enter&nbsp;to&nbsp;send · Shift+Enter&nbsp;for&nbsp;new&nbsp;line
      </p>
    </div>
  );
}
