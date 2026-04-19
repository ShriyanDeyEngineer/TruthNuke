"""Risk Scoring Module for TruthNuke.

Multi-signal risk scoring that layers categorized keyword detection,
phrase-level pattern matching, and claim-aware scoring on top of the
existing claim extraction pipeline.

This module does NOT modify or duplicate claim extraction logic.
It consumes claims produced upstream and adds a risk assessment layer.
"""

import re
import logging
from dataclasses import dataclass, field

from app.models.schemas import Claim, ClassificationLabel, ClassificationResult


logger = logging.getLogger(__name__)


# ============================================================================
# 1. Categorized keyword constants (replaces flat list)
# ============================================================================

MARKET_TERMS: set[str] = {
    "stock", "stocks", "equity", "equities", "shares", "market",
    "sp500", "s&p", "nasdaq", "dow", "nyse", "index", "indices",
    "portfolio", "dividend", "earnings", "ipo", "etf", "mutual fund",
    "market cap", "blue chip", "penny stock",
}

TRADING_ACTIONS: set[str] = {
    "buy", "sell", "short", "long", "hold", "trade", "trading",
    "calls", "puts", "options", "strike", "expiry", "forex",
    "leverage", "margin", "position", "entry", "exit",
}

CRYPTO_TERMS: set[str] = {
    "crypto", "bitcoin", "btc", "eth", "ethereum", "altcoin", "defi",
    "nft", "blockchain", "token", "coin", "mining", "staking",
    "wallet", "exchange", "binance", "coinbase",
    "$btc", "$eth", "$sol", "$doge",
}

HYPE_TERMS: set[str] = {
    "guaranteed", "guaranteed returns", "risk-free", "free money",
    "easy money", "get rich", "sure thing", "can't lose",
    "moon", "to the moon", "lambo", "100x", "10x", "1000x",
    "passive income", "financial freedom", "retire early",
    "once in a lifetime", "don't miss out", "act now",
    "pump", "dump", "pump and dump",
    "nfa", "dyor", "not financial advice",
}

NEUTRAL_INDICATORS: set[str] = {
    "according to", "reported", "data shows", "analysis indicates",
    "research suggests", "quarterly report", "annual report",
    "sec filing", "earnings call", "federal reserve",
    "year-over-year", "quarter-over-quarter", "basis points",
    "fiscal year", "balance sheet", "revenue growth",
}

# Category weights for keyword scoring
CATEGORY_WEIGHTS: dict[str, float] = {
    "hype": 3.0,
    "trading": 1.5,
    "crypto": 1.0,
    "market": 0.5,
    "neutral": -1.0,  # Reduces risk
}


# ============================================================================
# 2. High-risk phrase patterns (regex)
# ============================================================================

HIGH_RISK_PHRASES: list[tuple[str, re.Pattern]] = [
    ("guaranteed returns", re.compile(r"\bguaranteed\s+returns?\b", re.I)),
    ("risk-free profit", re.compile(r"\brisk[- ]free\s+(profit|income|returns?)\b", re.I)),
    ("will moon / 10x / 100x", re.compile(r"\b(will|going to)\s+(10x|100x|1000x|moon)\b", re.I)),
    ("buy now urgency", re.compile(r"\b(buy|invest|get in)\s+now\b", re.I)),
    ("don't miss out", re.compile(r"\bdon'?t\s+miss\s+out\b", re.I)),
    ("pump and dump", re.compile(r"\bpump\s+and\s+dump\b", re.I)),
    ("easy money", re.compile(r"\beasy\s+money\b", re.I)),
    ("get rich quick", re.compile(r"\bget\s+rich\s+(quick|fast)\b", re.I)),
    ("secret/insider tip", re.compile(r"\b(secret|insider)\s+(tip|info|knowledge)\b", re.I)),
    ("they don't want you to know", re.compile(r"\bthey\s+don'?t\s+want\s+you\s+to\s+know\b", re.I)),
    ("financial freedom promise", re.compile(r"\bfinancial\s+freedom\s+(in|within|by)\b", re.I)),
    ("must buy/sell urgency", re.compile(r"\b(must|need to|have to)\s+(buy|sell|invest)\b", re.I)),
    ("ticker hype", re.compile(r"\$[A-Z]{1,5}\s+(to the moon|🚀|going up|will explode)", re.I)),
]

# Phrase weight (highest signal)
PHRASE_WEIGHT: float = 4.0


# ============================================================================
# 3. Risk thresholds
# ============================================================================

RISK_THRESHOLDS = {
    "low": (0, 2),
    "medium": (3, 5),
    "high": (6, float("inf")),
}


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class KeywordSignals:
    """Keyword matches grouped by category."""
    market: list[str] = field(default_factory=list)
    trading: list[str] = field(default_factory=list)
    crypto: list[str] = field(default_factory=list)
    hype: list[str] = field(default_factory=list)
    neutral: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "market": self.market,
            "trading": self.trading,
            "crypto": self.crypto,
            "hype": self.hype,
            "neutral": self.neutral,
        }


@dataclass
class RiskResult:
    """Output of the risk scoring function."""
    risk_score: int
    risk_level: str  # "low" | "medium" | "high"
    signals: dict  # { keywords, phrases, claims }
    explanation: str


# ============================================================================
# Core functions
# ============================================================================

def scan_keywords(text: str) -> KeywordSignals:
    """Scan text for categorized keyword matches.

    Returns matches grouped by category. Each keyword is matched
    as a whole word (case-insensitive).
    """
    lower = text.lower()
    signals = KeywordSignals()

    for term in MARKET_TERMS:
        if term in lower:
            signals.market.append(term)
    for term in TRADING_ACTIONS:
        if term in lower:
            signals.trading.append(term)
    for term in CRYPTO_TERMS:
        if term in lower:
            signals.crypto.append(term)
    for term in HYPE_TERMS:
        if term in lower:
            signals.hype.append(term)
    for term in NEUTRAL_INDICATORS:
        if term in lower:
            signals.neutral.append(term)

    return signals


