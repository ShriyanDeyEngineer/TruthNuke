"""TruthNuke Pydantic Models.

This module contains all Phase 1 Pydantic models for the TruthNuke API.
These models are used for:
- API request/response validation
- Data serialization/deserialization
- Type safety throughout the pipeline

Requirements: 2.2, 3.2, 5.1, 6.1, 6.7, 8.2, 14.1, 15.1, 28.1, 28.2, 28.3
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ContentModality(str, Enum):
    """Content type for analysis input.
    
    TEXT is the only supported modality for MVP (Phase 1).
    Other values are defined for forward compatibility with Phase 3.
    """
    TEXT = "TEXT"
    VIDEO = "VIDEO"
    ARTICLE = "ARTICLE"
    SOCIAL_POST = "SOCIAL_POST"
    IMAGE = "IMAGE"


class AnalyzeRequest(BaseModel):
    """Request model for the POST /analyze endpoint.
    
    Attributes:
        text: The text content to analyze. Must be between 1 and 50,000 characters.
        content_type: The type of content being analyzed. Defaults to TEXT.
    
    Requirements: 1.3, 1.4, 8.1, 27.2, 27.3
    """
    text: str = Field(..., min_length=1, max_length=50000)
    content_type: ContentModality = ContentModality.TEXT


class Claim(BaseModel):
    """A single financial claim extracted from user-provided text.
    
    Attributes:
        id: Unique identifier (UUID) for the claim.
        text: The extracted claim text.
        start_index: Starting position of the claim in the original text (0-indexed).
        end_index: Ending position of the claim in the original text (exclusive).
        type: Category of the claim (banking, market, investment, crypto, economic).
        entities: Named entities referenced in the claim.
    
    Requirements: 2.2, 2.3, 2.4
    """
    id: str  # UUID
    text: str
    start_index: int = Field(..., ge=0)
    end_index: int = Field(..., gt=0)
    type: str  # "banking", "market", "investment", "crypto", "economic"
    entities: list[str]


class SearchResult(BaseModel):
    """A single search result from the RAG pipeline.
    
    Attributes:
        title: Title of the source article/document.
        source: Name of the publishing outlet or account.
        summary: Brief description of what the source states.
        timestamp: Publication timestamp in ISO 8601 format.
        relevance_score: Relevance score between 0.0 and 1.0.
        source_type: Type of source ("external" or "benchmark" for Phase 2).
    
    Requirements: 3.2, 4.3
    """
    title: str
    source: str
    summary: str
    timestamp: str  # ISO 8601
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    source_type: str = "external"  # "external" | "benchmark" (Phase 2)


class EvidenceSet(BaseModel):
    """Collection of search results for a claim.
    
    Attributes:
        results: List of search results retrieved for the claim.
        insufficient_evidence: Flag indicating if no evidence was found.
    
    Requirements: 3.4
    """
    results: list[SearchResult]
    insufficient_evidence: bool = False


class ClassificationLabel(str, Enum):
    """Misinformation risk classification labels.
    
    Requirements: 5.1
    """
    VERIFIED = "VERIFIED"
    MISLEADING = "MISLEADING"
    LIKELY_FALSE = "LIKELY_FALSE"
    HARMFUL = "HARMFUL"


class ClassificationResult(BaseModel):
    """Classification result for a single claim.
    
    Attributes:
        claim_id: ID of the claim being classified.
        label: The assigned classification label.
        reasoning: Explanation of the classification decision.
    
    Requirements: 5.1, 5.2
    """
    claim_id: str
    label: ClassificationLabel
    reasoning: str


class TrustScoreWeights(BaseModel):
    """Configurable weights for trust score computation.
    
    The four weights should sum to 1.0 for proper normalization.
    Default values: 0.3, 0.3, 0.2, 0.2
    
    Requirements: 6.1
    """
    source_credibility: float = 0.3
    evidence_strength: float = 0.3
    language_neutrality: float = 0.2
    cross_source_agreement: float = 0.2


class TrustScoreBreakdown(BaseModel):
    """Breakdown of the four trust score components.
    
    Each sub-score is an integer between 0 and 100.
    
    Attributes:
        source_credibility: Score based on reliability of sources (0-100).
        evidence_strength: Score based on quality of supporting evidence (0-100).
        language_neutrality: Score based on sentiment/emotional tone (0-100).
        cross_source_agreement: Score based on consistency across sources (0-100).
    
    Requirements: 6.2, 6.3, 6.4, 6.5, 6.7
    """
    source_credibility: int = Field(..., ge=0, le=100)
    evidence_strength: int = Field(..., ge=0, le=100)
    language_neutrality: int = Field(..., ge=0, le=100)
    cross_source_agreement: int = Field(..., ge=0, le=100)


class DeductionReference(BaseModel):
    """Reference to a source that contributed to a trust score deduction.
    
    Attributes:
        claim_id: ID of the claim this deduction relates to.
        source_name: Name of the publishing outlet or account.
        url: Direct link to the original source material.
        summary: Brief description of what the source states.
        contradiction_rationale: Explanation of how the source contradicts the claim.
    
    Requirements: 28.1, 28.2, 28.3
    """
    claim_id: str
    source_name: str
    url: str
    summary: str
    contradiction_rationale: str


class NoCorroborationDeduction(BaseModel):
    """Deduction record when no corroborating evidence was found.
    
    Used when a trust score deduction is due to lack of supporting evidence
    rather than directly contradicting sources.
    
    Attributes:
        claim_id: ID of the claim this deduction relates to.
        rationale: Explanation that deduction was due to lack of corroborating evidence.
    
    Requirements: 28.7
    """
    claim_id: str
    rationale: str  # Explains deduction was due to lack of corroborating evidence


class ClaimAnalysis(BaseModel):
    """Complete analysis result for a single claim.
    
    Attributes:
        claim: The extracted claim.
        classification: The classification result for the claim.
        evidence: The evidence set retrieved for the claim.
        deduction_references: References to sources that contributed to deductions.
    
    Requirements: 8.2, 28.1
    """
    claim: Claim
    classification: ClassificationResult
    evidence: EvidenceSet
    deduction_references: list[DeductionReference | NoCorroborationDeduction]


class RiskAssessment(BaseModel):
    """Multi-signal risk assessment for the analyzed content.

    Layered scoring from keywords, phrase patterns, and claim analysis.
    """
    risk_score: int = Field(..., ge=0, description="Composite risk score")
    risk_level: str = Field(..., description="low | medium | high")
    signals: dict = Field(default_factory=dict, description="Breakdown of keyword, phrase, and claim signals")
    explanation: str = Field(default="", description="Human-readable risk explanation")


class AnalysisResponse(BaseModel):
    """Response model for the POST /analyze endpoint.
    
    Attributes:
        claims: List of analyzed claims with their classifications and evidence.
        overall_classification: Overall classification for the content (None if no claims).
        trust_score: Overall trust score 0-100 (None if no claims).
        trust_score_breakdown: Breakdown of the four trust score components.
        explanation: Natural-language explanation of the analysis.
        sources: All retrieved sources across all claims.
        disclaimer: Legal disclaimer about automated assessments.
    
    Requirements: 8.2, 11.1, 12.1
    """
    claims: list[ClaimAnalysis]
    overall_classification: ClassificationLabel | None  # None when no claims found
    trust_score: int | None  # None when no claims found, else 0-100
    trust_score_breakdown: TrustScoreBreakdown | None
    explanation: str
    sources: list[SearchResult]
    risk_assessment: Optional[RiskAssessment] = None
    disclaimer: str = (
        "This analysis is an automated assessment and not a definitive judgment "
        "of truth. Please review the referenced sources to form your own conclusions."
    )


class ErrorResponse(BaseModel):
    """Error response model for API errors.
    
    Attributes:
        error: Error type identifier (e.g., "validation_error", "internal_error").
        detail: Optional detailed error message.
    
    Requirements: 8.3, 8.4
    """
    error: str
    detail: Optional[str] = None
