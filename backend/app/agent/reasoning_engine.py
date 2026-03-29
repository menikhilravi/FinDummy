"""
ReasoningEngine — Groq (Llama 3) inference for trade decisions.

The agent is given:
  - Current price bar
  - Recent news + sentiment scores
  - Macro-economic snapshot

It returns a structured JSON decision with a full internal monologue.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from groq import AsyncGroq

from app.core.config import settings
from app.core.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert quantitative trader and portfolio manager.
You will be given real-time market data, news, macro-economic context, and the
current position for a US-listed stock.
Your job is to reason like a professional hedge fund analyst and output a structured
trade decision that can profit in BOTH bull and bear markets.

DIRECTIONAL ACTIONS:
  LONG  — You are bullish. Open or maintain a long position (buy the stock).
  SHORT — You are bearish. Open or maintain a short position (short sell the stock).
  EXIT  — Close any existing position immediately (take profit or cut loss).
  HOLD  — No new trade. Stay flat or maintain current position as-is.

CRITICAL RULES:
- Never risk more than 2% of total portfolio equity on a single trade.
- Prefer HOLD when macro, news, AND technical signals conflict.
- SHORT is valid — use it when bearish catalysts are confirmed by TA (price below VWAP,
  RSI overbought, death cross, MACD bearish cross). Only SHORT if shortable.
- For day trades: VWAP, intraday RSI, and MACD histogram are the primary signals.
- For swing trades: SMA crosses, daily RSI, and Bollinger Band position matter more.
- ATR tells you how volatile the stock is — factor this into position sizing.
- Always cite specific TA signals in your directional_bias reasoning.
- Only suggest US-listed equities (NYSE, NASDAQ, AMEX) for watchlist additions.
- Output ONLY valid JSON — no markdown, no commentary outside the JSON object.

Output format (strictly):
{
  "action": "LONG" | "SHORT" | "EXIT" | "HOLD",
  "confidence": <float 0.0-1.0>,
  "position_size_pct": <float 0.0-0.02>,
  "thought_log": {
    "price_analysis": "<string>",
    "technical_signals": "<key TA signals — RSI, MACD, VWAP, crosses>",
    "news_sentiment": "<string>",
    "macro_outlook": "<string>",
    "risk_assessment": "<string>",
    "directional_bias": "<why LONG or SHORT — cite specific TA + news catalyst>",
    "final_decision": "<string>"
  },
  "reasoning": "<one-sentence summary for the trade alert>",
  "watchlist_add": ["<TICKER>"],
  "watchlist_remove": false
}"""


