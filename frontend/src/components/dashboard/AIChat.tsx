"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, X, Send, Bot, User, AlertCircle, Loader2, Trash2 } from "lucide-react";
import { useTradeStore } from "@/hooks/useTradeStore";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Message {
  id: string;
  role: "user" | "model";
  content: string;
  off_topic?: boolean;
  timestamp: Date;
}

// ── Minimal markdown renderer ─────────────────────────────────────────────────
function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    // Bold
    const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, j) => {
      if (part.startsWith("**") && part.endsWith("**"))
        return <strong key={j} className="text-text-primary font-semibold">{part.slice(2, -2)}</strong>;
      if (part.startsWith("`") && part.endsWith("`"))
        return <code key={j} className="font-mono text-neon-blue bg-bg-border/50 px-1 rounded text-[10px]">{part.slice(1, -1)}</code>;
      return part;
    });

    // Bullet points
    if (line.trimStart().startsWith("• ") || line.trimStart().startsWith("- ")) {
      return (
        <div key={i} className="flex gap-1.5 ml-2">
          <span className="text-neon-green mt-0.5 shrink-0">▸</span>
          <span>{parts}</span>
        </div>
      );
    }

    // Headers
    if (line.startsWith("## "))
      return <p key={i} className="font-mono font-bold text-text-primary text-xs mt-2">{parts}</p>;
    if (line.startsWith("# "))
      return <p key={i} className="font-mono font-bold text-neon-green text-xs mt-2">{parts}</p>;

    if (line === "") return <div key={i} className="h-1" />;
    return <p key={i}>{parts}</p>;
  });
}

// ── Single message bubble ─────────────────────────────────────────────────────
function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn("flex gap-2.5 group", isUser && "flex-row-reverse")}
    >
      {/* Avatar */}
      <div className={cn(
        "w-6 h-6 rounded-lg shrink-0 flex items-center justify-center mt-0.5",
        isUser ? "bg-neon-blue/10 border border-neon-blue/30" : "bg-neon-green/10 border border-neon-green/30"
      )}>
        {isUser
          ? <User className="w-3 h-3 text-neon-blue" />
          : <Bot className="w-3 h-3 text-neon-green" />
        }
      </div>

      {/* Bubble */}
      <div className={cn(
        "max-w-[82%] rounded-xl px-3 py-2 text-[11px] font-mono leading-relaxed",
        isUser
          ? "bg-neon-blue/10 border border-neon-blue/20 text-text-primary"
          : msg.off_topic
          ? "bg-neon-red/10 border border-neon-red/20 text-neon-red"
          : "bg-bg-card border border-bg-border text-text-secondary"
      )}>
        {msg.off_topic
          ? <div className="flex items-center gap-1.5">
              <AlertCircle className="w-3 h-3 shrink-0" />
              {msg.content}
            </div>
          : <div className="space-y-0.5">{renderMarkdown(msg.content)}</div>
        }
        <p className={cn(
          "text-[9px] mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity",
          isUser ? "text-neon-blue/50 text-right" : "text-text-muted"
        )}>
          {msg.timestamp.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })}
        </p>
      </div>
    </motion.div>
  );
}

// ── Typing indicator ──────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="flex gap-2.5">
      <div className="w-6 h-6 rounded-lg bg-neon-green/10 border border-neon-green/30 flex items-center justify-center shrink-0">
        <Bot className="w-3 h-3 text-neon-green" />
      </div>
      <div className="bg-bg-card border border-bg-border rounded-xl px-3 py-2.5 flex gap-1 items-center">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-neon-green"
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
          />
        ))}
      </div>
    </div>
  );
}

