"""Trust scoring engine - combines multiple signals into a single trust score."""


def calculate_trust_score(
    analysis: dict,
    author: str,
    has_market_data: bool = False,
) -> int:
    """
    Calculate a 0-100 trust score based on LLM analysis and metadata.

    Scoring breakdown:
    - Base score: 50 (neutral starting point)
    - Manipulation score from LLM: -40 to 0 (high manipulation = lower score)
    - Red flags: -5 each (up to -25)
    - Verified claims: +5 each (up to +15)
    - Misleading claims: -10 each (up to -30)
    - Market data available: +5 (claims can be cross-referenced)
    """
    score = 50

    # Factor 1: LLM manipulation score (inverted — high manipulation = bad)
    manipulation = analysis.get("manipulation_score", 50)
    score -= int(manipulation * 0.4)  # 0 to -40

    # Factor 2: Red flags
    flags = analysis.get("flags", [])
    flag_penalty = min(len(flags) * 5, 25)
    score -= flag_penalty

    # Factor 3: Claim verdicts
    claims = analysis.get("claims", [])
    for claim in claims:
        verdict = claim.get("verdict", "questionable")
        if verdict == "verified":
            score += 5
        elif verdict == "misleading":
            score -= 10
        elif verdict == "questionable":
            score -= 3

    # Factor 4: Market data cross-reference bonus
    if has_market_data:
        score += 5

    # Clamp to 0-100
    return max(0, min(100, score))


def get_trust_level(score: int) -> str:
    """Convert numeric score to trust level label."""
    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    else:
        return "low"
