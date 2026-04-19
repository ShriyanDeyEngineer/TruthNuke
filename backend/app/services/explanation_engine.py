"""Explanation Engine for TruthNuke.

This module generates natural-language explanations for claim classifications.
The explanations reference evidence gaps, conflicting sources, manipulative
language patterns, and supporting sources to help users understand the analysis.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 11.2, 12.2
"""

import logging
import re
from typing import Optional

from app.models.schemas import (
    Claim,
    ClassificationLabel,
    ClassificationResult,
    EvidenceSet,
    TrustScoreBreakdown,
)
from app.services.llm_client import LLMClient, LLMUnavailableError


logger = logging.getLogger(__name__)


# Emotional/manipulative language patterns for detection (Req 7.3)
EMOTIONAL_PATTERNS = [
    # Urgency patterns
    (r"\b(urgent|immediately|act now|don't wait|hurry|limited time|last chance)\b", "urgency"),
    # Hype patterns
    (r"\b(guaranteed|100%|risk-free|can't lose|sure thing|easy money|get rich)\b", "hype"),
    # Fear patterns
    (r"\b(crash|collapse|disaster|catastrophe|crisis|panic|plunge|plummet)\b", "fear-inducing"),
    # Greed patterns
    (r"\b(massive gains|huge returns|skyrocket|moon|lambo|millionaire|fortune)\b", "greed-inducing"),
    # Manipulation patterns
    (r"\b(secret|insider|they don't want you to know|hidden|exclusive tip)\b", "manipulation"),
    # Exaggeration patterns
    (r"\b(incredible|unbelievable|amazing|revolutionary|game-changer|unprecedented)\b", "exaggeration"),
    # Pressure patterns
    (r"\b(must buy|must sell|everyone is|you're missing out|fomo)\b", "pressure"),
]

# Compiled patterns for efficiency
COMPILED_EMOTIONAL_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), category)
    for pattern, category in EMOTIONAL_PATTERNS
]


# Fallback explanation templates (Req 7.5)
FALLBACK_EXPLANATIONS = {
    ClassificationLabel.VERIFIED: (
        "This claim appears to be supported by available evidence. "
        "However, we recommend reviewing the referenced sources to form your own conclusions."
    ),
    ClassificationLabel.MISLEADING: (
        "This claim may contain misleading elements. "
        "Some aspects could be technically accurate but presented in a way that may lead to incorrect conclusions. "
        "Please review the referenced sources for more context."
    ),
    ClassificationLabel.LIKELY_FALSE: (
        "This claim appears to conflict with available evidence. "
        "We found information that suggests the claim may not be accurate. "
        "Please review the referenced sources to verify."
    ),
    ClassificationLabel.HARMFUL: (
        "This claim contains potentially harmful financial advice or misinformation. "
        "Exercise caution and consult qualified financial professionals before making any decisions based on this information."
    ),
}


