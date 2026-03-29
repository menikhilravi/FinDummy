"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  BarChart2,
  Shield,
  Wifi,
  WifiOff,
  AlertTriangle,
} from "lucide-react";
import { useTradeStore } from "@/hooks/useTradeStore";
import { getSafetyStats } from "@/lib/api";
import { cn, formatCurrency } from "@/lib/utils";

interface SafetyStats {
  date: string;
  realised_pnl: number;
  trade_count: number;
}

export function StatsHUD() {
  const account = useTradeStore((s) => s.account);
  const wsStatus = useTradeStore((s) => s.wsStatus);
  const isAgentRunning = useTradeStore((s) => s.isAgentRunning);
  const marketState = useTradeStore((s) => s.marketState);
  const tradingAllowed = useTradeStore((s) => s.tradingAllowed);
  const recentTrades = useTradeStore((s) => s.recentTrades);
  const [safetyStats, setSafetyStats] = useState<SafetyStats | null>(null);

  useEffect(() => {
    const load = () => getSafetyStats().then(setSafetyStats).catch(() => {});
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, []);

  const dailyPnl = safetyStats?.realised_pnl ?? 0;
  const dailyLossLimit = (account?.equity ?? 100_000) * 0.015;
  const circuitPct =
    dailyPnl < 0 ? Math.min(Math.abs(dailyPnl) / dailyLossLimit, 1) : 0;

  const stats = [
    {
      label: "Portfolio",
      value: formatCurrency(account?.portfolio_value ?? 0),
      icon: BarChart2,
      color: "text-neon-blue",
      bg: "bg-neon-blue/10",
    },
    {
      label: "Daily PnL",
      value: `${dailyPnl >= 0 ? "+" : ""}${formatCurrency(dailyPnl)}`,
      icon: Activity,
      color: dailyPnl >= 0 ? "text-neon-green" : "text-neon-red",
      bg: dailyPnl >= 0 ? "bg-neon-green/10" : "bg-neon-red/10",
    },
    {
      label: "Trades Today",
      value: safetyStats?.trade_count ?? recentTrades.length,
      icon: BarChart2,
      color: "text-neon-yellow",
      bg: "bg-neon-yellow/10",
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      {/* Connection & agent status */}
      <div className="glass-card rounded-xl px-4 py-3 flex items-center gap-3">
        {/* WS status */}
        <div className="flex items-center gap-1.5">
          {wsStatus === "connected" ? (
            <>
              <Wifi className="w-3.5 h-3.5 text-neon-green" />
              <span className="text-[10px] font-mono text-neon-green">LIVE</span>
            </>
          ) : wsStatus === "connecting" ? (
            <>
              <Wifi className="w-3.5 h-3.5 text-neon-yellow animate-pulse" />
              <span className="text-[10px] font-mono text-neon-yellow">CONNECTING</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 text-neon-red" />
              <span className="text-[10px] font-mono text-neon-red">OFFLINE</span>
            </>
          )}
        </div>

        <div className="h-3 w-px bg-bg-border" />

        {/* Agent status */}
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              isAgentRunning
                ? "bg-neon-green animate-pulse"
                : "bg-neon-red"
            )}
          />
          <span className="text-[10px] font-mono text-text-secondary">
            AGENT {isAgentRunning ? "RUNNING" : "STOPPED"}
          </span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <span className={cn(
            "text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded border",
            marketState === "OPEN"
              ? "text-neon-green border-neon-green/40 bg-neon-green/10"
              : marketState === "EXTENDED"
              ? "text-neon-yellow border-neon-yellow/40 bg-neon-yellow/10"
              : "text-text-muted border-bg-border bg-bg-border/30"
          )}>
            {marketState === "OPEN" ? "● MARKET OPEN" : marketState === "EXTENDED" ? "◐ EXTENDED" : "○ CLOSED"}
          </span>
          {!tradingAllowed && (
            <span className="text-[10px] font-mono text-text-muted">analysis only</span>
          )}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-3">
        {stats.map((stat) => (
          <motion.div
            key={stat.label}
            whileHover={{ scale: 1.02 }}
            className="glass-card rounded-xl p-3 flex flex-col gap-1"
          >
            <div className="flex items-center gap-1.5">
              <div className={cn("p-1 rounded-lg", stat.bg)}>
                <stat.icon className={cn("w-3 h-3", stat.color)} />
              </div>
              <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
                {stat.label}
              </span>
            </div>
            <span className={cn("font-mono font-bold text-sm truncate", stat.color)}>
              {stat.value}
            </span>
          </motion.div>
        ))}
      </div>

      {/* Circuit breaker bar */}
      <div className="glass-card rounded-xl px-4 py-3">
        <div className="flex items-center gap-2 mb-2">
          <Shield
            className={cn(
              "w-3.5 h-3.5",
              circuitPct >= 0.8
                ? "text-neon-red animate-pulse"
                : "text-neon-green"
            )}
          />
          <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
            Circuit Breaker
          </span>
          <span
            className={cn(
              "ml-auto text-[10px] font-mono",
              circuitPct >= 0.8 ? "text-neon-red" : "text-text-secondary"
            )}
          >
            {(circuitPct * 100).toFixed(1)}% / 100%
          </span>
        </div>
        <div className="w-full h-2 bg-bg-border rounded-full overflow-hidden">
          <motion.div
            className={cn(
              "h-full rounded-full transition-colors duration-500",
              circuitPct < 0.5
                ? "bg-neon-green"
                : circuitPct < 0.8
                ? "bg-neon-yellow"
                : "bg-neon-red"
            )}
            initial={{ width: 0 }}
            animate={{ width: `${circuitPct * 100}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          />
        </div>
        {circuitPct >= 0.8 && (
          <div className="flex items-center gap-1 mt-1.5">
            <AlertTriangle className="w-3 h-3 text-neon-red" />
            <span className="text-[10px] font-mono text-neon-red">
              Approaching daily loss limit — trading may halt
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
