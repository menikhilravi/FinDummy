"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity, AlertTriangle, CheckCircle, RefreshCw, Info,
} from "lucide-react";
import { getUsage } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ServiceData {
  label: string;
  daily_limit: number | null;
  rpm_limit: number | null;
  tier: string;
  color: string;
  calls_session: number;
  calls_today: number;
  daily_pct: number | null;
}

const COLOR_MAP: Record<string, string> = {
  orange:  "text-orange-400 border-orange-400/30 bg-orange-400/10",
  blue:    "text-blue-400 border-blue-400/30 bg-blue-400/10",
  cyan:    "text-cyan-400 border-cyan-400/30 bg-cyan-400/10",
  yellow:  "text-yellow-400 border-yellow-400/30 bg-yellow-400/10",
  green:   "text-neon-green border-neon-green/30 bg-neon-green/10",
  emerald: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10",
};

const BAR_COLOR: Record<string, string> = {
  orange:  "bg-orange-400",
  blue:    "bg-blue-400",
  cyan:    "bg-cyan-400",
  yellow:  "bg-yellow-400",
  green:   "bg-neon-green",
  emerald: "bg-emerald-400",
};

function statusIcon(pct: number | null) {
  if (pct === null) return <CheckCircle className="w-3.5 h-3.5 text-neon-green" />;
  if (pct >= 90) return <AlertTriangle className="w-3.5 h-3.5 text-neon-red animate-pulse" />;
  if (pct >= 70) return <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />;
  return <CheckCircle className="w-3.5 h-3.5 text-neon-green" />;
}

function ServiceCard({ id, data }: { id: string; data: ServiceData }) {
  const pct = data.daily_pct;
  const barColor = BAR_COLOR[data.color] ?? "bg-neon-green";
  const accent = COLOR_MAP[data.color] ?? COLOR_MAP.green;
  const isWarning = pct !== null && pct >= 70;
  const isCritical = pct !== null && pct >= 90;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "glass-card rounded-xl p-4 flex flex-col gap-3",
        isCritical && "border border-neon-red/30",
        isWarning && !isCritical && "border border-yellow-400/20",
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={cn("text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border", accent)}>
            {id.toUpperCase().replace("_", " ")}
          </span>
          <span className="text-[10px] font-mono text-text-muted">{data.tier}</span>
        </div>
        {statusIcon(pct)}
      </div>

      <p className="text-xs font-mono text-text-secondary">{data.label}</p>

      {/* Daily usage bar */}
      {data.daily_limit ? (
        <div>
          <div className="flex justify-between mb-1">
            <span className="text-[10px] font-mono text-text-muted">Today</span>
            <span className={cn(
              "text-[10px] font-mono font-semibold",
              isCritical ? "text-neon-red" : isWarning ? "text-yellow-400" : "text-text-secondary"
            )}>
              {data.calls_today.toLocaleString()} / {data.daily_limit.toLocaleString()}
            </span>
          </div>
          <div className="w-full h-1.5 bg-bg-border rounded-full overflow-hidden">
            <motion.div
              className={cn("h-full rounded-full", barColor)}
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(pct ?? 0, 100)}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          </div>
          <p className={cn(
            "text-[9px] font-mono mt-1",
            isCritical ? "text-neon-red" : "text-text-muted"
          )}>
            {pct?.toFixed(1)}% of daily free limit
            {isCritical && " — NEAR LIMIT"}
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-1.5">
          <CheckCircle className="w-3 h-3 text-neon-green" />
          <span className="text-[10px] font-mono text-text-muted">No daily cap</span>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-2 pt-1 border-t border-bg-border/50">
        <div>
          <p className="text-[9px] font-mono text-text-muted uppercase tracking-wider">Session</p>
          <p className="text-sm font-mono font-bold text-text-primary">
            {data.calls_session.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-[9px] font-mono text-text-muted uppercase tracking-wider">Rate limit</p>
          <p className="text-sm font-mono font-bold text-text-secondary">
            {data.rpm_limit ? `${data.rpm_limit}/min` : "—"}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

export function UsageDashboard() {
  const [data, setData] = useState<Record<string, ServiceData> | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const result = await getUsage();
      setData(result as Record<string, ServiceData>);
      setLastUpdated(new Date());
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, []);

  const totalCalls = data
    ? Object.values(data).reduce((sum, s) => sum + s.calls_session, 0)
    : 0;

  const criticalServices = data
    ? Object.values(data).filter((s) => s.daily_pct !== null && s.daily_pct >= 90).length
    : 0;

  return (
    <div className="p-4 flex flex-col gap-4 overflow-y-auto h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-mono font-bold text-text-primary">API Usage Monitor</h2>
          <p className="text-[10px] font-mono text-text-muted mt-0.5">
            {lastUpdated
              ? `Updated ${lastUpdated.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}`
              : "Loading…"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {criticalServices > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-mono text-neon-red border border-neon-red/30 bg-neon-red/10 px-2 py-1 rounded">
              <AlertTriangle className="w-3 h-3" />
              {criticalServices} service{criticalServices > 1 ? "s" : ""} near limit
            </span>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted hover:text-text-primary transition-colors border border-bg-border rounded-lg px-2.5 py-1.5"
          >
            <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary strip */}
      <div className="glass-card rounded-xl px-4 py-3 flex items-center gap-6">
        <div>
          <p className="text-[9px] font-mono text-text-muted uppercase tracking-wider">Total calls this session</p>
          <p className="text-xl font-mono font-bold text-neon-green">{totalCalls.toLocaleString()}</p>
        </div>
        <div className="h-8 w-px bg-bg-border" />
        <div>
          <p className="text-[9px] font-mono text-text-muted uppercase tracking-wider">Services tracked</p>
          <p className="text-xl font-mono font-bold text-text-primary">{data ? Object.keys(data).length : "—"}</p>
        </div>
        <div className="h-8 w-px bg-bg-border" />
        <div className="flex items-start gap-1.5 ml-auto">
          <Info className="w-3 h-3 text-text-muted mt-0.5 shrink-0" />
          <p className="text-[10px] font-mono text-text-muted leading-relaxed max-w-xs">
            Session counts reset on server restart. Daily counts reset at midnight UTC.
            Limits shown are free-tier caps.
          </p>
        </div>
      </div>

      {/* Service grid */}
      {data ? (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(data).map(([id, svc]) => (
            <ServiceCard key={id} id={id} data={svc} />
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center flex-1">
          <div className="flex items-center gap-2 text-text-muted">
            <Activity className="w-4 h-4 animate-pulse" />
            <span className="text-xs font-mono">Loading usage data…</span>
          </div>
        </div>
      )}

      {/* Railway note */}
      <div className="glass-card rounded-xl px-4 py-3 flex items-start gap-2">
        <Info className="w-3.5 h-3.5 text-neon-blue shrink-0 mt-0.5" />
        <p className="text-[10px] font-mono text-text-muted leading-relaxed">
          <span className="text-neon-blue font-semibold">Railway (backend hosting)</span> is the only paid service (~$2–4/mo after free trial).
          Monitor spend at{" "}
          <span className="text-text-secondary">railway.app → your project → Usage tab</span>.
          All other services above are on free tiers with no credit card required.
        </p>
      </div>
    </div>
  );
}
