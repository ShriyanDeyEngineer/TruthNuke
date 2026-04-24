"""Analyzer Orchestrator for TruthNuke.

This module provides the central orchestrator that coordinates the full analysis
pipeline: validate → normalize → extract → retrieve → classify → score → explain.

Requirements: 1.1, 1.2, 1.3, 1.4, 8.2, 12.1, 12.3, 28.1
"""

import logging
import re
from typing import TYPE_CHECKING, Union

from app.models.schemas import (
    AnalysisResponse,
    Claim,
    ClaimAnalysis,
    ClassificationLabel,
    ClassificationResult,
    DeductionReference,
    EvidenceSet,
    NoCorroborationDeduction,
    RiskAssessment,
    SearchResult,
    TrustScoreBreakdown,
)

if TYPE_CHECKING:
    from app.services.claim_extractor import ClaimExtractor
    from app.services.classifier import Classifier
    from app.services.explanation_engine import ExplanationEngine
    from app.services.rag_pipeline import RAGPipeline
    from app.services.trust_score_engine import TrustScoreEngine


logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails.
    
    This error is raised when:
    - Text is empty or contains only whitespace (Req 1.3)
    - Text exceeds the maximum allowed length of 50,000 characters (Req 1.4)
    
    Attributes:
        message: A descriptive error message explaining the validation failure.
    
    Requirements: 1.3, 1.4
    """
    
    def __init__(self, message: str) -> None:
        """Initialize the ValidationError.
        
        Args:
            message: A descriptive error message.
        """
        self.message = message
        super().__init__(self.message)


class Analyzer:
    """Central orchestrator for the TruthNuke analysis pipeline.
    
    The Analyzer coordinates the full analysis pipeline:
    1. Validate input text (reject empty/whitespace-only/oversized text)
    2. Normalize text (trim whitespace, collapse consecutive whitespace)
    3. Extract claims using LLM-based claim extraction
    4. Retrieve evidence for each claim via RAG pipeline
    5. Classify each claim for misinformation risk
    6. Compute trust scores
    7. Generate explanations
    
    Attributes:
        claim_extractor: Service for extracting claims from text.
        rag_pipeline: Service for retrieving evidence.
        classifier: Service for classifying claims.
        trust_score_engine: Service for computing trust scores.
        explanation_engine: Service for generating explanations.
        max_input_length: Maximum allowed input text length (default 50,000).
    
    Example:
        >>> analyzer = Analyzer(
        ...     claim_extractor=claim_extractor,
        ...     rag_pipeline=rag_pipeline,
        ...     classifier=classifier,
        ...     trust_score_engine=trust_score_engine,
        ...     explanation_engine=explanation_engine,
        ... )
        >>> response = await analyzer.analyze("The stock rose 10% yesterday.")
    
    Requirements: 1.1, 1.2, 1.3, 1.4, 8.2, 12.1, 12.3, 28.1
    """
    
    # Maximum allowed input text length in characters
    MAX_INPUT_LENGTH = 50000
    
    def __init__(
        self,
        claim_extractor: "ClaimExtractor | None" = None,
        rag_pipeline: "RAGPipeline | None" = None,
        classifier: "Classifier | None" = None,
        trust_score_engine: "TrustScoreEngine | None" = None,
        explanation_engine: "ExplanationEngine | None" = None,
        max_input_length: int = MAX_INPUT_LENGTH,
    ) -> None:
        """Initialize the Analyzer with service dependencies.
        
        Args:
            claim_extractor: Service for extracting claims from text.
            rag_pipeline: Service for retrieving evidence.
            classifier: Service for classifying claims.
            trust_score_engine: Service for computing trust scores.
            explanation_engine: Service for generating explanations.
            max_input_length: Maximum allowed input text length (default 50,000).
        """
        self.claim_extractor = claim_extractor
        self.rag_pipeline = rag_pipeline
        self.classifier = classifier
        self.trust_score_engine = trust_score_engine
        self.explanation_engine = explanation_engine
        self.max_input_length = max_input_length
    
    def _validate(self, text: str) -> None:
        """Validate input text before processing.
        
        Validation rules:
        1. Text must not be empty or whitespace-only (Req 1.3)
        2. Text must not exceed 50,000 characters (Req 1.4)
        
        Args:
            text: The raw input text to validate.
        
        Raises:
            ValidationError: If text is empty, whitespace-only, or exceeds
                the maximum allowed length.
        
        Example:
            >>> analyzer._validate("Valid text")  # OK
            >>> analyzer._validate("")  # Raises ValidationError
            >>> analyzer._validate("   ")  # Raises ValidationError
            >>> analyzer._validate("x" * 60000)  # Raises ValidationError
        
        Requirements: 1.3, 1.4
        """
        # Check for empty or whitespace-only text (Req 1.3)
        if not text or not text.strip():
            raise ValidationError(
                "Non-empty text is required. Please provide text containing "
                "financial claims to analyze."
            )
        
        # Check for text exceeding maximum length (Req 1.4)
        if len(text) > self.max_input_length:
            raise ValidationError(
                f"Text exceeds maximum allowed length of {self.max_input_length:,} "
                f"characters. Received {len(text):,} characters."
            )
    
    def _normalize(self, text: str) -> str:
        """Normalize input text for consistent processing.
        
        Normalization steps:
        1. Trim leading and trailing whitespace
        2. Collapse consecutive whitespace characters into single spaces
        
        This ensures consistent text format for downstream processing
        regardless of the original formatting.
        
        Args:
            text: The raw input text to normalize.
        
        Returns:
            The normalized text with trimmed edges and collapsed whitespace.
        
        Example:
            >>> analyzer._normalize("  Hello   world  ")
            'Hello world'
            >>> analyzer._normalize("Line1\\n\\n\\nLine2")
            'Line1 Line2'
            >>> analyzer._normalize("\\t\\tTabbed\\t\\tcontent")
            'Tabbed content'
        
        Requirements: 1.2
        """
        # Trim leading and trailing whitespace
        trimmed = text.strip()
        
        # Collapse consecutive whitespace characters (spaces, tabs, newlines)
        # into single spaces using regex
        normalized = re.sub(r'\s+', ' ', trimmed)
        
        return normalized
    
    async def analyze(self, text: str) -> AnalysisResponse:
        """Analyze text for financial misinformation.
        
        This method orchestrates the full analysis pipeline:
        1. Validate input text (reject empty/whitespace-only/oversized)
        2. Normalize text (trim whitespace, collapse consecutive whitespace)
        3. Extract claims using LLM-based claim extraction
        4. Retrieve evidence for each claim via RAG pipeline
        5. Classify each claim for misinformation risk
        6. Compute trust scores
        7. Generate explanations
        
        If the LLM is unavailable, falls back to rule-based analysis using
        keyword detection and risk scoring.
        
        Args:
            text: The raw input text containing financial claims to analyze.
        
        Returns:
            AnalysisResponse containing the analysis results.
        
        Raises:
            ValidationError: If text is empty, whitespace-only, or exceeds
                the maximum allowed length.
        
        Requirements: 1.1, 1.2, 1.3, 1.4, 8.2, 12.1, 12.3, 28.1
        """
        # Step 1: Validate input text (Req 1.3, 1.4)
        self._validate(text)
        
        # Step 2: Normalize text (Req 1.2)
        normalized_text = self._normalize(text)
        
        logger.info(f"Starting analysis of text ({len(normalized_text)} chars)")
        
        # Step 3: Extract claims with a timeout (Req 2.1)
        # If the LLM is slow, fall back to rule-based analysis quickly.
        claims: list[Claim] = []
        if self.claim_extractor:
            import asyncio
            try:
                claims = await asyncio.wait_for(
                    self.claim_extractor.extract_claims(normalized_text),
                    timeout=12.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Claim extraction timed out, using fallback analysis")
                return self._fallback_analysis(normalized_text)
            except Exception as e:
                logger.warning(f"LLM claim extraction failed, using fallback: {e}")
                return self._fallback_analysis(normalized_text)
        
            # Limit to 3 most important claims to keep response times reasonable
            if len(claims) > 3:
                logger.info(f"Limiting {len(claims)} claims to top 3")
                claims = claims[:3]
            logger.info(f"Extracted {len(claims)} claims")
        
        # If no claims found (LLM failed or no financial content), use rule-based fallback
        if not claims:
            return self._fallback_analysis(normalized_text)
        
        # Step 4: Retrieve evidence for all claims in parallel (Req 3.1)
        evidence_map: dict[str, EvidenceSet] = {}
        all_sources: list[SearchResult] = []
        
        if self.rag_pipeline:
            import asyncio
            
            async def _retrieve_one(claim: Claim) -> tuple[str, EvidenceSet]:
                evidence = await self.rag_pipeline.retrieve_evidence(claim)
                return claim.id, evidence
            
            results = await asyncio.gather(
                *[_retrieve_one(c) for c in claims],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Evidence retrieval failed: {result}")
                    continue
                claim_id, evidence = result
                evidence_map[claim_id] = evidence
                all_sources.extend(evidence.results)
                logger.debug(
                    f"Retrieved {len(evidence.results)} sources for claim {claim_id}"
                )
            # Fill in empty evidence for any claims that failed
            for claim in claims:
                if claim.id not in evidence_map:
                    evidence_map[claim.id] = EvidenceSet(
                        results=[], insufficient_evidence=True
                    )
        else:
            # No RAG pipeline - use empty evidence
            for claim in claims:
                evidence_map[claim.id] = EvidenceSet(
                    results=[], insufficient_evidence=True
                )
        
        # Step 5: Classify each claim in parallel (Req 5.1)
        classifications: dict[str, ClassificationResult] = {}
        
        if self.classifier:
            import asyncio
            
            async def _classify_one(claim: Claim) -> tuple[str, ClassificationResult]:
                evidence = evidence_map.get(
                    claim.id, EvidenceSet(results=[], insufficient_evidence=True)
                )
                result = await self.classifier.classify(claim, evidence)
                return claim.id, result
            
            results = await asyncio.gather(
                *[_classify_one(c) for c in claims],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Classification failed for a claim: {result}")
                    continue
                claim_id, classification = result
                classifications[claim_id] = classification
                logger.debug(
                    f"Classified claim {claim_id} as {classification.label.value}"
                )
        else:
            # No classifier - use default classification
            for claim in claims:
                classifications[claim.id] = ClassificationResult(
                    claim_id=claim.id,
                    label=ClassificationLabel.MISLEADING,
                    reasoning="Classification service not available.",
                )
        
        # Step 6: Compute trust scores (Req 6.1)
        trust_score: int | None = None
        trust_score_breakdown: TrustScoreBreakdown | None = None
        deduction_refs_by_claim: dict[
            str, list[Union[DeductionReference, NoCorroborationDeduction]]
        ] = {}
        
        if self.trust_score_engine:
            score_result = self.trust_score_engine.compute(
                claims, evidence_map, classifications
            )
            trust_score = score_result.trust_score
            trust_score_breakdown = score_result.breakdown
            
            # Group deduction references by claim_id
            for ref in score_result.deduction_references:
                claim_id = ref.claim_id
                if claim_id not in deduction_refs_by_claim:
                    deduction_refs_by_claim[claim_id] = []
                deduction_refs_by_claim[claim_id].append(ref)
            
            logger.info(f"Computed trust score: {trust_score}")
        else:
            # No trust score engine - use default
            trust_score = 50
            trust_score_breakdown = TrustScoreBreakdown(
                source_credibility=50,
                evidence_strength=50,
                language_neutrality=50,
                cross_source_agreement=50,
            )
        
        # Step 7: Generate explanations (Req 7.1)
        explanation = ""
        
        if self.explanation_engine and trust_score_breakdown:
            if claims:
                first_claim = claims[0]
                first_classification = classifications.get(first_claim.id)
                first_evidence = evidence_map.get(
                    first_claim.id, EvidenceSet(results=[], insufficient_evidence=True)
                )
                
                if first_classification:
                    try:
                        explanation = await self.explanation_engine.generate_explanation(
                            claim=first_claim,
                            classification=first_classification,
                            trust_score=trust_score or 50,
                            trust_score_breakdown=trust_score_breakdown,
                            evidence=first_evidence,
                        )
                    except Exception as e:
                        logger.warning(f"Explanation generation failed, using default: {e}")
        
        if not explanation:
            explanation = self._generate_default_explanation(
                claims, classifications, trust_score
            )
        
        # Build claim analysis results (Req 8.2, 28.1)
        claim_analyses: list[ClaimAnalysis] = []
        
        for claim in claims:
            classification = classifications.get(claim.id)
            evidence = evidence_map.get(
                claim.id, EvidenceSet(results=[], insufficient_evidence=True)
            )
            deduction_refs = deduction_refs_by_claim.get(claim.id, [])
            
            if classification:
                claim_analysis = ClaimAnalysis(
                    claim=claim,
                    classification=classification,
                    evidence=evidence,
                    deduction_references=deduction_refs,
                )
                claim_analyses.append(claim_analysis)
        
        # Step 8: Compute risk assessment (layered signal scoring)
        from app.services.risk_scorer import compute_risk_score
        risk_result = compute_risk_score(normalized_text, claims, classifications)
        risk_assessment = RiskAssessment(
            risk_score=risk_result.risk_score,
            risk_level=risk_result.risk_level,
            signals=risk_result.signals,
            explanation=risk_result.explanation,
        )
        
        # Determine overall classification (most severe label)
        overall_classification = self._determine_overall_classification(classifications)
        
        # Deduplicate sources
        unique_sources = self._deduplicate_sources(all_sources)
        
        logger.info(
            f"Analysis complete: {len(claim_analyses)} claims, "
            f"trust_score={trust_score}, classification={overall_classification}"
        )
        
        return AnalysisResponse(
            claims=claim_analyses,
            overall_classification=overall_classification,
            trust_score=trust_score,
            trust_score_breakdown=trust_score_breakdown,
            explanation=explanation,
            sources=unique_sources,
            risk_assessment=risk_assessment,
        )
    
    def _determine_overall_classification(
        self, classifications: dict[str, ClassificationResult]
    ) -> ClassificationLabel | None:
        """Determine the overall classification from individual claim classifications.
        
        Uses the most severe classification label as the overall classification.
        Severity order: HARMFUL > LIKELY_FALSE > MISLEADING > VERIFIED
        
        Args:
            classifications: Mapping of claim_id to classification result.
        
        Returns:
            The most severe classification label, or None if no classifications.
        """
        if not classifications:
            return None
        
        # Severity ranking (higher = more severe)
        severity = {
            ClassificationLabel.VERIFIED: 0,
            ClassificationLabel.MISLEADING: 1,
            ClassificationLabel.LIKELY_FALSE: 2,
            ClassificationLabel.HARMFUL: 3,
        }
        
        most_severe: ClassificationLabel | None = None
        max_severity = -1
        
        for result in classifications.values():
            label_severity = severity.get(result.label, 0)
            if label_severity > max_severity:
                max_severity = label_severity
                most_severe = result.label
        
        return most_severe
    
    def _deduplicate_sources(
        self, sources: list[SearchResult]
    ) -> list[SearchResult]:
        """Deduplicate sources by title and source name.
        
        Args:
            sources: List of search results that may contain duplicates.
        
        Returns:
            Deduplicated list of search results.
        """
        seen: set[tuple[str, str]] = set()
        unique: list[SearchResult] = []
        
        for source in sources:
            key = (source.title, source.source)
            if key not in seen:
                seen.add(key)
                unique.append(source)
        
        return unique
    
    def _generate_default_explanation(
        self,
        claims: list[Claim],
        classifications: dict[str, ClassificationResult],
        trust_score: int | None,
    ) -> str:
        """Generate a default explanation when the explanation engine is unavailable.
        
        Args:
            claims: List of extracted claims.
            classifications: Mapping of claim_id to classification result.
            trust_score: The computed trust score.
        
        Returns:
            A default explanation string.
        """
        num_claims = len(claims)
        
        if trust_score is None:
            return (
                f"Analysis identified {num_claims} financial claim(s) in the text. "
                "Please review the individual claim classifications and sources "
                "to form your own conclusions."
            )
        
        if trust_score >= 70:
            trust_level = "relatively high"
            advice = "The claims appear to be generally supported by available evidence."
        elif trust_score >= 40:
            trust_level = "moderate"
            advice = "Some claims may require additional verification."
        else:
            trust_level = "low"
            advice = "Exercise caution and verify claims through additional sources."
        
        return (
            f"Analysis identified {num_claims} financial claim(s) with a {trust_level} "
            f"trust score of {trust_score}/100. {advice} "
            "Please review the referenced sources to form your own conclusions."
        )
    
    def _fallback_analysis(self, text: str) -> AnalysisResponse:
        """Produce a rule-based analysis when the LLM is unavailable.
        
        Uses keyword detection, phrase pattern matching, and risk scoring
        to provide a useful result without any LLM calls.
        
        Args:
            text: The normalized input text.
        
        Returns:
            AnalysisResponse with rule-based scores and explanation.
        """
        from app.services.risk_scorer import (
            compute_risk_score,
            scan_keywords,
            scan_phrases,
        )
        
        risk_result = compute_risk_score(text, claims=[], classifications=None)
        kw = scan_keywords(text)
        phrases = scan_phrases(text)
        
        # Derive a trust score from the risk score (inverse relationship)
        # risk 0 → trust 75, risk 6+ → trust 25
        trust_score = max(20, min(80, 75 - risk_result.risk_score * 5))
        
        # Build explanation from signals
        parts = []
        if risk_result.risk_level == "high":
            parts.append(
                "This content contains several high-risk signals commonly "
                "associated with misleading financial advice."
            )
        elif risk_result.risk_level == "medium":
            parts.append(
                "This content contains some signals that warrant caution."
            )
        else:
            parts.append(
                "This content does not show strong signals of financial misinformation."
            )
        
        if kw.hype:
            parts.append(f"Hype language detected: {', '.join(kw.hype[:4])}.")
        if phrases:
            parts.append(f"Risky phrases found: {', '.join(phrases[:3])}.")
        if kw.neutral:
            parts.append("Some neutral/institutional language is present, which is a positive sign.")
        
        parts.append(
            "Note: This is a quick rule-based analysis. "
            "Full AI-powered analysis was unavailable."
        )
        
        explanation = " ".join(parts)
        
        risk_assessment = RiskAssessment(
            risk_score=risk_result.risk_score,
            risk_level=risk_result.risk_level,
            signals=risk_result.signals,
            explanation=risk_result.explanation,
        )
        
        breakdown = TrustScoreBreakdown(
            source_credibility=50,
            evidence_strength=50,
            language_neutrality=max(20, 80 - len(kw.hype) * 15),
            cross_source_agreement=50,
        )
        
        logger.info(
            f"Fallback analysis complete: trust_score={trust_score}, "
            f"risk={risk_result.risk_level}"
        )
        
        return AnalysisResponse(
            claims=[],
            overall_classification=None,
            trust_score=trust_score,
            trust_score_breakdown=breakdown,
            explanation=explanation,
            sources=[],
            risk_assessment=risk_assessment,
        )
    
    def _generate_default_explanation(
        self,
        claims: list[Claim],
        classifications: dict[str, ClassificationResult],
        trust_score: int | None,
    ) -> str:
        """Generate a default explanation when the explanation engine is unavailable.
        
        Args:
            claims: List of extracted claims.
            classifications: Mapping of claim_id to classification result.
            trust_score: The computed trust score.
        
        Returns:
            A default explanation string.
        """
        num_claims = len(claims)
        
        if trust_score is None:
            return (
                f"Analysis identified {num_claims} financial claim(s) in the text. "
                "Please review the individual claim classifications and sources "
                "to form your own conclusions."
            )
        
        if trust_score >= 70:
            trust_level = "relatively high"
            advice = "The claims appear to be generally supported by available evidence."
        elif trust_score >= 40:
            trust_level = "moderate"
            advice = "Some claims may require additional verification."
        else:
            trust_level = "low"
            advice = "Exercise caution and verify claims through additional sources."
        
        return (
            f"Analysis identified {num_claims} financial claim(s) with a {trust_level} "
            f"trust score of {trust_score}/100. {advice} "
            "Please review the referenced sources to form your own conclusions."
        )
