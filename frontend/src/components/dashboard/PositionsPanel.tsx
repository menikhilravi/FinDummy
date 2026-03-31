"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Briefcase, TrendingUp, TrendingDown, Zap } from "lucide-react";
import { useTradeStore } from "@/hooks/useTradeStore";
import { cn, formatCurrency } from "@/lib/utils";
import { TradeFeed } from "./TradeAlerts";

export function RightPanel() {
  const [tab, setTab] = useState<"trades" | "positions">("trades");
  const positions = useTradeStore((s) => s.positions);
  const recentTrades = useTradeStore((s) => s.recentTrades);

  const totalUnrealizedPL = positions.reduce((sum, p) => sum + p.unrealized_pl, 0);
  const isUp = totalUnrealizedPL >= 0;

  return (
    <div className="flex flex-col h-full glass-card rounded-xl overflow-hidden">
      {/* Tab bar */}
      <div className="flex items-center border-b border-bg-border shrink-0">
        <button
          onClick={() => setTab("trades")}
          className={cn(
            "flex items-center gap-1.5 px-4 py-3 text-[10px] font-mono uppercase tracking-widest border-b-2 transition-colors",
            tab === "trades"
              ? "border-neon-yellow text-neon-yellow"
              : "border-transparent text-text-muted hover:text-text-secondary"
          )}
        >
          <Zap className="w-3 h-3" />
          Trade Feed
          {recentTrades.length > 0 && (
            <span className="ml-1 text-[9px] bg-neon-yellow/20 text-neon-yellow px-1 rounded">
              {recentTrades.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("positions")}
          className={cn(
            "flex items-center gap-1.5 px-4 py-3 text-[10px] font-mono uppercase tracking-widest border-b-2 transition-colors",
            tab === "positions"
              ? "border-neon-blue text-neon-blue"
              : "border-transparent text-text-muted hover:text-text-secondary"
          )}
        >
          <Briefcase className="w-3 h-3" />
          Positions
          {positions.length > 0 && (
            <span className={cn(
              "ml-1 text-[9px] px-1 rounded",
              isUp ? "bg-neon-green/20 text-neon-green" : "bg-neon-red/20 text-neon-red"
            )}>
              {positions.length}
            </span>
          )}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {tab === "trades" ? (
          <TradeFeedInner />
        ) : (
          <PositionsInner positions={positions} totalUnrealizedPL={totalUnrealizedPL} isUp={isUp} />
        )}
      </div>
    </div>
  );
}

function TradeFeedInner() {
  const trades = useTradeStore((s) => s.recentTrades);
  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {trades.length === 0 ? (
        <div className="flex items-center justify-center h-full text-text-muted">
          <span className="text-xs font-mono">No trades yet…</span>
        </div>
      ) : (
        <AnimatePresence mode="popLayout" initial={false}>
          {trades.map((trade, i) => (
            <motion.div
              key={`${trade.order_id}-${i}`}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "flex items-center gap-3 px-4 py-2.5 border-b border-bg-border/40",
                "hover:bg-bg-hover/20 transition-colors"
              )}
            >
              <div className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
                trade.side === "BUY" ? "bg-neon-green/10 text-neon-green" : "bg-neon-red/10 text-neon-red"
              )}>
                {trade.side === "BUY" ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-text-primary text-sm">{trade.symbol}</span>
                  <span className={cn(
                    "text-[10px] font-mono font-semibold",
                    trade.direction === "LONG" ? "text-neon-green" :
                    trade.direction === "SHORT" ? "text-neon-red" :
                    trade.direction === "EXIT" ? "text-neon-yellow" : "text-text-muted"
                  )}>
                    {trade.direction ?? trade.side}
                  </span>
                  {trade.trading_mode === "PAPER" && (
                    <span className="text-[10px] font-mono text-text-muted border border-bg-border rounded px-1">PAPER</span>
                  )}
                </div>
                <p className="text-[11px] font-mono text-text-muted truncate">
                  {trade.qty.toFixed(4)} @ ${trade.price.toFixed(2)}
                </p>
              </div>
              <div className="text-right">
                <span className="text-[10px] font-mono text-text-muted block">
                  {new Date(trade.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </span>
                <span className="text-[10px] font-mono text-neon-blue">
                  {(trade.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      )}
    </div>
  );
}

function PositionsInner({
  positions,
  totalUnrealizedPL,
  isUp,
}: {
  positions: import("@/types").Position[];
  totalUnrealizedPL: number;
  isUp: boolean;
}) {
  if (positions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-text-muted px-4 text-center">
        <Briefcase className="w-6 h-6 opacity-40" />
        <span className="text-xs font-mono">No open positions</span>
        <span className="text-[10px] font-mono opacity-60">
          Portfolio changes are from unrealized P&L on existing positions
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Summary strip */}
      <div className="px-4 py-2 border-b border-bg-border/40 flex items-center justify-between">
        <span className="text-[10px] font-mono text-text-muted">Unrealized P&L</span>
        <span className={cn("text-xs font-mono font-bold", isUp ? "text-neon-green" : "text-neon-red")}>
          {isUp ? "+" : ""}{formatCurrency(totalUnrealizedPL)}
        </span>
      </div>
      {positions.map((pos) => {
        const plUp = pos.unrealized_pl >= 0;
        const plPct = (pos.unrealized_plpc * 100).toFixed(2);
        return (
          <motion.div
            key={pos.symbol}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-start gap-3 px-4 py-3 border-b border-bg-border/40 hover:bg-bg-hover/20 transition-colors"
          >
            <div className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
              pos.side === "long" ? "bg-neon-green/10 text-neon-green" : "bg-neon-red/10 text-neon-red"
            )}>
              {pos.side === "long" ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="font-mono font-bold text-text-primary text-sm">{pos.symbol}</span>
                <span className={cn("text-xs font-mono font-semibold", plUp ? "text-neon-green" : "text-neon-red")}>
                  {plUp ? "+" : ""}{formatCurrency(pos.unrealized_pl)}
                </span>
              </div>
              <div className="flex items-center justify-between mt-0.5">
                <span className="text-[11px] font-mono text-text-muted">
                  {pos.qty} @ ${pos.avg_entry_price.toFixed(2)}
                </span>
                <span className={cn("text-[10px] font-mono", plUp ? "text-neon-green" : "text-neon-red")}>
                  {plUp ? "+" : ""}{plPct}%
                </span>
              </div>
              <div className="flex items-center justify-between mt-0.5">
                <span className="text-[10px] font-mono text-text-muted">
                  Current ${pos.current_price.toFixed(2)}
                </span>
                <span className="text-[10px] font-mono text-neon-blue">
                  MV {formatCurrency(pos.market_value)}
                </span>
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
