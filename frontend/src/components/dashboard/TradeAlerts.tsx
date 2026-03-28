"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TrendingUp, TrendingDown, ShieldAlert, AlertTriangle, X, Zap } from "lucide-react";
import { useTradeStore } from "@/hooks/useTradeStore";
import { cn, formatTime } from "@/lib/utils";
import type { ToastData } from "@/types";

const toastConfig = {
  trade: {
    BUY: {
      icon: TrendingUp,
      gradient: "from-neon-green/20 to-transparent",
      border: "border-neon-green/40",
      iconColor: "text-neon-green",
      glow: "shadow-neon-green",
    },
    SELL: {
      icon: TrendingDown,
      gradient: "from-neon-red/20 to-transparent",
      border: "border-neon-red/40",
      iconColor: "text-neon-red",
      glow: "shadow-neon-red",
    },
  },
  safety: {
    icon: ShieldAlert,
    gradient: "from-neon-yellow/10 to-transparent",
    border: "border-neon-yellow/30",
    iconColor: "text-neon-yellow",
    glow: "",
  },
  error: {
    icon: AlertTriangle,
    gradient: "from-neon-red/10 to-transparent",
    border: "border-neon-red/30",
    iconColor: "text-neon-red",
    glow: "",
  },
  shutdown: {
    icon: Zap,
    gradient: "from-neon-red/20 to-transparent",
    border: "border-neon-red/50",
    iconColor: "text-neon-red",
    glow: "shadow-neon-red",
  },
};

function ToastItem({ toast }: { toast: ToastData }) {
  const dismiss = useTradeStore((s) => s.dismissToast);

  const config =
    toast.type === "trade"
      ? toastConfig.trade[toast.side ?? "BUY"]
      : toastConfig[toast.type];

  const Icon = config.icon;

  // Auto-dismiss after 8 seconds for trade alerts
  useEffect(() => {
    if (toast.type === "trade") {
      const timer = setTimeout(() => dismiss(toast.id), 8000);
      return () => clearTimeout(timer);
    }
  }, [toast.id, toast.type, dismiss]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 60, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 60, scale: 0.9 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className={cn(
        "relative flex items-start gap-3 p-4 rounded-xl border backdrop-blur-md",
        "bg-gradient-to-r",
        config.gradient,
        config.border,
        config.glow && config.glow,
        "min-w-[300px] max-w-[380px]"
      )}
    >
      {/* Icon */}
      <div className={cn("mt-0.5 shrink-0", config.iconColor)}>
        <Icon className="w-5 h-5" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-text-primary text-sm">
            {toast.title}
          </span>
          {toast.confidence !== undefined && (
            <span className="text-[10px] font-mono text-text-muted">
              {(toast.confidence * 100).toFixed(0)}% conf
            </span>
          )}
        </div>
        <p className="text-xs font-mono text-text-secondary mt-0.5 leading-relaxed">
          {toast.description}
        </p>
        <span className="text-[10px] font-mono text-text-muted mt-1 block">
          {formatTime(toast.timestamp)}
        </span>
      </div>

      {/* Dismiss */}
      <button
        onClick={() => dismiss(toast.id)}
        className="shrink-0 text-text-muted hover:text-text-primary transition-colors"
      >
        <X className="w-3.5 h-3.5" />
      </button>

      {/* Progress bar for trade alerts */}
      {toast.type === "trade" && (
        <motion.div
          className={cn(
            "absolute bottom-0 left-0 h-0.5 rounded-b-xl",
            toast.side === "BUY" ? "bg-neon-green" : "bg-neon-red"
          )}
          initial={{ width: "100%" }}
          animate={{ width: "0%" }}
          transition={{ duration: 8, ease: "linear" }}
        />
      )}
    </motion.div>
  );
}

export function TradeAlerts() {
  const toasts = useTradeStore((s) => s.toasts);

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-3 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastItem toast={toast} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}

// ── Trade Feed panel (persistent log) ─────────────────────────────────────────

export function TradeFeed() {
  const trades = useTradeStore((s) => s.recentTrades);

  return (
    <div className="flex flex-col h-full glass-card rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-bg-border">
        <Zap className="w-4 h-4 text-neon-yellow" />
        <span className="text-xs font-mono font-semibold text-text-secondary uppercase tracking-widest">
          Trade Feed
        </span>
        <span className="ml-auto text-[10px] font-mono text-text-muted">
          {trades.length} orders
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
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
                <div
                  className={cn(
                    "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
                    trade.side === "BUY"
                      ? "bg-neon-green/10 text-neon-green"
                      : "bg-neon-red/10 text-neon-red"
                  )}
                >
                  {trade.side === "BUY" ? (
                    <TrendingUp className="w-4 h-4" />
                  ) : (
                    <TrendingDown className="w-4 h-4" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-text-primary text-sm">
                      {trade.symbol}
                    </span>
                    <span
                      className={cn(
                        "text-[10px] font-mono font-semibold",
                        trade.direction === "LONG"  ? "text-neon-green" :
                        trade.direction === "SHORT" ? "text-neon-red" :
                        trade.direction === "EXIT"  ? "text-neon-yellow" :
                        "text-text-muted"
                      )}
                    >
                      {trade.direction ?? trade.side}
                    </span>
                    {trade.trading_mode === "PAPER" && (
                      <span className="text-[10px] font-mono text-text-muted border border-bg-border rounded px-1">
                        PAPER
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] font-mono text-text-muted truncate">
                    {trade.qty.toFixed(4)} @ ${trade.price.toFixed(2)}
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-mono text-text-muted block">
                    {formatTime(trade.timestamp)}
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
    </div>
  );
}
