"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, TrendingUp, TrendingDown, Minus, LogOut, BarChart2 } from "lucide-react";
import { useTradeStore } from "@/hooks/useTradeStore";
import { cn, formatTime, confidenceColor } from "@/lib/utils";
import type { MonologueEntry, TradeDirection } from "@/types";

const ActionIcon = ({ action }: { action: TradeDirection }) => {
  if (action === "LONG")  return <TrendingUp className="w-3 h-3 text-neon-green" />;
  if (action === "SHORT") return <TrendingDown className="w-3 h-3 text-neon-red" />;
  if (action === "EXIT")  return <LogOut className="w-3 h-3 text-neon-yellow" />;
  return <Minus className="w-3 h-3 text-text-secondary" />;
};

const actionBadge: Record<TradeDirection, string> = {
  LONG:  "bg-neon-green/10 text-neon-green border-neon-green/30",
  SHORT: "bg-neon-red/10 text-neon-red border-neon-red/30",
  EXIT:  "bg-neon-yellow/10 text-neon-yellow border-neon-yellow/30",
  HOLD:  "bg-text-muted/10 text-text-muted border-text-muted/30",
};

function ThoughtEntry({ entry }: { entry: MonologueEntry }) {
  const { thought_log } = entry;
  const steps = [
    { label: "PRICE",  value: thought_log.price_analysis },
    { label: "CHART",  value: thought_log.technical_signals },
    { label: "NEWS",   value: thought_log.news_sentiment },
    { label: "MACRO",  value: thought_log.macro_outlook },
    { label: "BIAS",   value: thought_log.directional_bias },
    { label: "RISK",   value: thought_log.risk_assessment },
    { label: "DECIDE", value: thought_log.final_decision },
  ].filter((s) => s.value);

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25 }}
      className="border-b border-bg-border/50 py-3 px-4 hover:bg-bg-hover/30 transition-colors"
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="font-mono font-bold text-text-primary text-sm tracking-wider">
          {entry.symbol}
        </span>
        <span
          className={cn(
            "flex items-center gap-1 text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded border",
            actionBadge[entry.action]
          )}
        >
          <ActionIcon action={entry.action} />
          {entry.action}
        </span>
        <span className={cn("text-xs font-mono ml-auto", confidenceColor(entry.confidence))}>
          {(entry.confidence * 100).toFixed(0)}%
        </span>
        <span className="text-[10px] text-text-muted font-mono">
          {formatTime(entry.timestamp)}
        </span>
      </div>

      {/* Thought steps */}
      <div className="space-y-1 pl-2 border-l border-bg-border/50">
        {steps.map((step) => (
          <div key={step.label} className="flex gap-2">
            <span className="text-[10px] font-mono text-text-muted w-16 shrink-0 pt-0.5">
              [{step.label}]
            </span>
            <p className="text-[11px] font-mono text-text-secondary leading-relaxed">
              {step.value}
            </p>
          </div>
        ))}
      </div>

      {/* Reasoning summary */}
      <p className="mt-2 text-[11px] font-mono text-neon-blue/80 pl-2">
        ▶ {entry.reasoning}
      </p>
    </motion.div>
  );
}

export function InternalMonologue() {
  const monologue = useTradeStore((s) => s.monologue);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isUserScrolling = useRef(false);

  // Auto-scroll to top on new entries (newest is at top)
  useEffect(() => {
    if (!isUserScrolling.current && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [monologue.length]);

  return (
    <div className="flex flex-col h-full glass-card rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-bg-border">
        <Brain className="w-4 h-4 text-neon-green animate-pulse" />
        <span className="text-xs font-mono font-semibold text-text-secondary uppercase tracking-widest">
          Internal Monologue
        </span>
        <span className="ml-auto text-[10px] font-mono text-text-muted">
          {monologue.length} entries
        </span>
        {/* Live indicator */}
        <span className="flex items-center gap-1 text-[10px] font-mono text-neon-green">
          <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse" />
          LIVE
        </span>
      </div>

      {/* Feed */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto scrollbar-thin"
        onMouseEnter={() => { isUserScrolling.current = true; }}
        onMouseLeave={() => { isUserScrolling.current = false; }}
      >
        {monologue.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-text-muted">
            <Brain className="w-8 h-8 opacity-20" />
            <span className="text-xs font-mono">Waiting for agent thoughts…</span>
            <span className="text-[10px] font-mono animate-pulse">
              █ █ █ █ █
            </span>
          </div>
        ) : (
          <AnimatePresence mode="popLayout" initial={false}>
            {monologue.map((entry) => (
              <ThoughtEntry key={entry.id} entry={entry} />
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