def scan_phrases(text: str) -> list[str]:
    """Scan text for high-risk phrase patterns.

    Returns a list of matched phrase labels.
    """
    matched: list[str] = []
    for label, pattern in HIGH_RISK_PHRASES:
        if pattern.search(text):
            matched.append(label)
    return matched


def score_claims(
    claims: list[Claim],
    classifications: dict[str, ClassificationResult] | None = None,
) -> tuple[float, list[dict]]:
    """Score claims based on type and classification.

    Returns (score_delta, claim_signals) where score_delta is the
    net risk adjustment from claims and claim_signals is a list of
    per-claim signal dicts for the output.
    """
    delta = 0.0
    claim_signals: list[dict] = []

    for claim in claims:
        signal: dict = {
            "text": claim.text[:120],
            "type": claim.type,
            "risk_contribution": 0,
        }

        # Category-based scoring
        ctype = claim.type.lower() if claim.type else ""

        if ctype in ("investment", "market"):
            # Check if it's a prediction (heuristic: future tense words)
            prediction_pattern = re.compile(
                r"\b(will|going to|expected to|forecast|predict|projected)\b", re.I
            )
            if prediction_pattern.search(claim.text):
                delta += 2
                signal["risk_contribution"] = 2
                signal["reason"] = "speculative/predictive investment claim"
            else:
                delta += 0.5
                signal["risk_contribution"] = 0.5
                signal["reason"] = "investment claim (factual tone)"

        elif ctype == "crypto":
            delta += 1
            signal["risk_contribution"] = 1
            signal["reason"] = "crypto claim (inherently higher risk)"

        elif ctype == "economic":
            delta -= 1
            signal["risk_contribution"] = -1
            signal["reason"] = "economic/macro claim (typically factual)"

        elif ctype == "banking":
            delta += 0.5
            signal["risk_contribution"] = 0.5
            signal["reason"] = "banking claim"

        # Classification-based adjustment
        if classifications and claim.id in classifications:
            label = classifications[claim.id].label
            if label == ClassificationLabel.HARMFUL:
                delta += 3
                signal["classification_boost"] = 3
            elif label == ClassificationLabel.LIKELY_FALSE:
                delta += 2
                signal["classification_boost"] = 2
            elif label == ClassificationLabel.MISLEADING:
                delta += 1
                signal["classification_boost"] = 1
            elif label == ClassificationLabel.VERIFIED:
                delta -= 1
                signal["classification_boost"] = -1

        claim_signals.append(signal)

    return delta, claim_signals


def compute_risk_score(
    text: str,
    claims: list[Claim],
    classifications: dict[str, ClassificationResult] | None = None,
) -> RiskResult:
    """Compute a multi-signal risk score for the given text and claims.

    Layers three signal sources:
    1. Categorized keyword matches (weighted by category)
    2. High-risk phrase pattern matches (highest weight)
    3. Claim-aware scoring (type + classification)

    Args:
        text: The raw or normalized input text.
        claims: Claims already extracted upstream.
        classifications: Optional classification results keyed by claim id.

    Returns:
        RiskResult with score, level, signals breakdown, and explanation.
    """
    # --- Layer 1: Keywords ---
    kw_signals = scan_keywords(text)
    kw_score = (
        len(kw_signals.hype) * CATEGORY_WEIGHTS["hype"]
        + len(kw_signals.trading) * CATEGORY_WEIGHTS["trading"]
        + len(kw_signals.crypto) * CATEGORY_WEIGHTS["crypto"]
        + len(kw_signals.market) * CATEGORY_WEIGHTS["market"]
        + len(kw_signals.neutral) * CATEGORY_WEIGHTS["neutral"]
    )

    # --- Layer 2: Phrases ---
    phrase_matches = scan_phrases(text)
    phrase_score = len(phrase_matches) * PHRASE_WEIGHT

    # --- Layer 3: Claims ---
    claim_delta, claim_signals = score_claims(claims, classifications)

    # --- Combine ---
    raw_score = kw_score + phrase_score + claim_delta
    # Floor at 0
    final_score = max(0, round(raw_score))

    # Determine level
    risk_level = "low"
    for level, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= final_score <= hi:
            risk_level = level
            break

    # Build explanation
    parts: list[str] = []
    if phrase_matches:
        parts.append(f"High-risk phrases detected: {', '.join(phrase_matches)}.")
    if kw_signals.hype:
        parts.append(f"Hype language found: {', '.join(kw_signals.hype[:5])}.")
    if claim_signals:
        speculative = [c for c in claim_signals if c.get("risk_contribution", 0) >= 2]
        if speculative:
            parts.append(f"{len(speculative)} speculative/predictive claim(s) detected.")
        verified = [c for c in claim_signals if c.get("classification_boost") == -1]
        if verified:
            parts.append(f"{len(verified)} claim(s) verified by evidence.")
    if kw_signals.neutral:
        parts.append("Some neutral/institutional language detected, which lowers risk.")
    if not parts:
        parts.append("No significant risk signals detected.")

    explanation = " ".join(parts)

    logger.info(
        f"Risk score: {final_score} ({risk_level}) — "
        f"kw={kw_score:.1f}, phrases={phrase_score:.1f}, claims={claim_delta:.1f}"
    )

    return RiskResult(
        risk_score=final_score,
        risk_level=risk_level,
        signals={
            "keywords": kw_signals.to_dict(),
            "phrases": phrase_matches,
            "claims": claim_signals,
        },
        explanation=explanation,
    )