// ── Main chat panel ───────────────────────────────────────────────────────────
export function AIChat() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "model",
      content: "Hey! I'm **NeuroTrader AI**, your finance assistant.\n\nAsk me anything about stocks, technical analysis, earnings, macro, trading strategies — I'm here to help.\n\nI have live access to your portfolio context.",
      timestamp: new Date(),
    },
  ]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const account = useTradeStore((s) => s.account);
  const watchlist = useTradeStore((s) => s.watchlist);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Focus input when opened
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    // Build history (exclude welcome message)
    const history = messages
      .filter((m) => m.id !== "welcome")
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const res = await fetch(`${API_BASE}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history,
          context: {
            account: account ?? undefined,
            watchlist: watchlist.slice(0, 10),
          },
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString() + "_ai",
          role: "model",
          content: data.reply,
          off_topic: data.off_topic,
          timestamp: new Date(),
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString() + "_err",
          role: "model",
          content: `Error: ${err.message}`,
          off_topic: false,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, messages, account, watchlist]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([{
      id: "welcome",
      role: "model",
      content: "Chat cleared. What would you like to know?",
      timestamp: new Date(),
    }]);
  };

  return (
    <>
      {/* ── Floating toggle button ──────────────────────────────────────────── */}
      <motion.button
        onClick={() => setOpen((v) => !v)}
        whileTap={{ scale: 0.93 }}
        className={cn(
          "fixed bottom-6 right-6 z-50 w-12 h-12 rounded-2xl",
          "flex items-center justify-center",
          "border-2 transition-all duration-200 shadow-lg",
          open
            ? "bg-bg-card border-neon-green/50 text-neon-green shadow-neon-green"
            : "bg-bg-card border-bg-border text-text-secondary hover:border-neon-green/40 hover:text-neon-green"
        )}
      >
        <AnimatePresence mode="wait">
          {open
            ? <motion.div key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }}>
                <X className="w-5 h-5" />
              </motion.div>
            : <motion.div key="chat" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }}>
                <MessageSquare className="w-5 h-5" />
              </motion.div>
          }
        </AnimatePresence>
        {/* Unread dot */}
        {!open && messages.length > 1 && (
          <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-neon-green border-2 border-bg-base" />
        )}
      </motion.button>

      {/* ── Chat panel ─────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            className={cn(
              "fixed bottom-22 right-6 z-50",
              "w-[380px] h-[540px] flex flex-col",
              "glass-card rounded-2xl overflow-hidden shadow-glass",
            )}
          >
            {/* Header */}
            <div className="flex items-center gap-2.5 px-4 py-3 border-b border-bg-border shrink-0">
              <div className="w-7 h-7 rounded-xl bg-neon-green/10 border border-neon-green/30 flex items-center justify-center">
                <Bot className="w-3.5 h-3.5 text-neon-green" />
              </div>
              <div>
                <p className="text-xs font-mono font-bold text-text-primary">NeuroTrader AI</p>
                <p className="text-[10px] font-mono text-text-muted">Finance questions only</p>
              </div>
              <button
                onClick={clearChat}
                className="ml-auto text-text-muted hover:text-neon-red transition-colors"
                title="Clear chat"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto scrollbar-thin px-3 py-3 space-y-3">
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <MessageBubble key={msg.id} msg={msg} />
                ))}
              </AnimatePresence>
              {loading && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="px-3 pb-3 pt-2 border-t border-bg-border shrink-0">
              <div className="flex gap-2 items-end">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about stocks, TA, macro…"
                  rows={1}
                  disabled={loading}
                  className={cn(
                    "flex-1 resize-none bg-bg-base border border-bg-border rounded-xl",
                    "px-3 py-2 text-[11px] font-mono text-text-primary",
                    "placeholder:text-text-muted outline-none",
                    "focus:border-neon-green/40 transition-colors",
                    "max-h-24 overflow-y-auto scrollbar-thin"
                  )}
                  style={{ minHeight: "36px" }}
                  onInput={(e) => {
                    const t = e.currentTarget;
                    t.style.height = "auto";
                    t.style.height = Math.min(t.scrollHeight, 96) + "px";
                  }}
                />
                <motion.button
                  whileTap={{ scale: 0.9 }}
                  onClick={sendMessage}
                  disabled={!input.trim() || loading}
                  className={cn(
                    "w-9 h-9 rounded-xl flex items-center justify-center shrink-0",
                    "border transition-all duration-150",
                    input.trim() && !loading
                      ? "bg-neon-green/10 border-neon-green/50 text-neon-green hover:bg-neon-green/20"
                      : "bg-bg-base border-bg-border text-text-muted cursor-not-allowed"
                  )}
                >
                  {loading
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <Send className="w-3.5 h-3.5" />
                  }
                </motion.button>
              </div>
              <p className="text-[9px] font-mono text-text-muted mt-1.5 text-center">
                Shift+Enter for new line · Enter to send
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
