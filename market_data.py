"""Market data lookups using Alpha Vantage API."""

import os
import re
import httpx

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
BASE_URL = "https://www.alphavantage.co/query"


def extract_tickers(text: str) -> list[str]:
    """Extract stock ticker symbols from text (e.g., $TSLA, $AAPL)."""
    tickers = re.findall(r"\$([A-Za-z]{1,5})\b", text)
    return [t.upper() for t in tickers]


async def get_quote(ticker: str) -> dict | None:
    """Fetch current quote for a ticker symbol."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
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
            if not quote:
                return None
            return {
                "ticker": ticker,
                "price": float(quote.get("05. price", 0)),
                "change_percent": quote.get("10. change percent", "0%"),
                "volume": int(quote.get("06. volume", 0)),
            }
    except Exception:
        return None


async def get_market_context(tickers: list[str]) -> list[dict]:
    """Get market data for a list of tickers."""
    results = []
    for ticker in tickers[:3]:  # Limit to 3 to avoid rate limits
        quote = await get_quote(ticker)
        if quote:
            results.append(quote)
    return results
