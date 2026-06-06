"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Brain, Lock, LockOpen, PaperPlaneTilt } from "@phosphor-icons/react";

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
    <div className="bg-background px-4 pb-4 pt-2">
      <div className="mx-auto w-full max-w-5xl">
        {privateMode && (
          <div className="mb-2 flex items-center gap-1.5 px-1">
            <Lock size={11} className="text-primary" />
            <p className="text-[11px] font-medium text-primary">
              Private mode - Ollama only, no data sent externally
            </p>
          </div>
        )}
        {agenticMode && agenticAvailable && (
          <div className="mb-2 flex items-center gap-1.5 px-1">
            <Brain size={11} className="text-muted-foreground" />
            <p className="text-[11px] font-medium text-muted-foreground">
              Agentic mode - plans multiple note searches before answering
            </p>
          </div>
        )}

        <div
          className={`flex min-w-0 items-end gap-2 rounded-lg border bg-card px-3 py-2.5 shadow-sm shadow-zinc-950/[0.025] transition-all duration-200 ${
            focused ? "border-primary/70 ring-3 ring-primary/15" : "border-border"
          }`}
        >
          <label htmlFor="chat-message" className="sr-only">Chat message</label>
          <textarea
            id="chat-message"
            ref={textareaRef}
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Ask anything about your notes..."
            rows={1}
            disabled={disabled}
            className="min-h-[28px] max-h-40 min-w-0 flex-1 basis-0 resize-none bg-transparent text-sm leading-[1.65] text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
          />

          <div className="flex shrink-0 items-center gap-1.5 pb-0.5">
            {agenticAvailable && (
              <motion.button
                type="button"
                whileTap={{ scale: 0.9 }}
                onClick={() => setAgenticMode((previous) => !previous)}
                className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-all focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/15 ${
                  agenticMode
                    ? "border-primary/30 bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
                aria-label="Toggle agentic RAG"
                aria-pressed={agenticMode}
                title={agenticMode ? "Agentic RAG on" : "Agentic RAG off"}
              >
                <Brain size={14} weight={agenticMode ? "bold" : "regular"} />
              </motion.button>
            )}

            <motion.button
              type="button"
              whileTap={{ scale: 0.9 }}
              onClick={() => setPrivateMode((previous) => !previous)}
              className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-all focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-primary/15 ${
                privateMode
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
              aria-label="Toggle private mode"
              aria-pressed={privateMode}
              title={privateMode ? "Private on (Ollama)" : "Private off (Gemini)"}
            >
              {privateMode ? <Lock size={14} weight="bold" /> : <LockOpen size={14} />}
            </motion.button>

            <motion.button
              type="button"
              whileTap={{ scale: 0.91 }}
              onClick={submit}
              disabled={!canSend}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm shadow-amber-200/60 transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-30 dark:shadow-none"
              aria-label="Send"
            >
              <PaperPlaneTilt size={14} weight="bold" />
            </motion.button>
          </div>
        </div>

        <p className="mt-1.5 px-1 text-[10px] text-muted-foreground/70">
          Enter to send / Shift+Enter for a new line
        </p>
      </div>
    </div>
  );
}
