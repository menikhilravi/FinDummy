"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Bot, BarChart2, Activity } from "lucide-react";

import { useWebSocket } from "@/hooks/useWebSocket";
import { useTradeStore } from "@/hooks/useTradeStore";
import { getAccount, getWatchlist } from "@/lib/api";
import { cn } from "@/lib/utils";

import { InternalMonologue } from "@/components/dashboard/InternalMonologue";
import { TradeAlerts, TradeFeed } from "@/components/dashboard/TradeAlerts";
import { EquityChart } from "@/components/dashboard/EquityChart";
import { PanicButton } from "@/components/dashboard/PanicButton";
import { WatchlistTable } from "@/components/dashboard/WatchlistTable";
import { StatsHUD } from "@/components/dashboard/StatsHUD";
import { AIChat } from "@/components/dashboard/AIChat";
import { UsageDashboard } from "@/components/dashboard/UsageDashboard";

export default function DashboardPage() {
  const [view, setView] = useState<"trading" | "usage">("trading");
  const handleWsEvent = useTradeStore((s) => s.handleWsEvent);
  const setWsStatus = useTradeStore((s) => s.setWsStatus);
  const setAccount = useTradeStore((s) => s.setAccount);
  const setWatchlist = useTradeStore((s) => s.setWatchlist);

  const { status } = useWebSocket({
    onMessage: handleWsEvent,
  });

  // Sync WS status into store
  useEffect(() => {
    setWsStatus(status);
  }, [status, setWsStatus]);

  // Bootstrap: load account + watchlist via REST
  useEffect(() => {
    getAccount().then(setAccount).catch(() => {});
    getWatchlist().then(setWatchlist).catch(() => {});

    // Poll account every 30 s as fallback
    const interval = setInterval(() => {
      getAccount().then(setAccount).catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, [setAccount, setWatchlist]);

  return (
    <div className="min-h-screen bg-bg-base grid-bg">
      {/* ── Toast overlay ──────────────────────────────────────────────────── */}
      <TradeAlerts />

      {/* ── AI Chat ────────────────────────────────────────────────────────── */}
      <AIChat />

      {/* ── Top nav ────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 flex items-center gap-3 px-6 py-3 border-b border-bg-border glass-card">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-neon-green/10 border border-neon-green/30 flex items-center justify-center">
            <Bot className="w-4 h-4 text-neon-green" />
          </div>
          <div>
            <h1 className="text-sm font-mono font-bold text-text-primary text-glow-green">
              FINDUMMY
            </h1>
            <p className="text-[10px] font-mono text-text-muted">
              AI-Powered Trading Agent
            </p>
          </div>
        </div>

        {/* Ticker marquee */}
        <div className="flex-1 mx-6 overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]">
          <TickerMarquee />
        </div>

        {/* View toggle */}
        <div className="flex items-center gap-1 p-0.5 rounded-lg border border-bg-border bg-bg-surface mr-2">
          <button
            onClick={() => setView("trading")}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-mono transition-all",
              view === "trading"
                ? "bg-neon-green/10 text-neon-green border border-neon-green/30"
                : "text-text-muted hover:text-text-secondary"
            )}
          >
            <Activity className="w-3 h-3" />
            TRADING
          </button>
          <button
            onClick={() => setView("usage")}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-mono transition-all",
              view === "usage"
                ? "bg-neon-blue/10 text-neon-blue border border-neon-blue/30"
                : "text-text-muted hover:text-text-secondary"
            )}
          >
            <BarChart2 className="w-3 h-3" />
            USAGE
          </button>
        </div>

        {/* Panic button in header */}
        <PanicButton />
      </header>

      {/* ── Main layout ────────────────────────────────────────────────────── */}
      {view === "usage" && (
        <main style={{ height: "calc(100vh - 64px)" }} className="overflow-y-auto">
          <UsageDashboard />
        </main>
      )}
      <main className={cn("p-4 grid grid-cols-12 gap-4", view !== "trading" && "hidden")} style={{ height: "calc(100vh - 64px)" }}>

        {/* ── Left column (4/12): Stats + Watchlist ───────────────────────── */}
        <motion.aside
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="col-span-12 lg:col-span-3 flex flex-col gap-4 overflow-hidden"
        >
          <StatsHUD />
          <div className="flex-1 min-h-0">
            <WatchlistTable />
          </div>
        </motion.aside>

        {/* ── Centre column (5/12): Equity chart + Monologue ──────────────── */}
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="col-span-12 lg:col-span-6 flex flex-col gap-4 overflow-hidden"
        >
          {/* Equity chart — fixed height */}
          <div className="h-[280px] shrink-0">
            <EquityChart />
          </div>

          {/* Internal Monologue — fills remaining space */}
          <div className="flex-1 min-h-0">
            <InternalMonologue />
          </div>
        </motion.section>

        {/* ── Right column (3/12): Trade feed ─────────────────────────────── */}
        <motion.aside
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="col-span-12 lg:col-span-3 flex flex-col overflow-hidden"
        >
          <TradeFeed />
        </motion.aside>
      </main>
    </div>
  );
}

// ── Ticker marquee ────────────────────────────────────────────────────────────

function TickerMarquee() {
  const watchlist = useTradeStore((s) => s.watchlist);

  if (watchlist.length === 0) {
    return (
      <div className="flex gap-4 text-[11px] font-mono text-text-muted animate-pulse">
        {["AAPL", "MSFT", "NVDA", "TSLA", "SPY"].map((t) => (
          <span key={t}>{t} —.——</span>
        ))}
      </div>
    );
  }

  const items = [...watchlist, ...watchlist]; // duplicate for seamless loop

  return (
    <div className="flex gap-6 animate-marquee whitespace-nowrap">
      {items.map((entry, i) => {
        const isPos = entry.sentiment_score >= 0;
        return (
          <div key={`${entry.symbol}-${i}`} className="flex items-center gap-1.5 shrink-0">
            <span className="text-[11px] font-mono font-semibold text-text-primary">
              {entry.symbol}
            </span>
            <span className="text-[11px] font-mono text-text-secondary">
              ${entry.last_price?.toFixed(2) ?? "—"}
            </span>
            <span className={`text-[10px] font-mono ${isPos ? "text-neon-green" : "text-neon-red"}`}>
              {isPos ? "▲" : "▼"} {Math.abs(entry.sentiment_score * 100).toFixed(2)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
