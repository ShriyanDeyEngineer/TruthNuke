"""Trust Score Engine for TruthNuke.

This module computes a weighted trust score from four independently computed sub-scores:
- Source Credibility (SC): Based on reliability ratings of sources in retrieved evidence
- Evidence Strength (ES): Based on number and quality of supporting sources
- Language Neutrality (LN): Based on sentiment and emotional tone analysis
- Cross-Source Agreement (CSA): Based on consistency of information across sources

The final trust score is computed using the formula:
Trust_Score = round(SC * 0.3 + ES * 0.3 + LN * 0.2 + CSA * 0.2) clamped to [0, 100]

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 28.1, 28.2, 28.3, 28.4, 28.7
"""

import logging
import re
from dataclasses import dataclass
from typing import Union

from app.models.schemas import (
    Claim,
    ClassificationLabel,
    ClassificationResult,
    DeductionReference,
    EvidenceSet,
    NoCorroborationDeduction,
    TrustScoreBreakdown,
    TrustScoreWeights,
)


logger = logging.getLogger(__name__)


# Known reputable sources for source credibility scoring (Req 28.4)
REPUTABLE_SOURCES = {
    # Tier 1: Major established news outlets (highest credibility)
    "reuters": 95,
    "associated press": 95,
    "ap": 95,
    "bloomberg": 90,
    "bbc": 90,
    "financial times": 90,
    "wall street journal": 90,
    "wsj": 90,
    "new york times": 85,
    "nyt": 85,
    "the economist": 85,
    "cnbc": 80,
    "marketwatch": 80,
    "forbes": 75,
    "business insider": 70,
    # Tier 2: Government and regulatory sources
    "sec": 95,
    "federal reserve": 95,
    "treasury": 90,
    # Tier 3: Financial data providers
    "yahoo finance": 70,
    "google finance": 70,
    "morningstar": 80,
}

# Emotional/manipulative language patterns for language neutrality scoring (Req 6.4)
EMOTIONAL_PATTERNS = [
    # Urgency patterns
    r"\b(urgent|immediately|act now|don't wait|hurry|limited time|last chance)\b",
    # Hype patterns
    r"\b(guaranteed|100%|risk-free|can't lose|sure thing|easy money|get rich)\b",
    # Fear patterns
    r"\b(crash|collapse|disaster|catastrophe|crisis|panic|plunge|plummet)\b",
    # Greed patterns
    r"\b(massive gains|huge returns|skyrocket|moon|lambo|millionaire|fortune)\b",
    # Manipulation patterns
    r"\b(secret|insider|they don't want you to know|hidden|exclusive tip)\b",
    # Exaggeration patterns
    r"\b(incredible|unbelievable|amazing|revolutionary|game-changer|unprecedented)\b",
    # Pressure patterns
    r"\b(must buy|must sell|everyone is|you're missing out|fomo)\b",
]

# Compiled emotional patterns for efficiency
COMPILED_EMOTIONAL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in EMOTIONAL_PATTERNS]


@dataclass
class TrustScoreResult:
    """Result of trust score computation.
    
    Attributes:
        trust_score: Final trust score (0-100)
        breakdown: Breakdown of the four sub-scores
        deduction_references: References to sources that contributed to deductions
    """
    trust_score: int
    breakdown: TrustScoreBreakdown
    deduction_references: list[Union[DeductionReference, NoCorroborationDeduction]]


