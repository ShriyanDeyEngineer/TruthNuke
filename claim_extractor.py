"""LLM-based claim extraction and analysis using Featherless AI."""

import os
import re
import json
import logging
from typing import List, Optional
import httpx

logger = logging.getLogger("truthnuke")

FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"

SYSTEM_PROMPT = """You are a financial content analyst. You MUST respond with ONLY valid JSON.

Analyze the post and return this exact JSON structure:
{"claims":[{"claim":"text","verdict":"verified|questionable|misleading","explanation":"text","sources":["text"]}],"flags":["text"],"manipulation_score":50,"explanation":"text","sources":["text"]}

Rules:
- claims: extract specific financial claims. Empty array [] if none found.
- verdict: "verified", "questionable", or "misleading"
- claim sources: for questionable or misleading claims, provide 1-2 well-known sources that contradict or could verify the claim. Use real, major outlets like Reuters, Bloomberg, CNBC, Wall Street Journal, SEC filings, Federal Reserve, Yahoo Finance, MarketWatch, Financial Times, or verified expert accounts. Format as "Source Name: brief what they reported". Empty array [] if verified or no source needed.
- flags: red flags like urgency language, unrealistic promises, pump-and-dump, FOMO, undisclosed sponsorship. Empty array [] if none.
- manipulation_score: 0 (trustworthy) to 100 (manipulative)
- explanation: 1-2 sentence summary for a beginner investor
- sources: top-level array of 1-3 major sources relevant to the overall topic for the reader to check. Format as "Source Name: what to look for". Empty array [] if post is clean.

If the post is NOT about finance/investing, return:
{"claims":[],"flags":[],"manipulation_score":0,"explanation":"This post does not contain financial advice.","sources":[]}

RESPOND WITH ONLY JSON. No markdown, no explanation, no code blocks."""


def extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling various formats."""
    text = text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Find first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("No valid JSON found in response", text, 0)


async def extract_and_analyze(text: str, author: str, market_data: Optional[List[dict]] = None) -> dict:
    """Use LLM to extract claims and analyze trustworthiness."""
    truncated = text[:2000] if len(text) > 2000 else text
    logger.info(f"Analyzing post by @{author} ({len(truncated)} chars)")

    user_message = f'Analyze this post by @{author}: "{truncated}"'

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{FEATHERLESS_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "max_tokens": 768,
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                },
                timeout=45.0,
            )
            resp.raise_for_status()
            data = resp.json()

        result_text = data["choices"][0]["message"]["content"]
        logger.info(f"LLM response for @{author}: {result_text[:150]}")
        return extract_json(result_text)

    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON from LLM for @{author}: {e}")
        return {
            "claims": [],
            "flags": ["Unable to fully analyze this post"],
            "manipulation_score": 50,
            "explanation": "Analysis was inconclusive. Exercise caution with any financial advice from social media.",
        }
    except Exception as e:
        logger.error(f"Analysis failed for @{author}: {type(e).__name__}: {e}")
        return {
            "claims": [],
            "flags": [f"Analysis error: {type(e).__name__}"],
            "manipulation_score": 50,
            "explanation": "Could not complete analysis. Always verify financial claims independently.",
        }
