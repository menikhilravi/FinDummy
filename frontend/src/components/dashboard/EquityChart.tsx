"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import { TrendingUp, RefreshCw } from "lucide-react";
import { useTradeStore } from "@/hooks/useTradeStore";
import { formatCurrency } from "@/lib/utils";
import { getEquityHistory } from "@/lib/api";
import type { EquitySnapshot } from "@/types";
import { cn } from "@/lib/utils";

type Range = "1D" | "1W" | "1M" | "ALL";

const RANGE_SECONDS: Record<Range, number> = {
  "1D":  86_400,
  "1W":  7  * 86_400,
  "1M":  30 * 86_400,
  "ALL": Infinity,
};

export function EquityChart() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  const account = useTradeStore((s) => s.account);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<EquitySnapshot[]>([]);
  const [range, setRange] = useState<Range>("ALL");

  // Tooltip state
  const [tooltip, setTooltip] = useState<{
    visible: boolean;
    x: number;
    y: number;
    value: string;
    time: string;
  }>({ visible: false, x: 0, y: 0, value: "", time: "" });

  // Load historical data
  useEffect(() => {
    getEquityHistory(500)
      .then((data) => {
        setHistory(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Initialise chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#475569",
        fontFamily: "JetBrains Mono, monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1f2937", style: LineStyle.Dotted },
        horzLines: { color: "#1f2937", style: LineStyle.Dotted },
      },
      crosshair: {
        vertLine: { color: "#00ff88", width: 1, style: LineStyle.Dashed },
        horzLine: { color: "#00ff88", width: 1, style: LineStyle.Dashed },
      },
      rightPriceScale: {
        borderColor: "#1f2937",
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: "#1f2937",
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });

    const areaSeries = chart.addAreaSeries({
      lineColor: "#00ff88",
      topColor: "rgba(0, 255, 136, 0.3)",
      bottomColor: "rgba(0, 255, 136, 0.0)",
      lineWidth: 2,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });

    // Crosshair tooltip
    chart.subscribeCrosshairMove((param) => {
      if (!chartContainerRef.current) return;

      if (!param.point || !param.time || param.point.x < 0 || param.point.y < 0) {
        setTooltip((t) => ({ ...t, visible: false }));
        return;
      }

      const data = param.seriesData.get(areaSeries) as { value?: number } | undefined;
      if (!data?.value) {
        setTooltip((t) => ({ ...t, visible: false }));
        return;
      }

      const ts = typeof param.time === "number" ? param.time * 1000 : Date.now();
      const timeStr = new Date(ts).toLocaleString([], {
        month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      });

      const containerRect = chartContainerRef.current.getBoundingClientRect();
      // Flip tooltip to left side if near right edge
      const flipX = param.point.x > containerRect.width * 0.65;

      setTooltip({
        visible: true,
        x: flipX ? param.point.x - 140 : param.point.x + 12,
        y: Math.max(4, param.point.y - 36),
        value: formatCurrency(data.value),
        time: timeStr,
      });
    });

    chartRef.current = chart;
    seriesRef.current = areaSeries;

    const observer = new ResizeObserver(() => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    });
    observer.observe(chartContainerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, []);

  // Filter + populate data when history or range changes
  useEffect(() => {
    if (!seriesRef.current || history.length === 0) return;

    const cutoff = range === "ALL"
      ? 0
      : Date.now() / 1000 - RANGE_SECONDS[range];

    const points = history
      .map((s) => ({
        time: Math.floor(new Date(s.created_at).getTime() / 1000) as any,
        value: s.equity,
      }))
      .filter((p) => p.time >= cutoff)
      .sort((a, b) => a.time - b.time);

    // Deduplicate timestamps (lightweight-charts requires unique times)
    const seen = new Set<number>();
    const unique = points.filter((p) => {
      if (seen.has(p.time)) return false;
      seen.add(p.time);
      return true;
    });

    seriesRef.current.setData(unique);
    chartRef.current?.timeScale().fitContent();
  }, [history, range]);

  // Stream live equity updates
  useEffect(() => {
    if (!seriesRef.current || !account) return;
    seriesRef.current.update({
      time: Math.floor(Date.now() / 1000) as any,
      value: account.equity,
    });
  }, [account?.equity]);

  const equity = account?.equity ?? 0;
  const prevEquity = history.length > 1 ? history[history.length - 2]?.equity ?? equity : equity;
  const change = equity - prevEquity;
  const changePct = prevEquity > 0 ? (change / prevEquity) * 100 : 0;
  const isPositive = change >= 0;

  return (
    <div className="flex flex-col h-full glass-card rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between px-4 py-3 border-b border-bg-border">
        <div>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-neon-green" />
            <span className="text-xs font-mono font-semibold text-text-secondary uppercase tracking-widest">
              Total Equity
            </span>
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-mono font-bold text-text-primary">
              {formatCurrency(equity)}
            </span>
            <span className={`text-sm font-mono font-semibold ${isPositive ? "text-neon-green" : "text-neon-red"}`}>
              {isPositive ? "+" : ""}{formatCurrency(change)} ({isPositive ? "+" : ""}{changePct.toFixed(2)}%)
            </span>
          </div>
        </div>

        <div className="flex flex-col items-end gap-1.5">
          {/* Range selector */}
          <div className="flex items-center gap-1">
            {(["1D", "1W", "1M", "ALL"] as Range[]).map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={cn(
                  "px-2 py-0.5 text-[10px] font-mono rounded transition-colors",
                  range === r
                    ? "bg-neon-green/20 text-neon-green border border-neon-green/40"
                    : "text-text-muted hover:text-text-secondary border border-transparent"
                )}
              >
                {r}
              </button>
            ))}
          </div>
          <div className="text-right text-[11px] font-mono text-text-muted space-y-0.5">
            <div>Cash: <span className="text-text-secondary">{formatCurrency(account?.cash ?? 0)}</span></div>
            <div>BP: <span className="text-text-secondary">{formatCurrency(account?.buying_power ?? 0)}</span></div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 relative p-2">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <RefreshCw className="w-5 h-5 text-neon-green animate-spin" />
          </div>
        )}
        <div ref={chartContainerRef} className="w-full h-full" />

        {/* Crosshair tooltip */}
        {tooltip.visible && (
          <div
            className="absolute pointer-events-none z-20 px-2 py-1.5 rounded-lg border border-neon-green/40 bg-bg-base/90 backdrop-blur-sm"
            style={{ left: tooltip.x, top: tooltip.y }}
          >
            <div className="text-[11px] font-mono font-bold text-neon-green">{tooltip.value}</div>
            <div className="text-[10px] font-mono text-text-muted">{tooltip.time}</div>
          </div>
        )}
      </div>
    </div>
  );
}
