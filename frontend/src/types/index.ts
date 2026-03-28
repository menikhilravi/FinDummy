// ─────────────────────────────────────────────────────────────────────────────
// Shared TypeScript types
// ─────────────────────────────────────────────────────────────────────────────

export type TradeSide = "BUY" | "SELL";
export type TradeDirection = "LONG" | "SHORT" | "EXIT" | "HOLD";
export type TradingMode = "PAPER" | "LIVE";
export type MarketState = "OPEN" | "EXTENDED" | "CLOSED";

// ── WebSocket event types ─────────────────────────────────────────────────────

export interface MarketStateEvent {
  type: "market_state";
  state: MarketState;
  trading_allowed: boolean;
  timestamp: string;
}

export interface ThoughtEvent {
  type: "thought";
  symbol: string;
  action: TradeDirection;
  confidence: number;
  thought_log: ThoughtLog;
  reasoning: string;
  watchlist_add: string[];
  watchlist_remove: boolean;
  price: number;
  market_state: MarketState;
  trading_allowed: boolean;
  timestamp: string;
}

export interface WatchlistUpdateEvent {
  type: "watchlist_update";
  action: "add" | "remove";
  symbol: string;
  reason?: string;
  timestamp: string;
}

export interface TradeAlertEvent {
  type: "trade_alert";
  symbol: string;
  side: TradeSide;
  direction: TradeDirection;
  qty: number;
  price: number;
  confidence: number;
  reasoning: string;
  order_id: string;
  trading_mode: TradingMode;
  timestamp: string;
}

export interface AccountUpdateEvent {
  type: "account_update";
  data: AccountData;
  timestamp: string;
}

export interface SafetyRejectionEvent {
  type: "safety_rejection";
  symbol: string;
  reason: string;
  message: string;
  timestamp: string;
}

export interface ShutdownEvent {
  type: "shutdown";
  message: string;
}

export interface ErrorEvent {
  type: "error";
  message: string;
  timestamp: string;
}

export type WSEvent =
  | ThoughtEvent
  | TradeAlertEvent
  | AccountUpdateEvent
  | SafetyRejectionEvent
  | WatchlistUpdateEvent
  | MarketStateEvent
  | TAUpdateEvent
  | ShutdownEvent
  | ErrorEvent;

// ── Domain models ─────────────────────────────────────────────────────────────

export interface ThoughtLog {
  price_analysis?: string;
  technical_signals?: string;
  news_sentiment?: string;
  macro_outlook?: string;
  risk_assessment?: string;
  directional_bias?: string;
  final_decision?: string;
  [key: string]: string | undefined;
}

export interface TASignals {
  signals: string[];
  rsi?: number;
  macd_hist?: number;
  vwap?: number;
  vwap_deviation_pct?: number;
  bb_pct?: number;
  volume_ratio?: number;
}

export interface TAUpdateEvent {
  type: "ta_update";
  symbol: string;
  daily: { signals: string[]; momentum?: { rsi: number; macd_hist: number }; volatility?: { bb_pct: number }; volume?: { ratio_vs_avg: number }; error?: string };
  intraday: { signals: string[]; intraday_rsi?: number; vwap?: number; vwap_deviation_pct?: number; volume_ratio?: number; error?: string };
  timestamp: string;
}

export interface AccountData {
  equity: number;
  cash: number;
  buying_power: number;
  portfolio_value: number;
  daytrade_count: number;
}

export interface Position {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  market_value: number;
  side: string;
}

export interface Trade {
  id: string;
  symbol: string;
  side: TradeSide;
  qty: number;
  entry_price: number;
  exit_price?: number;
  pnl?: number;
  confidence: number;
  reasoning?: string;
  trading_mode: TradingMode;
  created_at: string;
  closed_at?: string;
}

export interface WatchlistEntry {
  symbol: string;
  sentiment_score: number;
  last_price: number;
  notes: string;
  updated_at: string;
}

export interface EquitySnapshot {
  equity: number;
  portfolio_value: number;
  created_at: string;
}

// ── UI state ──────────────────────────────────────────────────────────────────

export interface MonologueEntry {
  id: string;
  symbol: string;
  action: TradeAction;
  confidence: number;
  thought_log: ThoughtLog;
  reasoning: string;
  price: number;
  timestamp: string;
}

export interface ToastData {
  id: string;
  type: "trade" | "safety" | "error" | "shutdown";
  title: string;
  description: string;
  side?: TradeSide;
  confidence?: number;
  timestamp: string;
}
