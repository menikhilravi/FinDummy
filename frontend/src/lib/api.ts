import type {
  AccountData,
  EquitySnapshot,
  Position,
  Trade,
  WatchlistEntry,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${path} → ${res.status}: ${err}`);
  }
  return res.json() as Promise<T>;
}

// ── Account ───────────────────────────────────────────────────────────────────

export const getAccount = () => request<AccountData>("/api/v1/account");
export const getPositions = () => request<Position[]>("/api/v1/positions");

// ── Trade history ─────────────────────────────────────────────────────────────

export const getTrades = (limit = 50) =>
  request<Trade[]>(`/api/v1/trades?limit=${limit}`);

// ── Watchlist ─────────────────────────────────────────────────────────────────

export const getWatchlist = () =>
  request<WatchlistEntry[]>("/api/v1/watchlist");

// ── Equity chart ──────────────────────────────────────────────────────────────

export const getEquityHistory = (limit = 200) =>
  request<EquitySnapshot[]>(`/api/v1/equity/history?limit=${limit}`);

// ── Agent control ─────────────────────────────────────────────────────────────

export const startAgent = () =>
  request<{ status: string }>("/api/v1/agent/start", { method: "POST" });

export const stopAgent = () =>
  request<{ status: string }>("/api/v1/agent/stop", { method: "POST" });

export const emergencyShutdown = () =>
  request<{ status: string; message: string }>("/api/v1/shutdown", {
    method: "POST",
  });

// ── Health ─────────────────────────────────────────────────────────────────────

export const getHealth = () =>
  request<{ status: string; trading_mode: string; ws_connections: number }>(
    "/api/v1/health"
  );

export const getSafetyStats = () =>
  request<{ date: string; realised_pnl: number; trade_count: number }>(
    "/api/v1/safety/stats"
  );
