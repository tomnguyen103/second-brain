"use client";

import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { PaperPlaneTilt, Lock, LockOpen } from "@phosphor-icons/react";

interface Props {
  onSend: (message: string, privateMode: boolean) => void;
  disabled?: boolean;
}

export function ChatComposer({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const [privateMode, setPrivateMode] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /* Auto-resize textarea */
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const canSend = text.trim().length > 0 && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim(), privateMode);
    setText("");
  };

  return (
    <div className="border-t border-zinc-200 bg-white px-4 pt-3 pb-4">
      {/* Private mode banner */}
      {privateMode && (
        <div className="flex items-center gap-1.5 mb-2 px-1">
          <Lock size={11} className="text-amber-600" />
          <p className="text-[11px] text-amber-600 font-medium">
            Private mode — Ollama only, nothing leaves your machine
          </p>
        </div>
      )}

      <div className="flex items-end gap-2">
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask anything about your notes…"
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-amber-400/60 focus:border-amber-400 transition-all duration-150 disabled:opacity-50 leading-[1.6] min-h-[42px] max-h-40"
          aria-label="Chat message"
        />

        {/* Action buttons */}
        <div className="flex items-center gap-1.5 pb-px">
          {/* Private mode toggle */}
          <motion.button
            whileTap={{ scale: 0.93 }}
            onClick={() => setPrivateMode((p) => !p)}
            className={`flex h-9 w-9 items-center justify-center rounded-lg border transition-all duration-150 ${
              privateMode
                ? "bg-amber-50 border-amber-300 text-amber-600"
                : "border-zinc-200 bg-white text-zinc-400 hover:text-zinc-600 hover:border-zinc-300"
            }`}
            title={privateMode ? "Private mode ON" : "Private mode OFF"}
            aria-label="Toggle private mode"
          >
            {privateMode ? <Lock size={15} weight="bold" /> : <LockOpen size={15} />}
          </motion.button>

          {/* Send */}
          <motion.button
            whileTap={{ scale: 0.94 }}
            onClick={submit}
            disabled={!canSend}
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500 text-white transition-all duration-150 hover:bg-amber-600 disabled:opacity-30 disabled:cursor-not-allowed shadow-sm shadow-amber-200"
            aria-label="Send"
          >
            <PaperPlaneTilt size={15} weight="bold" />
          </motion.button>
        </div>
      </div>

      <p className="mt-1.5 px-1 text-[10px] text-zinc-400">
        Enter to send&nbsp;&nbsp;·&nbsp;&nbsp;Shift+Enter for new line
      </p>
    </div>
  );
}
