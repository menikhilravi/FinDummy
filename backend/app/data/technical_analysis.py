"""
TechnicalAnalysis — multi-timeframe indicator engine.

Computed purely with pandas/numpy (already installed via alpaca-py).
No extra dependencies.

Timeframes:
  DAILY   (50 bars)  — trend, SMA/EMA crosses, daily RSI, MACD, Bollinger
  INTRA   (15-min, 2 days) — VWAP, intraday RSI, intraday momentum
  MICRO   (1-min, today)   — latest price action, volume spike detection

Output is a compact structured dict → converted to LLM-readable text.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ── Indicator helpers (pure pandas, no extra libs) ────────────────────────────

def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _macd(series: pd.Series, fast=12, slow=26, signal=9) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def _bollinger(series: pd.Series, period=20, std_dev=2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = _sma(series, period)
    std = series.rolling(window=period, min_periods=period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower

def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def _vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical_price = (high + low + close) / 3
    cumulative_tp_vol = (typical_price * volume).cumsum()
    cumulative_vol = volume.cumsum()
    return cumulative_tp_vol / cumulative_vol.replace(0, np.nan)

def _stoch(high: pd.Series, low: pd.Series, close: pd.Series, k=14, d=3) -> tuple[pd.Series, pd.Series]:
    lowest_low = low.rolling(window=k, min_periods=k).min()
    highest_high = high.rolling(window=k, min_periods=k).max()
    k_pct = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d_pct = k_pct.rolling(window=d).mean()
    return k_pct, d_pct


# ── Main engine ───────────────────────────────────────────────────────────────

class TechnicalAnalysis:

    def compute_daily(self, bars: list[dict]) -> dict[str, Any]:
        """
        Full daily indicator suite from daily OHLCV bars (needs ≥ 50 bars).
        """
        if len(bars) < 10:
            return {"error": "Insufficient daily bars"}

        df = self._to_df(bars)
        close = df["close"]
        high  = df["high"]
        low   = df["low"]
        vol   = df["volume"]

        # Trend
        sma20  = _sma(close, 20).iloc[-1]
        sma50  = _sma(close, 50).iloc[-1] if len(df) >= 50 else None
        ema9   = _ema(close, 9).iloc[-1]
        ema21  = _ema(close, 21).iloc[-1]
        price  = close.iloc[-1]

        # Momentum
        rsi    = _rsi(close).iloc[-1]
        macd_l, macd_s, macd_h = _macd(close)
        macd_val  = macd_l.iloc[-1]
        macd_sig  = macd_s.iloc[-1]
        macd_hist = macd_h.iloc[-1]
        macd_hist_prev = macd_h.iloc[-2] if len(macd_h) > 1 else 0

        # Volatility
        bb_upper, bb_mid, bb_lower = _bollinger(close)
        bb_u  = bb_upper.iloc[-1]
        bb_l  = bb_lower.iloc[-1]
        bb_b  = bb_mid.iloc[-1]
        atr   = _atr(high, low, close).iloc[-1]
        bb_pct = (price - bb_l) / (bb_u - bb_l) if (bb_u - bb_l) > 0 else 0.5

        # Volume
        vol_avg20 = vol.rolling(20).mean().iloc[-1]
        vol_ratio = vol.iloc[-1] / vol_avg20 if vol_avg20 > 0 else 1.0

        # Stochastic
        stoch_k, stoch_d = _stoch(high, low, close)
        sk = stoch_k.iloc[-1]
        sd = stoch_d.iloc[-1]

        # Derived signals
        signals: list[str] = []
        if sma50 is not None:
            if price > sma20 > sma50:
                signals.append("BULLISH: price above SMA20 > SMA50 (uptrend)")
            elif price < sma20 < sma50:
                signals.append("BEARISH: price below SMA20 < SMA50 (downtrend)")
            # Golden/death cross
            sma20_prev = _sma(close, 20).iloc[-2] if len(df) > 1 else sma20
            sma50_prev = _sma(close, 50).iloc[-2] if len(df) > 1 else sma50
            if sma20 > sma50 and sma20_prev <= sma50_prev:
                signals.append("GOLDEN CROSS: SMA20 crossed above SMA50 — strong bull signal")
            elif sma20 < sma50 and sma20_prev >= sma50_prev:
                signals.append("DEATH CROSS: SMA20 crossed below SMA50 — strong bear signal")

        if rsi > 70:
            signals.append(f"RSI OVERBOUGHT ({rsi:.1f}) — potential reversal or short opportunity")
        elif rsi < 30:
            signals.append(f"RSI OVERSOLD ({rsi:.1f}) — potential reversal or long opportunity")

        if macd_hist > 0 and macd_hist_prev <= 0:
            signals.append("MACD BULLISH CROSSOVER — momentum turning positive")
        elif macd_hist < 0 and macd_hist_prev >= 0:
            signals.append("MACD BEARISH CROSSOVER — momentum turning negative")

        if bb_pct > 0.95:
            signals.append("PRICE AT UPPER BOLLINGER BAND — overbought / breakout watch")
        elif bb_pct < 0.05:
            signals.append("PRICE AT LOWER BOLLINGER BAND — oversold / breakdown watch")

        if vol_ratio > 2.0:
            signals.append(f"VOLUME SPIKE: {vol_ratio:.1f}x average — strong conviction move")

        if not signals:
            signals.append("No strong signals — market consolidating")

        return {
            "timeframe": "DAILY",
            "price": round(price, 2),
            "trend": {
                "sma20":  round(sma20, 2),
                "sma50":  round(sma50, 2) if sma50 else None,
                "ema9":   round(ema9, 2),
                "ema21":  round(ema21, 2),
                "price_vs_sma20": f"{((price/sma20)-1)*100:+.2f}%",
            },
            "momentum": {
                "rsi":          round(rsi, 1),
                "macd":         round(macd_val, 4),
                "macd_signal":  round(macd_sig, 4),
                "macd_hist":    round(macd_hist, 4),
                "stoch_k":      round(sk, 1) if not np.isnan(sk) else None,
                "stoch_d":      round(sd, 1) if not np.isnan(sd) else None,
            },
            "volatility": {
                "atr":       round(atr, 2),
                "bb_upper":  round(bb_u, 2),
                "bb_lower":  round(bb_l, 2),
                "bb_pct":    round(bb_pct * 100, 1),
                "atr_pct":   round((atr / price) * 100, 2),
            },
            "volume": {
                "ratio_vs_avg": round(vol_ratio, 2),
            },
            "signals": signals,
        }

    def compute_intraday(self, bars: list[dict], timeframe: str = "15Min") -> dict[str, Any]:
        """
        Intraday indicators from sub-daily bars.
        Primary use: VWAP, intraday RSI, intraday momentum for day trading.
        """
        if len(bars) < 5:
            return {"error": "Insufficient intraday bars"}

        df = self._to_df(bars)
        close = df["close"]
        high  = df["high"]
        low   = df["low"]
        vol   = df["volume"]

        price = close.iloc[-1]
        vwap  = _vwap(high, low, close, vol).iloc[-1]
        rsi   = _rsi(close, period=min(14, len(df)-1)).iloc[-1]
        ema9  = _ema(close, 9).iloc[-1]

        macd_l, macd_s, macd_h = _macd(close)
        macd_hist      = macd_h.iloc[-1]
        macd_hist_prev = macd_h.iloc[-2] if len(macd_h) > 1 else 0

        # VWAP deviation
        vwap_dev = ((price - vwap) / vwap) * 100 if vwap > 0 else 0

        # Volume profile: last bar vs session average
        vol_avg  = vol.mean()
        vol_last = vol.iloc[-1]
        vol_ratio = vol_last / vol_avg if vol_avg > 0 else 1.0

        # Intraday trend: last N bars slope
        n = min(10, len(close))
        slope = (close.iloc[-1] - close.iloc[-n]) / n if n > 1 else 0

        signals: list[str] = []
        if price > vwap:
            signals.append(f"PRICE ABOVE VWAP (+{vwap_dev:.2f}%) — intraday bullish bias")
        else:
            signals.append(f"PRICE BELOW VWAP ({vwap_dev:.2f}%) — intraday bearish bias")

        if not np.isnan(rsi):
            if rsi > 70:
                signals.append(f"INTRADAY RSI OVERBOUGHT ({rsi:.1f})")
            elif rsi < 30:
                signals.append(f"INTRADAY RSI OVERSOLD ({rsi:.1f})")

        if macd_hist > 0 and macd_hist_prev <= 0:
            signals.append("INTRADAY MACD BULLISH CROSS")
        elif macd_hist < 0 and macd_hist_prev >= 0:
            signals.append("INTRADAY MACD BEARISH CROSS")

        if vol_ratio > 1.5:
            signals.append(f"HIGH INTRADAY VOLUME ({vol_ratio:.1f}x avg) — strong move likely")

        return {
            "timeframe": timeframe,
            "price": round(price, 2),
            "vwap":  round(vwap, 2),
            "vwap_deviation_pct": round(vwap_dev, 2),
            "intraday_rsi": round(rsi, 1) if not np.isnan(rsi) else None,
            "ema9":  round(ema9, 2),
            "macd_hist": round(macd_hist, 4),
            "volume_ratio": round(vol_ratio, 2),
            "price_slope_10bar": round(slope, 4),
            "signals": signals,
        }

    def to_llm_text(self, daily: dict, intraday: dict) -> str:
        """Converts TA dicts into a compact, token-efficient text block for the LLM."""
        lines: list[str] = []

        if "error" not in daily:
            t = daily["trend"]
            m = daily["momentum"]
            v = daily["volatility"]
            lines += [
                "── DAILY TECHNICALS ──",
                f"Price: ${daily['price']}  SMA20: ${t['sma20']} ({t['price_vs_sma20']})  SMA50: ${t.get('sma50','N/A')}  EMA9: ${t['ema9']}",
                f"RSI: {m['rsi']}  MACD hist: {m['macd_hist']}  Stoch K/D: {m.get('stoch_k','?')}/{m.get('stoch_d','?')}",
                f"BB%: {v['bb_pct']}%  ATR: ${v['atr']} ({v['atr_pct']}% of price)  Vol ratio: {daily['volume']['ratio_vs_avg']}x",
                "Signals: " + " | ".join(daily["signals"]),
            ]
        else:
            lines.append(f"Daily TA unavailable: {daily.get('error')}")

        lines.append("")

        if "error" not in intraday:
            lines += [
                f"── INTRADAY ({intraday['timeframe']}) ──",
                f"Price: ${intraday['price']}  VWAP: ${intraday['vwap']} ({intraday['vwap_deviation_pct']:+.2f}%)",
                f"Intraday RSI: {intraday.get('intraday_rsi','N/A')}  MACD hist: {intraday['macd_hist']}  Vol: {intraday['volume_ratio']}x avg",
                "Signals: " + " | ".join(intraday["signals"]),
            ]
        else:
            lines.append(f"Intraday TA unavailable: {intraday.get('error')}")

        return "\n".join(lines)

    @staticmethod
    def _to_df(bars: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(bars)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "time" in df.columns:
            df.index = pd.to_datetime(df["time"])
        return df.sort_index()


technical_analysis = TechnicalAnalysis()
