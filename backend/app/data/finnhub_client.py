"""
Finnhub client — real-time company news + basic sentiment scoring.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import finnhub

from app.core.config import settings
from app.core.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)

# Very simple word-list sentiment (avoids any extra ML dependencies)
_POSITIVE_WORDS = {
    "beat", "surpass", "record", "growth", "profit", "upgrade", "buy",
    "strong", "bullish", "positive", "rise", "soar", "gain", "rally",
    "outperform", "expansion", "innovation", "breakthrough",
}
_NEGATIVE_WORDS = {
    "miss", "loss", "decline", "downgrade", "sell", "weak", "bearish",
    "negative", "fall", "drop", "crash", "concern", "risk", "cut",
    "underperform", "recession", "layoff", "fraud", "investigation",
}


def _simple_sentiment(text: str) -> float:
    """Returns score in [-1, 1]; 0 = neutral."""
    words = text.lower().split()
    pos = sum(1 for w in words if w in _POSITIVE_WORDS)
    neg = sum(1 for w in words if w in _NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


class FinnhubClient:
    def __init__(self) -> None:
        self._client = finnhub.Client(api_key=settings.FINNHUB_API_KEY)

    async def get_company_news(
        self, symbol: str, days: int = 3
    ) -> list[dict[str, Any]]:
        to_date = datetime.now(timezone.utc)
        from_date = to_date - timedelta(days=days)
        usage_tracker.increment("finnhub")
        raw = await asyncio.to_thread(
            self._client.company_news,
            symbol,
            _from=from_date.strftime("%Y-%m-%d"),
            to=to_date.strftime("%Y-%m-%d"),
        )
        articles = []
        for item in (raw or [])[:10]:          # cap at 10
            headline = item.get("headline", "")
            summary = item.get("summary", "")
            full_text = f"{headline} {summary}"
            sentiment = _simple_sentiment(full_text)
            articles.append(
                {
                    "headline": headline,
                    "summary": summary[:300],
                    "source": item.get("source", ""),
                    "url": item.get("url", ""),
                    "datetime": item.get("datetime", 0),
                    "sentiment_score": round(sentiment, 3),
                }
            )
        return articles

    async def get_aggregate_sentiment(self, symbol: str) -> dict[str, Any]:
        """Returns averaged sentiment + article count for a symbol."""
        articles = await self.get_company_news(symbol)
        if not articles:
            return {"symbol": symbol, "score": 0.0, "article_count": 0}
        avg = sum(a["sentiment_score"] for a in articles) / len(articles)
        return {
            "symbol": symbol,
            "score": round(avg, 3),
            "article_count": len(articles),
            "articles": articles,
        }

    async def get_market_news(self) -> list[dict[str, Any]]:
        usage_tracker.increment("finnhub")
        raw = await asyncio.to_thread(self._client.general_news, "general")
        news = []
        for item in (raw or [])[:8]:
            headline = item.get("headline", "")
            news.append(
                {
                    "headline": headline,
                    "source": item.get("source", ""),
                    "url": item.get("url", ""),
                    "datetime": item.get("datetime", 0),
                    "sentiment_score": round(_simple_sentiment(headline), 3),
                }
            )
        return news


finnhub_client = FinnhubClient()
