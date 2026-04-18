"""TruthNuke API - Backend server for the browser extension."""

import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from typing import List

from claim_extractor import extract_and_analyze
from market_data import extract_tickers, get_market_context
from scorer import calculate_trust_score, get_trust_level

app = FastAPI(title="TruthNuke API", version="1.0.0")

# Allow extension to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str
    author: str = "unknown"
    author_name: str = ""
    platform: str = "twitter"


class ClaimResponse(BaseModel):
    claim: str
    verdict: str
    explanation: str


class AnalyzeResponse(BaseModel):
    trust_score: int
    trust_level: str
    claims: List[ClaimResponse]
    flags: List[str]
    explanation: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "truthnuke"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_post(req: AnalyzeRequest):
    """Analyze a social media post for financial trustworthiness."""

    # Step 1: Extract ticker symbols and fetch market data
    tickers = extract_tickers(req.text)
    market_data = await get_market_context(tickers) if tickers else []

    # Step 2: Use LLM to extract claims and detect manipulation
    analysis = await extract_and_analyze(
        text=req.text,
        author=req.author,
        market_data=market_data,
    )

    # Step 3: Calculate trust score
    trust_score = calculate_trust_score(
        analysis=analysis,
        author=req.author,
        has_market_data=len(market_data) > 0,
    )

    return AnalyzeResponse(
        trust_score=trust_score,
        trust_level=get_trust_level(trust_score),
        claims=[
            ClaimResponse(**c) for c in analysis.get("claims", [])
        ],
        flags=analysis.get("flags", []),
        explanation=analysis.get(
            "explanation",
            "Analysis complete. Always verify financial claims independently.",
        ),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
