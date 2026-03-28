from pydantic_settings import BaseSettings
from typing import Literal
import json


class Settings(BaseSettings):
    # ── Trading Mode ─────────────────────────────────────────────────────────
    TRADING_MODE: Literal["PAPER", "LIVE"] = "PAPER"

    # ── Alpaca ────────────────────────────────────────────────────────────────
    ALPACA_API_KEY: str
    ALPACA_SECRET_KEY: str
    ALPACA_PAPER_BASE_URL: str = "https://paper-api.alpaca.markets"
    ALPACA_LIVE_BASE_URL: str = "https://api.alpaca.markets"

    # ── Data Providers ────────────────────────────────────────────────────────
    FINNHUB_API_KEY: str
    ALPHA_VANTAGE_API_KEY: str

    # ── LLM (Groq — agent reasoning) ──────────────────────────────────────────
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama3-70b-8192"

    # ── LLM (Gemini — user chat) ──────────────────────────────────────────────
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3-flash-preview"

    # ── Database (Supabase) ───────────────────────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # ── Agent Behaviour ───────────────────────────────────────────────────────
    AGENT_LOOP_INTERVAL_SECONDS: int = 60
    WATCHLIST_RAW: str = '["AAPL","MSFT","NVDA","TSLA","SPY"]'

    # ── Safety Constraints ────────────────────────────────────────────────────
    MAX_POSITION_SIZE_PCT: float = 0.02   # 2 % of equity hard cap
    DAILY_LOSS_LIMIT_PCT: float = 0.015   # 1.5 % circuit-breaker
    RATE_LIMIT_BUFFER: float = 0.80       # trigger back-off at 80 % of limit

    # ── Dynamic Watchlist ─────────────────────────────────────────────────────
    MAX_WATCHLIST_SIZE: int = 20          # hard cap on tickers tracked
    WATCHLIST_HOLD_EVICT_COUNT: int = 5   # remove after N consecutive low-conf HOLDs

    # ── CORS ──────────────────────────────────────────────────────────────────
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    @property
    def WATCHLIST(self) -> list[str]:
        return json.loads(self.WATCHLIST_RAW)

    @property
    def ALPACA_BASE_URL(self) -> str:
        return (
            self.ALPACA_PAPER_BASE_URL
            if self.TRADING_MODE == "PAPER"
            else self.ALPACA_LIVE_BASE_URL
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