class ExplanationEngine:
    """Generates natural-language explanations for claim classifications.
    
    The engine uses an LLM to produce human-readable explanations that:
    - Reference specific missing or conflicting evidence (Req 7.1, 7.2)
    - Flag emotional or manipulative language patterns (Req 7.3)
    - Use uncertainty language, never presenting as absolute facts (Req 7.4, 11.2)
    - Reference supporting sources by name when available (Req 7.5)
    - Handle conflicting evidence appropriately (Req 12.2)
    
    Attributes:
        llm_client: The LLM client for generating explanations.
    
    Example:
        >>> engine = ExplanationEngine(llm_client)
        >>> explanation = await engine.generate_explanation(
        ...     claim, classification, trust_score, evidence
        ... )
        >>> print(explanation)
        "Based on our analysis, this claim appears to be misleading..."
    
    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 11.2, 12.2
    """
    
    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize the ExplanationEngine.
        
        Args:
            llm_client: The LLM client for generating explanations.
        """
        self.llm_client = llm_client
    
    async def generate_explanation(
        self,
        claim: Claim,
        classification: ClassificationResult,
        trust_score: int,
        trust_score_breakdown: TrustScoreBreakdown,
        evidence: EvidenceSet,
    ) -> str:
        """Generate a natural-language explanation for a claim classification.
        
        Produces an educational explanation that helps users understand why
        a claim was classified a certain way, referencing evidence, sources,
        and language patterns.
        
        Args:
            claim: The claim being explained.
            classification: The classification result for the claim.
            trust_score: The overall trust score (0-100).
            trust_score_breakdown: The breakdown of trust score components.
            evidence: The evidence set retrieved for the claim.
        
        Returns:
            A natural-language explanation string.
        
        Raises:
            LLMUnavailableError: If the LLM service is unavailable.
        
        Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 11.2, 12.2
        """
        # Detect emotional/manipulative language patterns (Req 7.3)
        detected_patterns = self._detect_emotional_patterns(claim.text)
        
        # Identify missing or conflicting evidence (Req 7.1, 7.2, 12.2)
        evidence_analysis = self._analyze_evidence(evidence)
        
        # Build the prompt for the LLM
        prompt = self._build_explanation_prompt(
            claim=claim,
            classification=classification,
            trust_score=trust_score,
            trust_score_breakdown=trust_score_breakdown,
            evidence=evidence,
            detected_patterns=detected_patterns,
            evidence_analysis=evidence_analysis,
        )
        
        system_prompt = self._get_system_prompt()
        
        try:
            explanation = await self.llm_client.complete(prompt, system_prompt)
            
            # Return fallback if LLM returns empty response (Req 7.5)
            if not explanation or not explanation.strip():
                logger.warning("LLM returned empty explanation, using fallback")
                return self._generate_fallback_explanation(
                    claim, classification, evidence, detected_patterns
                )
            
            return explanation.strip()
            
        except LLMUnavailableError:
            # Re-raise LLM unavailable errors
            raise
        except Exception as e:
            # Log unexpected errors and return fallback
            logger.error(f"Unexpected error generating explanation: {e}")
            return self._generate_fallback_explanation(
                claim, classification, evidence, detected_patterns
            )
    
    def _detect_emotional_patterns(self, text: str) -> list[dict[str, str]]:
        """Detect emotional or manipulative language patterns in text.
        
        Scans the claim text for patterns that indicate emotional manipulation,
        urgency, hype, fear, or other concerning language.
        
        Args:
            text: The text to analyze.
        
        Returns:
            List of detected patterns with their categories and matched text.
        
        Requirements: 7.3
        """
        detected = []
        
        for pattern, category in COMPILED_EMOTIONAL_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                detected.append({
                    "category": category,
                    "matched_text": match if isinstance(match, str) else match[0],
                })
        
        # Check for excessive punctuation
        excessive_punct = re.findall(r'[!?]{2,}', text)
        if excessive_punct:
            detected.append({
                "category": "excessive punctuation",
                "matched_text": excessive_punct[0],
            })
        
        # Check for ALL CAPS words (excluding common acronyms)
        all_caps_words = re.findall(r'\b[A-Z]{4,}\b', text)
        common_acronyms = {'NYSE', 'NASDAQ', 'SEC', 'IPO', 'ETF', 'CEO', 'CFO', 'GDP', 'FOMC', 'FDIC'}
        non_acronym_caps = [w for w in all_caps_words if w not in common_acronyms]
        if non_acronym_caps:
            detected.append({
                "category": "emphatic capitalization",
                "matched_text": non_acronym_caps[0],
            })
        
        return detected
    
    def _analyze_evidence(self, evidence: EvidenceSet) -> dict:
        """Analyze evidence for gaps and conflicts.
        
        Examines the evidence set to identify:
        - Missing evidence (insufficient evidence flag)
        - Conflicting sources (contradictory information)
        - Supporting sources (corroborating information)
        
        Args:
            evidence: The evidence set to analyze.
        
        Returns:
            Dictionary containing evidence analysis results.
        
        Requirements: 7.1, 7.2, 12.2
        """
        analysis = {
            "has_evidence": bool(evidence.results),
            "insufficient_evidence": evidence.insufficient_evidence,
            "source_count": len(evidence.results),
            "supporting_sources": [],
            "conflicting_sources": [],
            "neutral_sources": [],
        }
        
        if not evidence.results:
            return analysis
        
        # Keywords indicating support
        support_keywords = [
            "confirms", "supports", "agrees", "corroborates", "validates",
            "verified", "accurate", "correct", "consistent", "aligns"
        ]
        
        # Keywords indicating conflict
        conflict_keywords = [
            "contradicts", "disputes", "denies", "refutes", "false",
            "incorrect", "inaccurate", "misleading", "debunked", "contrary",
            "however", "opposes", "challenges", "questions"
        ]
        
        for result in evidence.results:
            summary_lower = result.summary.lower()
            
            is_supporting = any(kw in summary_lower for kw in support_keywords)
            is_conflicting = any(kw in summary_lower for kw in conflict_keywords)
            
            source_info = {
                "name": result.source,
                "title": result.title,
                "summary": result.summary,
                "relevance": result.relevance_score,
            }
            
            if is_conflicting:
                analysis["conflicting_sources"].append(source_info)
            elif is_supporting:
                analysis["supporting_sources"].append(source_info)
            else:
                analysis["neutral_sources"].append(source_info)
        
        return analysis
    
    def _build_explanation_prompt(
        self,
        claim: Claim,
        classification: ClassificationResult,
        trust_score: int,
        trust_score_breakdown: TrustScoreBreakdown,
        evidence: EvidenceSet,
        detected_patterns: list[dict[str, str]],
        evidence_analysis: dict,
    ) -> str:
        """Build the prompt for the LLM to generate an explanation.
        
        Constructs a detailed prompt that provides the LLM with all necessary
        context to generate an informative, educational explanation.
        
        Args:
            claim: The claim being explained.
            classification: The classification result.
            trust_score: The overall trust score.
            trust_score_breakdown: The breakdown of trust score components.
            evidence: The evidence set.
            detected_patterns: Detected emotional/manipulative patterns.
            evidence_analysis: Analysis of evidence gaps and conflicts.
        
        Returns:
            The prompt string for the LLM.
        """
        # Build evidence section
        evidence_section = self._format_evidence_section(evidence_analysis)
        
        # Build patterns section
        patterns_section = self._format_patterns_section(detected_patterns)
        
        # Build score breakdown section
        score_section = self._format_score_section(trust_score, trust_score_breakdown)
        
        prompt = f"""Generate a clear, educational explanation for the following financial claim analysis.

