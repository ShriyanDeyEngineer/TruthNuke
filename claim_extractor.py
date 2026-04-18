"""LLM-based claim extraction and analysis using Claude."""

import os
import json
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

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


async def extract_and_analyze(text: str, author: str, market_data: list[dict] | None = None) -> dict:
    """Use Claude to extract claims and analyze trustworthiness."""
    market_context = ""
    if market_data:
        market_context = "\n\nCurrent market data for referenced tickers:\n"
        for md in market_data:
            market_context += f"- {md['ticker']}: ${md['price']:.2f} ({md['change_percent']} today)\n"

    user_message = f"""Analyze this social media post about finance/investing:

Author: @{author}
Post: "{text}"
{market_context}
Extract claims, identify red flags, and assess trustworthiness."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        result_text = response.content[0].text
        return json.loads(result_text)
    except json.JSONDecodeError:
        # If Claude doesn't return valid JSON, return a default
        return {
            "claims": [],
            "flags": ["Unable to fully analyze this post"],
            "manipulation_score": 50,
            "explanation": "Analysis was inconclusive. Exercise caution with any financial advice from social media.",
        }
    except Exception as e:
        return {
            "claims": [],
            "flags": [f"Analysis error: {str(e)}"],
            "manipulation_score": 50,
            "explanation": "Could not complete analysis. Always verify financial claims independently.",
        }
