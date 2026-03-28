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

export function EquityChart() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  const account = useTradeStore((s) => s.account);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<EquitySnapshot[]>([]);

  // Load historical data
  useEffect(() => {
    getEquityHistory(200)
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

  // Populate historical data
  useEffect(() => {
    if (!seriesRef.current || history.length === 0) return;
    const points = history
      .map((s) => ({
        time: Math.floor(new Date(s.created_at).getTime() / 1000) as any,
        value: s.equity,
      }))
      .sort((a, b) => a.time - b.time);
    seriesRef.current.setData(points);
    chartRef.current?.timeScale().fitContent();
  }, [history]);

  // Stream live equity updates from account
  useEffect(() => {
    if (!seriesRef.current || !account) return;
    const point = {
      time: Math.floor(Date.now() / 1000) as any,
      value: account.equity,
    };
    seriesRef.current.update(point);
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
            <span
              className={`text-sm font-mono font-semibold ${
                isPositive ? "text-neon-green" : "text-neon-red"
              }`}
            >
              {isPositive ? "+" : ""}
              {formatCurrency(change)} ({isPositive ? "+" : ""}
              {changePct.toFixed(2)}%)
            </span>
          </div>
        </div>

        <div className="text-right text-[11px] font-mono text-text-muted space-y-0.5">
          <div>
            Cash:{" "}
            <span className="text-text-secondary">
              {formatCurrency(account?.cash ?? 0)}
            </span>
          </div>
          <div>
            BP:{" "}
            <span className="text-text-secondary">
              {formatCurrency(account?.buying_power ?? 0)}
            </span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 relative p-2">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <RefreshCw className="w-5 h-5 text-neon-green animate-spin" />
          </div>
        )}
        <div ref={chartContainerRef} className="w-full h-full" />
      </div>
    </div>
  );
}
