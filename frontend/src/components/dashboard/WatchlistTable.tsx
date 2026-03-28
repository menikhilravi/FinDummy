"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Eye, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { useTradeStore } from "@/hooks/useTradeStore";
import { getWatchlist } from "@/lib/api";
import { cn, formatCurrency, sentimentColor } from "@/lib/utils";

export function WatchlistTable() {
  const watchlist = useTradeStore((s) => s.watchlist);
  const setWatchlist = useTradeStore((s) => s.setWatchlist);

  // Load initial watchlist from REST
  useEffect(() => {
    getWatchlist().then(setWatchlist).catch(() => {});
  }, [setWatchlist]);

  return (
    <div className="flex flex-col h-full glass-card rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-bg-border">
        <Eye className="w-4 h-4 text-neon-blue" />
        <span className="text-xs font-mono font-semibold text-text-secondary uppercase tracking-widest">
          Watchlist
        </span>
        <span className="ml-auto text-[10px] font-mono text-text-muted">
          {watchlist.length} tickers
        </span>
      </div>

      {/* Table header */}
      <div className="grid grid-cols-4 px-4 py-1.5 border-b border-bg-border/50">
        {["TICKER", "PRICE", "SENT", "SIGNAL"].map((h) => (
          <span key={h} className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
            {h}
          </span>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {watchlist.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <span className="text-xs font-mono text-text-muted">No data yet…</span>
          </div>
        ) : (
          <AnimatePresence mode="popLayout" initial={false}>
            {watchlist.map((entry) => {
              const sent = entry.sentiment_score;
              const sentClass = sentimentColor(sent);
              return (
                <motion.div
                  key={entry.symbol}
                  layout
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="grid grid-cols-4 items-center px-4 py-2.5 border-b border-bg-border/30 hover:bg-bg-hover/20 transition-colors"
                >
                  <span className="font-mono font-bold text-text-primary text-sm">
                    {entry.symbol}
                  </span>

                  <span className="font-mono text-xs text-text-secondary">
                    {entry.last_price ? formatCurrency(entry.last_price) : "—"}
                  </span>

                  <div className={cn("flex items-center gap-1 text-xs font-mono", sentClass)}>
                    {sent > 0.1 ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : sent < -0.1 ? (
                      <TrendingDown className="w-3 h-3" />
                    ) : (
                      <Minus className="w-3 h-3" />
                    )}
                    {sent > 0 ? "+" : ""}
                    {sent.toFixed(2)}
                  </div>

                  <div className="text-[10px] font-mono text-text-muted truncate pr-2" title={entry.notes}>
                    {entry.notes?.slice(0, 30) ?? "—"}
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
