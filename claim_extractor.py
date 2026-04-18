"""LLM-based claim extraction and analysis using Featherless AI."""

import os
import json
import re
import logging
from typing import List, Optional
import httpx

logger = logging.getLogger("truthnuke")

FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"

SYSTEM_PROMPT = """You are a financial content analyst. Analyze social media posts about finance and investing.

For each post:
1. Extract specific financial claims (price predictions, investment advice, return promises)
2. Identify red flags and manipulation tactics
3. Assess overall trustworthiness

Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{
  "claims": [
    {
      "claim": "the specific claim extracted",
      "verdict": "verified",
      "explanation": "brief explanation"
    }
  ],
  "flags": ["list of red flags detected"],
  "manipulation_score": 75,
  "explanation": "2-3 sentence summary for a beginner investor"
}

Rules for the JSON:
- "claims" must be an array of objects, each with "claim", "verdict", and "explanation" string fields
- "verdict" must be one of: "verified", "questionable", "misleading"
- "flags" must be an array of strings
- "manipulation_score" must be an integer from 0 to 100
- "explanation" must be a string"""


def normalize_response(raw: dict) -> dict:
    """Normalize the LLM response to match the expected schema,
    handling common format variations from different models."""
    result = {
        "claims": [],
        "flags": [],
        "manipulation_score": 50,
        "explanation": raw.get("explanation", "Analysis complete."),
    }

    # Normalize claims — could be strings, dicts, or missing fields
    raw_claims = raw.get("claims", [])
    if isinstance(raw_claims, list):
        for c in raw_claims:
            if isinstance(c, dict) and "claim" in c:
                result["claims"].append({
                    "claim": str(c.get("claim", "")),
                    "verdict": str(c.get("verdict", "questionable")).lower(),
                    "explanation": str(c.get("explanation", "")),
                })
            elif isinstance(c, str) and c.strip():
                result["claims"].append({
                    "claim": c,
                    "verdict": "questionable",
                    "explanation": "",
                })

    # Normalize flags — could be a dict, list, or missing
    raw_flags = raw.get("flags", [])
    if isinstance(raw_flags, list):
        result["flags"] = [str(f) for f in raw_flags if f]
    elif isinstance(raw_flags, dict):
        result["flags"] = [k for k, v in raw_flags.items() if v]

    # Normalize manipulation_score — could be 0-1 float or 0-100 int
    score = raw.get("manipulation_score", 50)
    if isinstance(score, (int, float)):
        if 0 < score <= 1:
            score = int(score * 100)
        result["manipulation_score"] = max(0, min(100, int(score)))

    return result


def extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks and extra text."""
    text = text.strip()

    # Try to extract from markdown code block
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1).strip()

    # Try to find JSON object in the text
    brace_start = text.find("{")
    if brace_start >= 0:
        # Find the matching closing brace
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    text = text[brace_start:i + 1]
                    break

    return json.loads(text)


async def extract_and_analyze(text: str, author: str, market_data: Optional[List[dict]] = None) -> dict:
    """Use LLM to extract claims and analyze trustworthiness."""
    market_context = ""
    if market_data:
        market_context = "\n\nCurrent market data for referenced tickers:\n"
        for md in market_data:
            market_context += f"- {md['ticker']}: ${md['price']:.2f} ({md['change_percent']} today)\n"

    truncated_text = text[:2000] if len(text) > 2000 else text
    logger.info(f"Analyzing post by @{author} ({len(text)} chars, truncated to {len(truncated_text)})")

    user_message = f"""Analyze this social media post about finance/investing:

Author: @{author}
Post: "{truncated_text}"
{market_context}
Extract claims, identify red flags, and assess trustworthiness. Respond with JSON only."""

    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                f"{FEATHERLESS_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
                    "max_tokens": 1024,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                },
                timeout=25.0,
            )
            response.raise_for_status()
            data = response.json()

        result_text = data["choices"][0]["message"]["content"]
        raw = extract_json(result_text)
        return normalize_response(raw)

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"LLM returned invalid JSON for @{author}: {e}")
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
            "flags": [f"Analysis error: {str(e)}"],
            "manipulation_score": 50,
            "explanation": "Could not complete analysis. Always verify financial claims independently.",
        }
