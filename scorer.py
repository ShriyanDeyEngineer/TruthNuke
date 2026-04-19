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

    # Red flags: -5 each, capped at -25
    flags = analysis.get("flags", [])
    score -= min(len(flags) * 5, 25)

    # Claim verdicts
    claims = analysis.get("claims", [])
    for claim in claims:
        verdict = claim.get("verdict", "questionable")
        if verdict == "verified":
            score += 3
        elif verdict == "misleading":
            score -= 10
        elif verdict == "questionable":
            score -= 5

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
