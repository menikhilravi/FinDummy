"""
GeminiClient — finance-only AI chat using Google Gemini (free tier).

Guardrail strategy:
  1. System prompt hard-restricts the model to finance topics.
  2. The model is instructed to respond with OFF_TOPIC_MARKER for anything
     outside finance — detected server-side and returned as a 400.
  3. A lightweight keyword pre-screen catches obvious off-topic prompts
     before spending an API call.

Model: gemini-2.0-flash  (free tier, 15 RPM / 1M TPD)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

OFF_TOPIC_MARKER = "OFF_TOPIC_QUERY"

_SYSTEM_PROMPT = f"""You are NeuroTrader AI, an expert financial analyst and trading assistant
embedded inside a live algorithmic trading dashboard.

YOUR DOMAIN — you may ONLY discuss:
  • Stock markets, equities, ETFs, indices, futures, options, crypto (market-related)
  • Technical analysis: indicators, chart patterns, price action
  • Fundamental analysis: earnings, valuation, financial ratios, balance sheets
  • Macroeconomics: Fed policy, inflation, GDP, yield curves, sector rotation
  • Trading strategies: momentum, mean reversion, pairs trading, risk management
  • Portfolio management: diversification, position sizing, hedging
  • Financial news and its market impact
  • Specific tickers: price levels, catalysts, analyst ratings

STRICT REFUSAL — if a question is NOT about the above topics, respond with exactly
this single token and nothing else: {OFF_TOPIC_MARKER}

STYLE:
  • Be concise, data-driven, and direct — like a seasoned trader on a desk
  • Use markdown: **bold** for key numbers, `ticker` for symbols, bullet points
  • When discussing a ticker, always mention: trend bias, key level to watch, risk
  • Never give personal financial advice disclaimers — the user knows this is for
    educational/paper trading purposes"""

# Keywords that strongly suggest non-finance topics — fast pre-screen
_OFF_TOPIC_KEYWORDS = {
    "recipe", "cook", "weather", "sport", "music", "movie", "game",
    "travel", "hotel", "flight", "joke", "poem", "story", "history",
    "science", "physics", "chemistry", "biology", "math homework",
    "relationship", "medical", "health", "diet", "workout", "fitness",
    "politics", "religion", "philosophy",
}


class GeminiClient:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def chat(
        self,
        message: str,
        history: list[dict[str, str]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send a message and get a response.

        Args:
            message:  Latest user message.
            history:  List of {"role": "user"|"model", "content": "..."} dicts.
            context:  Optional live dashboard context (watchlist, account).

        Returns:
            {"reply": str, "off_topic": bool}
        """
        # ── Pre-screen ────────────────────────────────────────────────────────
        if self._is_obviously_off_topic(message):
            return {
                "reply": "I'm only able to help with finance and stock market questions.",
                "off_topic": True,
            }

        # ── Build contents ────────────────────────────────────────────────────
        contents = self._build_contents(message, history, context)

        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )
            reply = response.text or ""
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            raise

        # ── Off-topic check ───────────────────────────────────────────────────
        if OFF_TOPIC_MARKER in reply:
            return {
                "reply": "I can only help with finance and stock market questions.",
                "off_topic": True,
            }

        return {"reply": reply.strip(), "off_topic": False}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_contents(
        self,
        message: str,
        history: list[dict[str, str]],
        context: dict[str, Any] | None,
    ) -> list[types.Content]:
        contents: list[types.Content] = []

        # Inject live dashboard context as the first user turn (if provided)
        if context:
            ctx_lines = ["[LIVE DASHBOARD CONTEXT]"]
            account = context.get("account")
            if account:
                ctx_lines.append(
                    f"Portfolio equity: ${account.get('equity', 0):,.2f}  "
                    f"Cash: ${account.get('cash', 0):,.2f}  "
                    f"Buying power: ${account.get('buying_power', 0):,.2f}"
                )
            watchlist = context.get("watchlist", [])
            if watchlist:
                tickers = ", ".join(
                    f"`{w['symbol']}` ${w.get('last_price', 0):.2f} "
                    f"(sent={w.get('sentiment_score', 0):+.2f})"
                    for w in watchlist[:10]
                )
                ctx_lines.append(f"Active watchlist: {tickers}")
            ctx_text = "\n".join(ctx_lines)
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=ctx_text)],
                )
            )
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part(text="Got it. I have your live portfolio context.")],
                )
            )

        # Prior conversation history
        for turn in history[-20:]:        # cap at last 20 turns
            role = "user" if turn["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=turn["content"])],
                )
            )

        # Current message
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=message)],
            )
        )
        return contents

    @staticmethod
    def _is_obviously_off_topic(message: str) -> bool:
        lower = message.lower()
        return any(kw in lower for kw in _OFF_TOPIC_KEYWORDS)


gemini_client = GeminiClient()
