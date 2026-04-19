"""Market data lookups using Alpha Vantage API."""

import asyncio
import os
import re
from typing import List, Optional
import httpx

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
BASE_URL = "https://www.alphavantage.co/query"


def extract_tickers(text: str) -> List[str]:
    """Extract stock ticker symbols from text (e.g., $TSLA, $AAPL)."""
    tickers = re.findall(r"\$([A-Za-z]{1,5})\b", text)
    return list(dict.fromkeys(t.upper() for t in tickers))  # dedupe, preserve order


async def get_quote(ticker: str) -> Optional[dict]:
    """Fetch current quote for a ticker symbol."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                BASE_URL,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": ticker,
                    "apikey": ALPHA_VANTAGE_KEY,
                },
            )
            data = resp.json()
            quote = data.get("Global Quote", {})
            if not quote or not quote.get("05. price"):
                return None
            return {
                "ticker": ticker,
                "price": float(quote.get("05. price", 0)),
                "change_percent": quote.get("10. change percent", "0%"),
                "volume": int(quote.get("06. volume", 0)),
            }
    except Exception:
        return None


async def get_market_context(tickers: List[str]) -> List[dict]:
    """Get market data for a list of tickers concurrently."""
    limited = tickers[:3]  # Limit to 3 to avoid rate limits
    results = await asyncio.gather(*(get_quote(t) for t in limited))
    return [r for r in results if r is not None]
