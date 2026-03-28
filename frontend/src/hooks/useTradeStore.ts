"use client";

import { create } from "zustand";
import type {
  AccountData,
  MarketState,
  MonologueEntry,
  ToastData,
  TradeAlertEvent,
  WatchlistEntry,
  WSEvent,
} from "@/types";
import { generateId } from "@/lib/utils";

const MAX_MONOLOGUE = 100;
const MAX_TOASTS = 5;

interface TradeStore {
  // Connection
  wsStatus: "connecting" | "connected" | "disconnected" | "error";
  setWsStatus: (s: TradeStore["wsStatus"]) => void;

  // Account
  account: AccountData | null;
  setAccount: (a: AccountData) => void;

  // Monologue feed
  monologue: MonologueEntry[];
  addMonologue: (entry: MonologueEntry) => void;

  // Trade toasts
  toasts: ToastData[];
  addToast: (t: ToastData) => void;
  dismissToast: (id: string) => void;

  // Watchlist (live, updated by WS thought events)
  watchlist: WatchlistEntry[];
  setWatchlist: (wl: WatchlistEntry[]) => void;
  updateWatchlistEntry: (symbol: string, price: number, sentiment: number, notes: string) => void;

  // Recent trades
  recentTrades: TradeAlertEvent[];
  addTrade: (t: TradeAlertEvent) => void;

  // Agent status
  isAgentRunning: boolean;
  setAgentRunning: (v: boolean) => void;

  // Market state
  marketState: MarketState;
  tradingAllowed: boolean;
  setMarketState: (s: MarketState, allowed: boolean) => void;

  // Dispatch WS event
  handleWsEvent: (event: WSEvent) => void;
}

export const useTradeStore = create<TradeStore>((set, get) => ({
  wsStatus: "disconnected",
  setWsStatus: (s) => set({ wsStatus: s }),

  account: null,
  setAccount: (account) => set({ account }),

  monologue: [],
  addMonologue: (entry) =>
    set((state) => ({
      monologue: [entry, ...state.monologue].slice(0, MAX_MONOLOGUE),
    })),

  toasts: [],
  addToast: (t) =>
    set((state) => ({
      toasts: [t, ...state.toasts].slice(0, MAX_TOASTS),
    })),
  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  watchlist: [],
  setWatchlist: (watchlist) => set({ watchlist }),
  updateWatchlistEntry: (symbol, price, sentiment, notes) =>
    set((state) => {
      const existing = state.watchlist.find((w) => w.symbol === symbol);
      if (existing) {
        return {
          watchlist: state.watchlist.map((w) =>
            w.symbol === symbol
              ? { ...w, last_price: price, sentiment_score: sentiment, notes, updated_at: new Date().toISOString() }
              : w
          ),
        };
      }
      return {
        watchlist: [
          ...state.watchlist,
          { symbol, last_price: price, sentiment_score: sentiment, notes, updated_at: new Date().toISOString() },
        ],
      };
    }),

  recentTrades: [],
  addTrade: (t) =>
    set((state) => ({
      recentTrades: [t, ...state.recentTrades].slice(0, 50),
    })),

  isAgentRunning: true,
  setAgentRunning: (v) => set({ isAgentRunning: v }),

  marketState: "CLOSED",
  tradingAllowed: false,
  setMarketState: (marketState, tradingAllowed) => set({ marketState, tradingAllowed }),

  handleWsEvent: (event) => {
    const store = get();
    switch (event.type) {
      case "thought":
        store.addMonologue({
          id: generateId(),
          symbol: event.symbol,
          action: event.action,
          confidence: event.confidence,
          thought_log: event.thought_log,
          reasoning: event.reasoning,
          price: event.price,
          timestamp: event.timestamp,
        });
        store.updateWatchlistEntry(
          event.symbol,
          event.price,
          0,
          event.reasoning
        );
        break;

      case "trade_alert":
        store.addTrade(event);
        store.addToast({
          id: generateId(),
          type: "trade",
          title: `${event.side} ${event.symbol}`,
          description: `${event.qty.toFixed(4)} @ $${event.price.toFixed(2)} · ${(event.confidence * 100).toFixed(0)}% confidence`,
          side: event.side,
          confidence: event.confidence,
          timestamp: event.timestamp,
        });
        break;

      case "account_update":
        store.setAccount(event.data);
        break;

      case "safety_rejection":
        store.addToast({
          id: generateId(),
          type: "safety",
          title: `Safety Block: ${event.symbol}`,
          description: event.message,
          timestamp: new Date().toISOString(),
        });
        break;

      case "market_state":
        store.setMarketState(event.state, event.trading_allowed);
        break;

      case "watchlist_update":
        if (event.action === "add") {
          store.updateWatchlistEntry(event.symbol, 0, 0, "Auto-added by agent");
        } else {
          set((state) => ({
            watchlist: state.watchlist.filter((w) => w.symbol !== event.symbol),
          }));
        }
        store.addToast({
          id: generateId(),
          type: "safety",
          title: `Watchlist ${event.action === "add" ? "▲ Added" : "▼ Removed"}`,
          description: `${event.symbol}${event.reason ? ` — ${event.reason}` : ""}`,
          timestamp: event.timestamp,
        });
        break;

      case "shutdown":
        store.setAgentRunning(false);
        store.addToast({
          id: generateId(),
          type: "shutdown",
          title: "Emergency Shutdown",
          description: event.message,
          timestamp: new Date().toISOString(),
        });
        break;

      case "error":
        store.addToast({
          id: generateId(),
          type: "error",
          title: "Agent Error",
          description: event.message,
          timestamp: event.timestamp,
        });
        break;
    }
  },
}));
