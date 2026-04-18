"""LLM-based claim extraction and analysis using Featherless AI."""

import os
import json
import logging
from typing import List, Optional
import httpx

logger = logging.getLogger("truthnuke")

FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"

SYSTEM_PROMPT = """You are a financial content analyst. Your job is to analyze social media posts about finance and investing.

For each post, you must:
1. Extract any specific financial claims (price predictions, investment advice, return promises)
2. Identify red flags and manipulation tactics
3. Assess the overall trustworthiness of the content

Red flags to look for:
- Urgency language ("act NOW", "last chance", "don't miss out")
- Unrealistic return promises ("guaranteed 10x", "can't lose")
- Pump-and-dump indicators (heavy promotion of low-cap assets)
- Undisclosed sponsorship or affiliate promotion
- Appeal to authority without credentials
- Cherry-picked data or survivorship bias
- Emotional manipulation (fear, greed, FOMO)
- Vague or unfalsifiable predictions

Respond ONLY with valid JSON in this exact format:
{
  "claims": [
    {
      "claim": "the specific claim extracted",
      "verdict": "verified|questionable|misleading",
      "explanation": "brief explanation"
    }
  ],
  "flags": ["list of red flags detected"],
  "manipulation_score": 0-100,
  "explanation": "2-3 sentence plain-English summary for a beginner investor"
}"""


async def extract_and_analyze(text: str, author: str, market_data: Optional[List[dict]] = None) -> dict:
    """Use Claude to extract claims and analyze trustworthiness."""
    market_context = ""
    if market_data:
        market_context = "\n\nCurrent market data for referenced tickers:\n"
        for md in market_data:
            market_context += f"- {md['ticker']}: ${md['price']:.2f} ({md['change_percent']} today)\n"

    user_message = f"""Analyze this social media post about finance/investing:

Author: @{author}
Post: "{text[:2000]}"
{market_context}
Extract claims, identify red flags, and assess trustworthiness."""

    try:
        # Truncate long texts to avoid slow API responses
        truncated_text = text[:2000] if len(text) > 2000 else text
        logger.info(f"Analyzing post by @{author} ({len(text)} chars, truncated to {len(truncated_text)})")

        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                f"{FEATHERLESS_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "mistralai/Mistral-Nemo-Instruct-2407",
                    "max_tokens": 512,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                },
                timeout=20.0,
            )
            response.raise_for_status()
            data = response.json()

        result_text = data["choices"][0]["message"]["content"]
        return json.loads(result_text)
    except json.JSONDecodeError:
        logger.warning(f"LLM returned invalid JSON for @{author}")
        return {
            "claims": [],
            "flags": ["Unable to fully analyze this post"],
            "manipulation_score": 50,
            "explanation": "Analysis was inconclusive. Exercise caution with any financial advice from social media.",
        }
    except Exception as e:
        logger.error(f"Analysis failed for @{author}: {e}")
        return {
            "claims": [],
            "flags": [f"Analysis error: {str(e)}"],
            "manipulation_score": 50,
            "explanation": "Could not complete analysis. Always verify financial claims independently.",
        }
