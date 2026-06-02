"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Lock, Send } from "lucide-react";

interface Props {
  onSend: (message: string, privateMode: boolean) => void;
  disabled?: boolean;
}

export function ChatComposer({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const [privateMode, setPrivateMode] = useState(false);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, privateMode);
    setText("");
  };

  return (
    <div className="border-t bg-background px-4 pt-3 pb-4">
      <div className="flex gap-2 items-end">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask anything about your notes…"
          rows={2}
          disabled={disabled}
          className="resize-none text-sm flex-1"
          aria-label="Chat message"
        />
        <div className="flex flex-col gap-1.5">
          <Button
            size="icon"
            onClick={submit}
            disabled={disabled || !text.trim()}
            aria-label="Send"
          >
            <Send size={16} />
          </Button>
          <button
            onClick={() => setPrivateMode((p) => !p)}
            className={`flex items-center justify-center h-9 w-9 rounded-md border transition-colors ${
              privateMode
                ? "bg-amber-100 border-amber-400 text-amber-700"
                : "border-input text-muted-foreground hover:bg-muted"
            }`}
            title={privateMode ? "Private mode ON (Ollama)" : "Private mode OFF (Gemini)"}
            aria-label="Toggle private mode"
          >
            <Lock size={14} />
          </button>
        </div>
      </div>
      {privateMode && (
        <p className="text-xs text-amber-600 mt-1">
          Private mode — Ollama only, no data leaves your machine.
        </p>
      )}
    </div>
  );
}
