/**
 * TruthNuke API TypeScript Types
 *
 * This module contains TypeScript interfaces mirroring the backend Pydantic models.
 * These types ensure type safety between frontend and backend communication.
 *
 * Requirements: 8.2, 10.1, 10.2, 10.3, 10.4
 */

/**
 * Content type for analysis input.
 *
 * TEXT is the only supported modality for MVP (Phase 1).
 * Other values are defined for forward compatibility with Phase 3.
 */
export enum ContentModality {
  TEXT = "TEXT",
  VIDEO = "VIDEO",
  ARTICLE = "ARTICLE",
  SOCIAL_POST = "SOCIAL_POST",
  IMAGE = "IMAGE",
}

/**
 * Request model for the POST /analyze endpoint.
 *
 * Requirements: 1.3, 1.4, 8.1, 27.2, 27.3
 */
export interface AnalyzeRequest {
  /** The text content to analyze. Must be between 1 and 50,000 characters. */
  text: string;
  /** The type of content being analyzed. Defaults to TEXT. */
  content_type?: ContentModality;
}

/**
 * A single financial claim extracted from user-provided text.
 *
 * Requirements: 2.2, 2.3, 2.4
 */
export interface Claim {
  /** Unique identifier (UUID) for the claim. */
  id: string;
  /** The extracted claim text. */
  text: string;
  /** Starting position of the claim in the original text (0-indexed). */
  start_index: number;
  /** Ending position of the claim in the original text (exclusive). */
  end_index: number;
  /** Category of the claim: "banking", "market", "investment", "crypto", "economic". */
  type: string;
  /** Named entities referenced in the claim. */
  entities: string[];
}

/**
 * A single search result from the RAG pipeline.
 *
 * Requirements: 3.2, 4.3
 */
export interface SearchResult {
  /** Title of the source article/document. */
  title: string;
  /** Name of the publishing outlet or account. */
  source: string;
  /** Brief description of what the source states. */
  summary: string;
  /** Publication timestamp in ISO 8601 format. */
  timestamp: string;
  /** Relevance score between 0.0 and 1.0. */
  relevance_score: number;
  /** Type of source: "external" or "benchmark" (Phase 2). */
  source_type?: string;
}

/**
 * Collection of search results for a claim.
 *
 * Requirements: 3.4
 */
export interface EvidenceSet {
  /** List of search results retrieved for the claim. */
  results: SearchResult[];
  /** Flag indicating if no evidence was found. */
  insufficient_evidence: boolean;
}

/**
 * Misinformation risk classification labels.
 *
 * Requirements: 5.1
 */
export enum ClassificationLabel {
  VERIFIED = "VERIFIED",
  MISLEADING = "MISLEADING",
  LIKELY_FALSE = "LIKELY_FALSE",
  HARMFUL = "HARMFUL",
}

/**
 * Classification result for a single claim.
 *
 * Requirements: 5.1, 5.2
 */
export interface ClassificationResult {
  /** ID of the claim being classified. */
  claim_id: string;
  /** The assigned classification label. */
  label: ClassificationLabel;
  /** Explanation of the classification decision. */
  reasoning: string;
}

/**
 * Breakdown of the four trust score components.
 *
 * Each sub-score is an integer between 0 and 100.
 *
 * Requirements: 6.2, 6.3, 6.4, 6.5, 6.7
 */
export interface TrustScoreBreakdown {
  /** Score based on reliability of sources (0-100). */
  source_credibility: number;
  /** Score based on quality of supporting evidence (0-100). */
  evidence_strength: number;
  /** Score based on sentiment/emotional tone (0-100). */
  language_neutrality: number;
  /** Score based on consistency across sources (0-100). */
  cross_source_agreement: number;
}

/**
 * Reference to a source that contributed to a trust score deduction.
 *
 * Requirements: 28.1, 28.2, 28.3
 */
export interface DeductionReference {
  /** ID of the claim this deduction relates to. */
  claim_id: string;
  /** Name of the publishing outlet or account. */
  source_name: string;
  /** Direct link to the original source material. */
  url: string;
  /** Brief description of what the source states. */
  summary: string;
  /** Explanation of how the source contradicts the claim. */
  contradiction_rationale: string;
}

/**
 * Deduction record when no corroborating evidence was found.
 *
 * Used when a trust score deduction is due to lack of supporting evidence
 * rather than directly contradicting sources.
 *
 * Requirements: 28.7
 */
export interface NoCorroborationDeduction {
  /** ID of the claim this deduction relates to. */
  claim_id: string;
  /** Explanation that deduction was due to lack of corroborating evidence. */
  rationale: string;
}

/**
 * Type guard to check if a deduction is a DeductionReference.
 */
export function isDeductionReference(
  deduction: DeductionReference | NoCorroborationDeduction
): deduction is DeductionReference {
  return "source_name" in deduction && "url" in deduction;
}

/**
 * Type guard to check if a deduction is a NoCorroborationDeduction.
 */
export function isNoCorroborationDeduction(
  deduction: DeductionReference | NoCorroborationDeduction
): deduction is NoCorroborationDeduction {
  return "rationale" in deduction && !("source_name" in deduction);
}

/**
 * Complete analysis result for a single claim.
 *
 * Requirements: 8.2, 28.1
 */
export interface ClaimAnalysis {
  /** The extracted claim. */
  claim: Claim;
  /** The classification result for the claim. */
  classification: ClassificationResult;
  /** The evidence set retrieved for the claim. */
  evidence: EvidenceSet;
  /** References to sources that contributed to deductions. */
  deduction_references: (DeductionReference | NoCorroborationDeduction)[];
}

/**
 * Response model for the POST /analyze endpoint.
 *
 * Requirements: 8.2, 11.1, 12.1
 */
export interface AnalysisResponse {
  /** List of analyzed claims with their classifications and evidence. */
  claims: ClaimAnalysis[];
  /** Overall classification for the content (null if no claims). */
  overall_classification: ClassificationLabel | null;
  /** Overall trust score 0-100 (null if no claims). */
  trust_score: number | null;
  /** Breakdown of the four trust score components. */
  trust_score_breakdown: TrustScoreBreakdown | null;
  /** Natural-language explanation of the analysis. */
  explanation: string;
  /** All retrieved sources across all claims. */
  sources: SearchResult[];
  /** Legal disclaimer about automated assessments. */
  disclaimer: string;
}

/**
 * Error response model for API errors.
 *
 * Requirements: 8.3, 8.4
 */
export interface ErrorResponse {
  /** Error type identifier (e.g., "validation_error", "internal_error"). */
  error: string;
  /** Optional detailed error message. */
  detail?: string | null;
}