CLAIM:
"{claim.text}"

CLASSIFICATION: {classification.label.value}
CLASSIFICATION REASONING: {classification.reasoning}

TRUST SCORE: {trust_score}/100
{score_section}

{evidence_section}

{patterns_section}

INSTRUCTIONS:
1. Explain why this claim received the "{classification.label.value}" classification
2. Reference specific evidence that supports or contradicts the claim (mention source names)
3. If evidence is missing or insufficient, explain what information would be needed
4. If there are conflicting sources, describe the conflict clearly
5. If emotional or manipulative language was detected, point it out specifically
6. Use uncertainty language - say "appears to be", "suggests", "may indicate" rather than absolute statements
7. Be educational - help the user understand how to evaluate similar claims
8. Keep the explanation concise but informative (2-4 paragraphs)
9. Do NOT present the classification as an absolute fact
10. Reference supporting sources by name when available

Generate the explanation:"""

        return prompt
    
    def _format_evidence_section(self, evidence_analysis: dict) -> str:
        """Format the evidence analysis into a prompt section.
        
        Args:
            evidence_analysis: The evidence analysis dictionary.
        
        Returns:
            Formatted evidence section string.
        """
        lines = ["EVIDENCE ANALYSIS:"]
        
        if not evidence_analysis["has_evidence"]:
            lines.append("- No evidence was found for this claim")
            return "\n".join(lines)
        
        if evidence_analysis["insufficient_evidence"]:
            lines.append("- Evidence is flagged as insufficient")
        
        lines.append(f"- Total sources found: {evidence_analysis['source_count']}")
        
        if evidence_analysis["supporting_sources"]:
            lines.append(f"- Supporting sources ({len(evidence_analysis['supporting_sources'])}):")
            for source in evidence_analysis["supporting_sources"][:3]:  # Limit to top 3
                lines.append(f"  * {source['name']}: {source['summary'][:150]}...")
        
        if evidence_analysis["conflicting_sources"]:
            lines.append(f"- Conflicting sources ({len(evidence_analysis['conflicting_sources'])}):")
            for source in evidence_analysis["conflicting_sources"][:3]:  # Limit to top 3
                lines.append(f"  * {source['name']}: {source['summary'][:150]}...")
        
        if evidence_analysis["neutral_sources"]:
            lines.append(f"- Neutral/related sources ({len(evidence_analysis['neutral_sources'])}):")
            for source in evidence_analysis["neutral_sources"][:2]:  # Limit to top 2
                lines.append(f"  * {source['name']}: {source['summary'][:100]}...")
        
        return "\n".join(lines)
    
    def _format_patterns_section(self, detected_patterns: list[dict[str, str]]) -> str:
        """Format detected patterns into a prompt section.
        
        Args:
            detected_patterns: List of detected emotional/manipulative patterns.
        
        Returns:
            Formatted patterns section string.
        """
        if not detected_patterns:
            return "LANGUAGE ANALYSIS:\n- No concerning language patterns detected"
        
        lines = ["LANGUAGE ANALYSIS:"]
        lines.append("- Concerning language patterns detected:")
        
        # Group by category
        categories = {}
        for pattern in detected_patterns:
            cat = pattern["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(pattern["matched_text"])
        
        for category, matches in categories.items():
            unique_matches = list(set(matches))[:3]  # Limit to 3 unique matches
            lines.append(f"  * {category.title()}: {', '.join(unique_matches)}")
        
        return "\n".join(lines)
    
    def _format_score_section(
        self,
        trust_score: int,
        breakdown: TrustScoreBreakdown,
    ) -> str:
        """Format the trust score breakdown into a prompt section.
        
        Args:
            trust_score: The overall trust score.
            breakdown: The trust score breakdown.
        
        Returns:
            Formatted score section string.
        """
        lines = ["SCORE BREAKDOWN:"]
        lines.append(f"- Source Credibility: {breakdown.source_credibility}/100")
        lines.append(f"- Evidence Strength: {breakdown.evidence_strength}/100")
        lines.append(f"- Language Neutrality: {breakdown.language_neutrality}/100")
        lines.append(f"- Cross-Source Agreement: {breakdown.cross_source_agreement}/100")
        
        # Add interpretation
        if trust_score >= 70:
            lines.append("- Overall: High trust score indicates generally reliable information")
        elif trust_score >= 40:
            lines.append("- Overall: Moderate trust score suggests caution is warranted")
        else:
            lines.append("- Overall: Low trust score indicates significant concerns")
        
        return "\n".join(lines)
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for explanation generation.
        
        Returns:
            The system prompt string.
        """
        return """You are an expert financial fact-checker and educator. Your role is to explain 
financial claim analysis results in a clear, helpful, and educational manner.

Key principles:
1. NEVER present classifications as absolute facts - always use uncertainty language
2. Be educational - help users understand how to evaluate financial claims
3. Reference specific sources by name when available
4. Point out emotional or manipulative language patterns when detected
5. Explain evidence gaps and conflicts clearly
6. Be concise but thorough
7. Maintain a neutral, professional tone
8. Encourage users to verify information independently

Remember: Your explanations help users make informed decisions. Be helpful, not alarmist."""
    
    def _generate_fallback_explanation(
        self,
        claim: Claim,
        classification: ClassificationResult,
        evidence: EvidenceSet,
        detected_patterns: list[dict[str, str]],
    ) -> str:
        """Generate a fallback explanation when LLM is unavailable or returns empty.
        
        Produces a basic but informative explanation using templates and
        available data.
        
        Args:
            claim: The claim being explained.
            classification: The classification result.
            evidence: The evidence set.
            detected_patterns: Detected emotional/manipulative patterns.
        
        Returns:
            A fallback explanation string.
        
        Requirements: 7.5
        """
        # Start with the base template for this classification
        base_explanation = FALLBACK_EXPLANATIONS.get(
            classification.label,
            "This claim has been analyzed. Please review the referenced sources for more information."
        )
        
        parts = [base_explanation]
        
        # Add evidence information (Req 7.1, 7.2)
        if evidence.insufficient_evidence or not evidence.results:
            parts.append(
                "Note: Limited evidence was available for this claim, "
                "which may affect the reliability of this assessment."
            )
        elif evidence.results:
            source_names = [r.source for r in evidence.results[:3]]
            if source_names:
                sources_text = ", ".join(source_names)
                parts.append(f"Sources consulted include: {sources_text}.")
        
        # Add language pattern warnings (Req 7.3)
        if detected_patterns:
            categories = list(set(p["category"] for p in detected_patterns))
            if len(categories) == 1:
                parts.append(
                    f"The claim contains {categories[0]} language, "
                    "which may indicate an attempt to influence your decision-making."
                )
            else:
                categories_text = ", ".join(categories[:3])
                parts.append(
                    f"The claim contains concerning language patterns ({categories_text}), "
                    "which may indicate an attempt to influence your decision-making."
                )
        
        return " ".join(parts)