class ReasoningEngine:
    def __init__(self) -> None:
        self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    async def analyze(
        self,
        symbol: str,
        price_data: dict[str, Any],
        news: list[dict[str, Any]],
        macro: dict[str, Any],
        account: dict[str, Any],
        current_position: dict[str, Any] | None = None,
        shortable: bool = True,
        ta_text: str = "",
    ) -> dict[str, Any]:
        user_message = self._build_prompt(
            symbol, price_data, news, macro, account,
            current_position, shortable, ta_text,
        )

        try:
            response = await self._client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            usage_tracker.increment("groq")
            raw = response.choices[0].message.content or "{}"
            decision = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Groq returned non-JSON for %s: %s", symbol, exc)
            decision = self._default_hold(symbol, "JSON parse error from LLM")
        except Exception as exc:
            logger.error("Groq API error for %s: %s", symbol, exc)
            decision = self._default_hold(symbol, str(exc))

        # Normalise & validate
        decision = self._validate(decision, symbol)
        logger.info(
            "[%s] Decision: %s (conf=%.2f)",
            symbol, decision["action"], decision["confidence"],
        )
        return decision

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_prompt(
        self,
        symbol: str,
        price_data: dict,
        news: list[dict],
        macro: dict,
        account: dict,
        current_position: dict | None,
        shortable: bool,
        ta_text: str,
    ) -> str:
        news_summary = "\n".join(
            f"  [{n.get('sentiment_score', 0):+.2f}] {n.get('headline', '')}"
            for n in news[:5]
        ) or "  No recent news available."

        macro_summary = json.dumps(
            {
                k: v.get("latest", {}) if isinstance(v, dict) else v
                for k, v in macro.items()
            },
            indent=2,
        )

        if current_position:
            pos_summary = (
                f"  Side:          {current_position.get('side', 'N/A').upper()}\n"
                f"  Qty:           {current_position.get('qty', 0)}\n"
                f"  Avg Entry:     ${current_position.get('avg_entry_price', 0):.2f}\n"
                f"  Unrealised PnL: ${current_position.get('unrealized_pl', 0):.2f} "
                f"({float(current_position.get('unrealized_plpc', 0)) * 100:.2f}%)"
            )
        else:
            pos_summary = "  No open position (FLAT)"

        return f"""=== ANALYSIS REQUEST: {symbol} ===

CURRENT PRICE BAR:
  Open:   ${price_data.get('open', 0):.2f}
  High:   ${price_data.get('high', 0):.2f}
  Low:    ${price_data.get('low', 0):.2f}
  Close:  ${price_data.get('close', 0):.2f}
  Volume: {price_data.get('volume', 0):,}

CURRENT POSITION:
{pos_summary}

STOCK PROPERTIES:
  Shortable: {'YES — SHORT action is available' if shortable else 'NO — only LONG or HOLD'}

ACCOUNT:
  Total Equity:  ${account.get('equity', 0):,.2f}
  Cash:          ${account.get('cash', 0):,.2f}
  Buying Power:  ${account.get('buying_power', 0):,.2f}

TECHNICAL ANALYSIS:
{ta_text if ta_text else '  Not available this cycle.'}

RECENT NEWS (sentiment score in brackets, -1=bearish, +1=bullish):
{news_summary}

MACRO-ECONOMIC SNAPSHOT:
{macro_summary}

Based on ALL data above — especially TA signals — provide your structured trade decision as JSON.
LONG to profit from rising price. SHORT to profit from falling price."""

    def _validate(self, d: dict, symbol: str) -> dict:
        valid_actions = {"LONG", "SHORT", "EXIT", "HOLD"}
        action = str(d.get("action", "HOLD")).upper()
        if action not in valid_actions:
            action = "HOLD"

        confidence = float(d.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        position_size_pct = float(d.get("position_size_pct", 0.01))
        position_size_pct = max(0.0, min(settings.MAX_POSITION_SIZE_PCT, position_size_pct))

        thought_log = d.get("thought_log", {})
        if not isinstance(thought_log, dict):
            thought_log = {"final_decision": str(thought_log)}

        # Watchlist suggestions — only allow clean uppercase ticker strings
        raw_add = d.get("watchlist_add", [])
        watchlist_add = [
            t.upper().strip()
            for t in (raw_add if isinstance(raw_add, list) else [])
            if isinstance(t, str) and t.strip().isalpha() and 1 <= len(t.strip()) <= 5
        ][:3]

        watchlist_remove = bool(d.get("watchlist_remove", False))

        return {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "position_size_pct": position_size_pct,
            "thought_log": thought_log,
            "reasoning": str(d.get("reasoning", "No reasoning provided.")),
            "watchlist_add": watchlist_add,
            "watchlist_remove": watchlist_remove,
        }

    @staticmethod
    def _default_hold(symbol: str, reason: str) -> dict:
        return {
            "symbol": symbol,
            "action": "HOLD",
            "confidence": 0.0,
            "position_size_pct": 0.0,
            "thought_log": {
                "price_analysis": "N/A",
                "news_sentiment": "N/A",
                "macro_outlook": "N/A",
                "risk_assessment": "N/A",
                "final_decision": f"Defaulting to HOLD due to error: {reason}",
            },
            "reasoning": f"Defaulting to HOLD: {reason}",
        }


reasoning_engine = ReasoningEngine()