class TrustScoreEngine:
    """Computes weighted trust scores from four independently computed sub-scores.
    
    The engine analyzes evidence quality, source credibility, language patterns,
    and cross-source agreement to produce a comprehensive trust assessment.
    
    Attributes:
        weights: The weights for each sub-score component.
    
    Example:
        >>> engine = TrustScoreEngine()
        >>> result = engine.compute(claims, evidence_map, classifications)
        >>> print(result.trust_score)
        75
        >>> print(result.breakdown.source_credibility)
        80
    
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 28.1, 28.2, 28.3, 28.4, 28.7
    """
    
    def __init__(self, weights: TrustScoreWeights | None = None) -> None:
        """Initialize the TrustScoreEngine.
        
        Args:
            weights: Optional custom weights for sub-score computation.
                     Defaults to 0.3, 0.3, 0.2, 0.2 for SC, ES, LN, CSA.
        """
        self.weights = weights or TrustScoreWeights()
    
    def compute(
        self,
        claims: list[Claim],
        evidence: dict[str, EvidenceSet],  # claim_id -> evidence
        classifications: dict[str, ClassificationResult],
    ) -> TrustScoreResult:
        """Compute the trust score for analyzed claims.
        
        Computes four sub-scores and applies the weighted formula:
        Trust_Score = round(SC * 0.3 + ES * 0.3 + LN * 0.2 + CSA * 0.2)
        
        Args:
            claims: List of extracted claims.
            evidence: Mapping of claim_id to evidence set.
            classifications: Mapping of claim_id to classification result.
        
        Returns:
            TrustScoreResult containing the final score, breakdown, and deduction references.
        
        Requirements: 6.1, 6.6, 6.7, 28.1, 28.2, 28.3, 28.7
        """
        if not claims:
            # No claims means no analysis - return neutral score
            return TrustScoreResult(
                trust_score=50,
                breakdown=TrustScoreBreakdown(
                    source_credibility=50,
                    evidence_strength=50,
                    language_neutrality=50,
                    cross_source_agreement=50,
                ),
                deduction_references=[],
            )
        
        deduction_references: list[Union[DeductionReference, NoCorroborationDeduction]] = []
        
        # Aggregate evidence from all claims
        all_evidence = EvidenceSet(results=[], insufficient_evidence=False)
        for claim_id, ev in evidence.items():
            all_evidence.results.extend(ev.results)
            if ev.insufficient_evidence:
                all_evidence.insufficient_evidence = True
        
        # Compute sub-scores (Req 6.2, 6.3, 6.4, 6.5)
        source_credibility = self._compute_source_credibility(all_evidence)
        evidence_strength = self._compute_evidence_strength(all_evidence)
        
        # Language neutrality is computed per-claim and averaged
        language_scores = [self._compute_language_neutrality(claim) for claim in claims]
        language_neutrality = round(sum(language_scores) / len(language_scores)) if language_scores else 50
        
        cross_source_agreement = self._compute_cross_source_agreement(all_evidence)
        
        # Record deduction references for claims (Req 28.1, 28.2, 28.3, 28.7)
        for claim in claims:
            claim_evidence = evidence.get(claim.id, EvidenceSet(results=[], insufficient_evidence=True))
            claim_classification = classifications.get(claim.id)
            
            claim_deductions = self._compute_claim_deductions(
                claim, claim_evidence, claim_classification
            )
            deduction_references.extend(claim_deductions)
        
        # Compute final score using weighted formula (Req 6.1)
        raw_score = (
            source_credibility * self.weights.source_credibility +
            evidence_strength * self.weights.evidence_strength +
            language_neutrality * self.weights.language_neutrality +
            cross_source_agreement * self.weights.cross_source_agreement
        )
        
        # Round and clamp to [0, 100] (Req 6.6)
        trust_score = max(0, min(100, round(raw_score)))
        
        breakdown = TrustScoreBreakdown(
            source_credibility=source_credibility,
            evidence_strength=evidence_strength,
            language_neutrality=language_neutrality,
            cross_source_agreement=cross_source_agreement,
        )
        
        logger.debug(
            f"Trust score computed: {trust_score} "
            f"(SC={source_credibility}, ES={evidence_strength}, "
            f"LN={language_neutrality}, CSA={cross_source_agreement})"
        )
        
        return TrustScoreResult(
            trust_score=trust_score,
            breakdown=breakdown,
            deduction_references=deduction_references,
        )
    
    def _compute_source_credibility(self, evidence: EvidenceSet) -> int:
        """Compute source credibility sub-score based on source reliability.
        
        Evaluates the reliability ratings of sources in the retrieved evidence.
        Known reputable sources receive higher scores.
        
        Args:
            evidence: The evidence set to evaluate.
        
        Returns:
            Source credibility score (0-100).
        
        Requirements: 6.2, 28.4
        """
        if not evidence.results:
            return 30  # Low score for no evidence
        
        credibility_scores = []
        
        for result in evidence.results:
            source_lower = result.source.lower().strip()
            
            # Check against known reputable sources
            source_score = 50  # Default for unknown sources
            for known_source, score in REPUTABLE_SOURCES.items():
                if known_source in source_lower:
                    source_score = score
                    break
            
            # Weight by relevance score
            weighted_score = source_score * result.relevance_score
            credibility_scores.append(weighted_score)
        
        # Average the weighted scores
        avg_score = sum(credibility_scores) / len(credibility_scores)
        
        return max(0, min(100, round(avg_score)))
    
    def _compute_evidence_strength(self, evidence: EvidenceSet) -> int:
        """Compute evidence strength sub-score based on evidence quality.
        
        Evaluates the number and quality of supporting sources retrieved.
        More sources with higher relevance scores indicate stronger evidence.
        
        Args:
            evidence: The evidence set to evaluate.
        
        Returns:
            Evidence strength score (0-100).
        
        Requirements: 6.3
        """
        if evidence.insufficient_evidence or not evidence.results:
            return 20  # Low score for insufficient evidence
        
        num_results = len(evidence.results)
        
        # Base score from number of results (more is better, up to a point)
        # 1 result = 40, 2 = 55, 3 = 65, 4 = 75, 5+ = 80
        if num_results >= 5:
            quantity_score = 80
        elif num_results >= 4:
            quantity_score = 75
        elif num_results >= 3:
            quantity_score = 65
        elif num_results >= 2:
            quantity_score = 55
        else:
            quantity_score = 40
        
        # Quality score from average relevance
        avg_relevance = sum(r.relevance_score for r in evidence.results) / num_results
        quality_score = avg_relevance * 100
        
        # Combine quantity and quality (60% quantity, 40% quality)
        combined_score = quantity_score * 0.6 + quality_score * 0.4
        
        return max(0, min(100, round(combined_score)))
    
    def _compute_language_neutrality(self, claim: Claim) -> int:
        """Compute language neutrality sub-score based on claim text analysis.
        
        Evaluates the sentiment and emotional tone of the claim text.
        Neutral, factual language scores higher; emotional/manipulative language scores lower.
        
        Args:
            claim: The claim to analyze.
        
        Returns:
            Language neutrality score (0-100).
        
        Requirements: 6.4
        """
        text = claim.text.lower()
        
        # Count emotional pattern matches
        emotional_matches = 0
        for pattern in COMPILED_EMOTIONAL_PATTERNS:
            matches = pattern.findall(text)
            emotional_matches += len(matches)
        
        # Start with perfect score and deduct for emotional language
        # Each match deducts 15 points, minimum score is 10
        score = 100 - (emotional_matches * 15)
        
        # Additional checks for excessive punctuation (!!!, ???, etc.)
        excessive_punctuation = len(re.findall(r'[!?]{2,}', claim.text))
        score -= excessive_punctuation * 10
        
        # Check for ALL CAPS words (excluding common acronyms)
        all_caps_words = re.findall(r'\b[A-Z]{4,}\b', claim.text)
        # Filter out common financial acronyms
        common_acronyms = {'NYSE', 'NASDAQ', 'SEC', 'IPO', 'ETF', 'CEO', 'CFO', 'GDP', 'FOMC'}
        non_acronym_caps = [w for w in all_caps_words if w not in common_acronyms]
        score -= len(non_acronym_caps) * 10
        
        return max(10, min(100, score))
    
    def _compute_cross_source_agreement(self, evidence: EvidenceSet) -> int:
        """Compute cross-source agreement sub-score based on source consistency.
        
        Evaluates the consistency of information across retrieved sources.
        Multiple sources agreeing indicates higher reliability.
        
        Args:
            evidence: The evidence set to evaluate.
        
        Returns:
            Cross-source agreement score (0-100).
        
        Requirements: 6.5
        """
        if not evidence.results:
            return 30  # Low score for no evidence
        
        if len(evidence.results) == 1:
            return 50  # Neutral score for single source (can't measure agreement)
        
        # Analyze summaries for agreement/disagreement indicators
        summaries = [r.summary.lower() for r in evidence.results]
        
        # Check for contradiction indicators
        contradiction_keywords = [
            "however", "contrary", "disputes", "contradicts", "denies",
            "refutes", "disagrees", "opposes", "challenges", "questions",
            "false", "incorrect", "inaccurate", "misleading", "debunked"
        ]
        
        contradiction_count = 0
        for summary in summaries:
            for keyword in contradiction_keywords:
                if keyword in summary:
                    contradiction_count += 1
                    break  # Count each summary only once
        
        # Check for agreement indicators
        agreement_keywords = [
            "confirms", "supports", "agrees", "corroborates", "validates",
            "verified", "accurate", "correct", "consistent", "aligns"
        ]
        
        agreement_count = 0
        for summary in summaries:
            for keyword in agreement_keywords:
                if keyword in summary:
                    agreement_count += 1
                    break  # Count each summary only once
        
        # Calculate score based on agreement vs contradiction ratio
        total_sources = len(evidence.results)
        
        # Base score of 70 for multiple sources
        base_score = 70
        
        # Adjust based on agreement/contradiction
        agreement_bonus = (agreement_count / total_sources) * 30
        contradiction_penalty = (contradiction_count / total_sources) * 40
        
        score = base_score + agreement_bonus - contradiction_penalty
        
        return max(0, min(100, round(score)))
    
    def _compute_claim_deductions(
        self,
        claim: Claim,
        evidence: EvidenceSet,
        classification: ClassificationResult | None,
    ) -> list[Union[DeductionReference, NoCorroborationDeduction]]:
        """Compute deduction references for a specific claim.
        
        Records sources that contributed to trust score deductions, either
        from contradicting sources or lack of corroborating evidence.
        
        Args:
            claim: The claim being analyzed.
            evidence: The evidence set for the claim.
            classification: The classification result for the claim.
        
        Returns:
            List of deduction references for the claim.
        
        Requirements: 28.1, 28.2, 28.3, 28.7
        """
        deductions: list[Union[DeductionReference, NoCorroborationDeduction]] = []
        
        # Check if claim has deductions based on classification
        if classification and classification.label in {
            ClassificationLabel.MISLEADING,
            ClassificationLabel.LIKELY_FALSE,
            ClassificationLabel.HARMFUL,
        }:
            # Look for contradicting sources in evidence
            contradiction_keywords = [
                "contradicts", "disputes", "denies", "refutes", "false",
                "incorrect", "inaccurate", "misleading", "debunked", "contrary"
            ]
            
            found_contradiction = False
            for result in evidence.results:
                summary_lower = result.summary.lower()
                
                # Check if this source contradicts the claim
                for keyword in contradiction_keywords:
                    if keyword in summary_lower:
                        # Create deduction reference (Req 28.1, 28.2, 28.3)
                        deduction = DeductionReference(
                            claim_id=claim.id,
                            source_name=result.source,
                            url=f"https://{result.source.lower().replace(' ', '')}.com/article",  # Placeholder URL
                            summary=result.summary,
                            contradiction_rationale=f"This source {keyword}s the claim: {result.summary[:200]}",
                        )
                        deductions.append(deduction)
                        found_contradiction = True
                        break
            
            # If no contradicting sources found, record lack of corroboration (Req 28.7)
            if not found_contradiction:
                if evidence.insufficient_evidence or not evidence.results:
                    deduction = NoCorroborationDeduction(
                        claim_id=claim.id,
                        rationale="Trust score deduction was based on a lack of corroborating evidence. "
                                  "No reliable sources were found to support this claim.",
                    )
                    deductions.append(deduction)
                else:
                    # Evidence exists but doesn't support the claim
                    deduction = NoCorroborationDeduction(
                        claim_id=claim.id,
                        rationale="Trust score deduction was based on insufficient corroborating evidence. "
                                  "Available sources did not provide strong support for this claim.",
                    )
                    deductions.append(deduction)
        
        return deductions
