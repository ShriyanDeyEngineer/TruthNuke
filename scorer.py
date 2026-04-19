"""Trust scoring engine - combines multiple signals into a single trust score."""


def calculate_trust_score(
    analysis: dict,
    author: str,
    has_market_data: bool = False,
) -> int:
    """
    Calculate a 0-100 trust score based on LLM analysis and metadata.

    The manipulation_score from the LLM is 0 (trustworthy) to 100 (manipulative).
    We invert it to get a trust score: 100 - manipulation = trust baseline.

    Then adjust with flags and claim verdicts.
    """
    # Start from the inverse of manipulation score
    # manipulation_score 0 → trust 100, manipulation_score 100 → trust 0
    manipulation = analysis.get("manipulation_score", 50)
    try:
        manipulation = int(manipulation)
    except (ValueError, TypeError):
        manipulation = 50
    manipulation = max(0, min(100, manipulation))
    score = 100 - manipulation

    # Red flags: -7 each, capped at -35
    flags = analysis.get("flags", [])
    score -= min(len(flags) * 7, 35)

    # Claim verdicts — harsh on misleading content
    claims = analysis.get("claims", [])
    for claim in claims:
        verdict = claim.get("verdict", "questionable")
        if verdict == "verified":
            score += 3
        elif verdict == "misleading":
            score -= 15
        elif verdict == "questionable":
            score -= 7

    # Any misleading claim at all should cap the score below "Trustworthy"
    has_misleading = any(c.get("verdict") == "misleading" for c in claims)
    if has_misleading and score > 55:
        score = 55

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
