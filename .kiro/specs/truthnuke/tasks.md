# Implementation Plan: TruthNuke

## Overview

TruthNuke is a full-stack AI-powered financial misinformation detector. This implementation plan covers the Phase 1 MVP: text input, LLM-based claim extraction, prompt-driven classification, heuristic trust scoring, explanation generation, mock search provider, REST API, and React frontend with trust meter and explanation panel. Phase 2, Phase 3, and multi-modal features are included as optional tasks.

The backend is Python (FastAPI + Pydantic), the frontend is React/Next.js (TypeScript), and property-based tests use Hypothesis.

## Tasks

- [ ] 1. Project setup and scaffolding
  - [x] 1.1 Initialize Python backend project
    - Create `backend/` directory with FastAPI project structure
    - Set up `pyproject.toml` or `requirements.txt` with dependencies: `fastapi`, `uvicorn`, `pydantic`, `openai`, `httpx`, `python-dotenv`, `hypothesis` (dev)
    - Create `backend/app/` package with `__init__.py`, `main.py` (FastAPI app entry point)
    - Create sub-packages: `backend/app/models/`, `backend/app/services/`, `backend/app/api/`
    - Add `.env.example` with placeholder keys: `LLM_API_KEY`, `LLM_MODEL`, `TOP_K`, `MAX_INPUT_LENGTH`, `TRUST_SCORE_WEIGHTS`, `CORS_ORIGIN`
    - _Requirements: 13.1, 13.2_

  - [x] 1.2 Initialize React/Next.js frontend project
    - Create `frontend/` directory with Next.js + TypeScript scaffolding (`npx create-next-app@latest`)
    - Install dependencies: `axios` or `fetch` wrapper for API calls
    - Create component directory structure: `frontend/src/components/`, `frontend/src/pages/`, `frontend/src/types/`
    - _Requirements: 9.1_

  - [x] 1.3 Set up testing infrastructure
    - Configure `pytest` with Hypothesis for backend property-based and unit tests
    - Create `tests/` directory structure: `tests/property/`, `tests/unit/`, `tests/integration/`
    - Configure React Testing Library and Jest for frontend tests
    - _Requirements: 14.1, 15.1_

- [ ] 2. Core data models and types
  - [x] 2.1 Implement backend Pydantic models
    - Create `backend/app/models/schemas.py` with all Phase 1 Pydantic models:
      - `ContentModality` enum (TEXT only for MVP, other values defined for forward compatibility)
      - `AnalyzeRequest` with `text` (min_length=1, max_length=50000) and `content_type` (default TEXT)
      - `Claim` with `id`, `text`, `start_index` (ge=0), `end_index` (gt=0), `type`, `entities`
      - `SearchResult` with `title`, `source`, `summary`, `timestamp`, `relevance_score` (0.0–1.0)
      - `EvidenceSet` with `results` list and `insufficient_evidence` flag
      - `ClassificationLabel` enum: VERIFIED, MISLEADING, LIKELY_FALSE, HARMFUL
      - `ClassificationResult` with `claim_id`, `label`, `reasoning`
      - `TrustScoreWeights` with defaults (0.3, 0.3, 0.2, 0.2)
      - `TrustScoreBreakdown` with four sub-scores (0–100 each)
      - `DeductionReference` with `claim_id`, `source_name`, `url`, `summary`, `contradiction_rationale`
      - `NoCorroborationDeduction` with `claim_id`, `rationale`
      - `ClaimAnalysis` with `claim`, `classification`, `evidence`, `deduction_references`
      - `AnalysisResponse` with `claims`, `overall_classification`, `trust_score`, `trust_score_breakdown`, `explanation`, `sources`, `disclaimer`
      - `ErrorResponse` with `error` and optional `detail`
    - _Requirements: 2.2, 3.2, 5.1, 6.1, 6.7, 8.2, 14.1, 15.1, 28.1, 28.2, 28.3_

  - [x] 2.2 Implement frontend TypeScript types
    - Create `frontend/src/types/api.ts` with TypeScript interfaces mirroring backend models:
      - `AnalyzeRequest`, `Claim`, `SearchResult`, `EvidenceSet`, `ClassificationLabel`, `ClassificationResult`, `TrustScoreBreakdown`, `DeductionReference`, `NoCorroborationDeduction`, `ClaimAnalysis`, `AnalysisResponse`, `ErrorResponse`
    - _Requirements: 8.2, 10.1, 10.2, 10.3, 10.4_

  - [x] 2.3 Write property tests for Claim serialization round-trip
    - **Property 10: Claim serialization round-trip**
    - Generate random valid Claim objects using Hypothesis strategies, serialize to JSON, deserialize back, assert equivalence
    - **Validates: Requirements 14.1, 14.2**

  - [x] 2.4 Write property tests for TrustScore serialization round-trip
    - **Property 11: TrustScore serialization round-trip**
    - Generate random valid TrustScoreBreakdown objects, serialize to JSON, deserialize back, assert equivalence
    - **Validates: Requirements 15.1, 15.2**

- [x] 3. Checkpoint - Verify models and project structure
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. LLM client and configuration management
  - [x] 4.1 Implement configuration module
    - Create `backend/app/config.py` with a Pydantic `Settings` class reading from environment variables:
      - `LLM_API_KEY` (required — app fails to start if missing)
      - `LLM_MODEL` (default: `gpt-4o-mini`)
      - `LLM_TIMEOUT` (default: 30.0)
      - `LLM_MAX_RETRIES` (default: 3)
      - `TOP_K` (default: 5)
      - `MAX_INPUT_LENGTH` (default: 50000)
      - `TRUST_SCORE_WEIGHTS` (default: "0.3,0.3,0.2,0.2")
      - `CORS_ORIGIN` (default: `http://localhost:3000`)
    - Validate that `LLM_API_KEY` is set at startup; raise descriptive error if missing
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 4.2 Implement LLM client wrapper
    - Create `backend/app/services/llm_client.py` with `LLMClient` class
    - Implement `complete(prompt, system_prompt)` → returns response text
    - Implement `complete_json(prompt, system_prompt)` → parses response as JSON dict
    - Add exponential backoff retry logic (max 3 retries, base 1s, multiplier 2x, max 10s)
    - Handle retryable errors: timeout, 429, 500, 502, 503
    - Raise `LLMUnavailableError` after retries exhausted
    - Raise `LLMParsingError` if JSON response is invalid
    - _Requirements: 12.3, 14.3_

- [ ] 5. Input handling and normalization
  - [x] 5.1 Implement Analyzer orchestrator with validation and normalization
    - Create `backend/app/services/analyzer.py` with `Analyzer` class
    - Implement `_validate(text)`: reject empty/whitespace-only text (raise `ValidationError`), reject text > 50,000 chars
    - Implement `_normalize(text)`: trim leading/trailing whitespace, collapse consecutive whitespace to single spaces
    - Wire validation and normalization as the first steps of the `analyze()` method
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 5.2 Write property tests for text normalization
    - **Property 1: Text normalization preserves content and removes excess whitespace**
    - Generate random strings with mixed whitespace; assert normalized output has no leading/trailing whitespace, no consecutive whitespace, and preserves all non-whitespace content in order
    - **Validates: Requirements 1.2**

  - [x] 5.3 Write property tests for whitespace-only rejection
    - **Property 2: Whitespace-only strings are rejected**
    - Generate strings composed entirely of whitespace characters; assert validation raises error
    - **Validates: Requirements 1.3**

- [ ] 6. Claim extraction module
  - [x] 6.1 Implement Claim Extractor
    - Create `backend/app/services/claim_extractor.py` with `ClaimExtractor` class
    - Implement `extract_claims(text)`: send text to LLM with structured extraction prompt, parse JSON response into list of `Claim` objects
    - Implement `_validate_claim_indices(claim, original_text)`: verify `start_index >= 0`, `start_index < end_index`, and `original_text[start_index:end_index] == claim.text`
    - Filter out claims with invalid indices (log warning)
    - Return empty list when no financial claims found
    - Raise `ClaimExtractionError` on malformed LLM JSON response
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 14.3_

  - [x] 6.2 Write property tests for claim index invariant
    - **Property 3: Claim index invariant and substring correspondence**
    - Generate random text and valid index pairs; construct Claim objects; assert `start_index >= 0`, `start_index < end_index`, and substring matches claim text
    - **Validates: Requirements 2.3, 2.4**

  - [x] 6.3 Write unit tests for Claim Extractor
    - Test extraction with known text containing financial claims
    - Test extraction with text containing no financial claims → empty list
    - Test malformed LLM JSON → `ClaimExtractionError`
    - Test invalid claim indices are filtered out
    - _Requirements: 2.1, 2.5, 14.3_

- [x] 7. Mock search provider
  - [x] 7.1 Implement Search Provider protocol and Mock Search Provider
    - Create `backend/app/services/search_provider.py` with `SearchProvider` Protocol class defining `search(query, claim_type) -> list[SearchResult]`
    - Create `backend/app/services/mock_search_provider.py` with `MockSearchProvider` class
    - Implement type-aware synthetic data generation: return different evidence sets for banking, market, investment, crypto, economic claim types
    - Ensure output format matches live provider schema exactly (title, source, summary, timestamp, relevance_score)
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 7.2 Write property tests for mock provider
    - **Property 5: Mock provider returns type-varying evidence**
    - Generate pairs of Claims with different `type` values; assert returned evidence sets differ in content
    - **Validates: Requirements 4.2**

  - [x] 7.3 Write property tests for SearchResult schema conformance
    - **Property 6: SearchResult schema conformance**
    - Query MockSearchProvider with random claim types; assert each result has non-empty title, source, summary, timestamp, and relevance_score in [0.0, 1.0]
    - **Validates: Requirements 3.2, 4.3**

- [x] 8. RAG pipeline with search provider abstraction
  - [x] 8.1 Implement RAG Pipeline
    - Create `backend/app/services/rag_pipeline.py` with `RAGPipeline` class
    - Accept a `SearchProvider` instance (strategy pattern) and configurable `top_k` (default 5)
    - Implement `retrieve_evidence(claim)`: query search provider, rank results by `relevance_score` descending, return top-k results as `EvidenceSet`
    - Set `insufficient_evidence = True` when search provider returns no results
    - Handle search provider errors: log error, return empty EvidenceSet with insufficient_evidence flag
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 8.2 Write property tests for evidence ranking
    - **Property 4: Evidence results are ranked by descending relevance score**
    - Generate lists of SearchResult with random relevance_scores; pass through RAG pipeline; assert output is sorted descending
    - **Validates: Requirements 3.3**

- [x] 9. Misinformation classifier
  - [x] 9.1 Implement Classifier
    - Create `backend/app/services/classifier.py` with `Classifier` class
    - Implement `classify(claim, evidence)`: send claim + evidence to LLM with classification prompt
    - Assign exactly one label from {VERIFIED, MISLEADING, LIKELY_FALSE, HARMFUL}
    - Produce reasoning string explaining the classification decision
    - Factor in evidence, language, and source corroboration
    - Handle empty evidence: include "insufficient evidence" in reasoning
    - Handle conflicting evidence: reflect conflict in reasoning
    - Raise `ClassificationError` if LLM returns invalid label
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 12.2_

  - [x] 9.2 Write property tests for classification output validity
    - **Property 7: Classification output validity**
    - Mock LLM to return valid labels; generate random Claims and EvidenceSets; assert label is in valid set and reasoning is non-empty
    - **Validates: Requirements 5.1, 5.2**

- [x] 10. Trust score engine
  - [x] 10.1 Implement Trust Score Engine
    - Create `backend/app/services/trust_score_engine.py` with `TrustScoreEngine` class
    - Accept optional `TrustScoreWeights` (defaults: 0.3, 0.3, 0.2, 0.2)
    - Implement `_compute_source_credibility(evidence)` → sub-score 0–100
    - Implement `_compute_evidence_strength(evidence)` → sub-score 0–100
    - Implement `_compute_language_neutrality(claim)` → sub-score 0–100
    - Implement `_compute_cross_source_agreement(evidence)` → sub-score 0–100
    - Implement `compute(claims, evidence, classifications)` → `TrustScoreResult` with weighted formula: `round(SC*0.3 + ES*0.3 + LN*0.2 + CSA*0.2)` clamped to [0, 100]
    - Return all four sub-scores alongside final score
    - Record `DeductionReference` for claim-level deductions from contradicting sources
    - Record `NoCorroborationDeduction` when deduction is due to lack of corroborating evidence
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 28.1, 28.2, 28.3, 28.4, 28.7_

  - [x] 10.2 Write property tests for trust score weighted formula
    - **Property 8: Trust score weighted formula correctness**
    - Generate random four sub-scores in [0, 100]; compute expected result with formula; assert engine output matches
    - **Validates: Requirements 6.1**

  - [x] 10.3 Write property tests for trust score range and completeness
    - **Property 9: Trust score range and completeness**
    - Generate random inputs; assert all four sub-scores and final score are integers in [0, 100] and all five fields are present
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**

- [x] 11. Explanation engine
  - [x] 11.1 Implement Explanation Engine
    - Create `backend/app/services/explanation_engine.py` with `ExplanationEngine` class
    - Implement `generate_explanation(claim, classification, trust_score, evidence)` → explanation string
    - Reference specific missing or conflicting evidence in explanation
    - Flag emotional or manipulative language patterns
    - Use uncertainty language — never present classifications as absolute facts
    - Reference supporting sources by name when available
    - Return fallback explanation text if LLM returns empty response
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 11.2, 12.2_

- [x] 12. Checkpoint - Verify all backend services
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. REST API endpoint
  - [x] 13.1 Implement POST /analyze endpoint and API server
    - Create `backend/app/api/routes.py` with FastAPI router
    - Implement `POST /analyze` accepting `AnalyzeRequest` JSON body
    - Wire the Analyzer orchestrator: validate → normalize → extract → retrieve → classify → score → explain
    - Return `AnalysisResponse` JSON on success
    - Return 400 for validation errors (empty/whitespace text, text > 50k, missing text field, invalid content_type)
    - Return 503 for LLM unavailability
    - Return 500 for internal errors (no internal details exposed)
    - Default `content_type` to TEXT when omitted; reject unsupported types with 400
    - Implement `GET /health` returning `{"status": "ok", "version": "..."}`
    - Configure CORS middleware with allowed origin from environment variable
    - Wire dependency injection: create Analyzer with all service dependencies based on config (use MockSearchProvider when no API keys configured)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 12.1, 12.3, 13.1, 27.3, 27.4_

  - [x] 13.2 Write property tests for API response structure
    - **Property 12: API response structure completeness**
    - Submit random valid text strings via test client; assert response JSON contains `claims`, `overall_classification`, `trust_score`, `explanation`, `sources`, `disclaimer` fields
    - **Validates: Requirements 8.2**

  - [x] 13.3 Write unit tests for API error handling
    - Test missing `text` field → 400
    - Test empty text → 400
    - Test text > 50,000 chars → 400
    - Test invalid `content_type` → 400
    - Test LLM unavailable → 503
    - Test internal error → 500 with no internal details
    - Test no claims found → valid response with null trust_score and empty claims
    - _Requirements: 8.3, 8.4, 12.1, 12.3, 27.4_

  - [x] 13.4 Write property tests for DeductionReference integrity
    - **Property 13: DeductionReference integrity**
    - Submit texts that produce claims with deductions; assert each DeductionReference has non-empty `source_name`, `url`, `summary`, `contradiction_rationale`, and `claim_id` matching an existing Claim
    - **Validates: Requirements 28.1, 28.2, 28.3**

- [x] 14. Checkpoint - Verify backend API end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Frontend - Text input and submission
  - [x] 15.1 Implement TextInput and SubmitButton components
    - Create `frontend/src/components/TextInput.tsx` — textarea for entering/pasting text
    - Create `frontend/src/components/SubmitButton.tsx` — button that triggers POST /analyze
    - Create `frontend/src/components/LoadingIndicator.tsx` — spinner/skeleton shown during analysis
    - Create `frontend/src/components/ErrorMessage.tsx` — user-friendly error display for 400/500/503 responses
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 15.2 Implement AnalyzePage with API integration
    - Create `frontend/src/pages/AnalyzePage.tsx` (or Next.js page route)
    - Wire TextInput → SubmitButton → POST /analyze API call
    - Manage loading state: show LoadingIndicator while request is in progress
    - Handle error responses: display ErrorMessage with user-friendly text
    - Store successful response in state for results display
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 16. Frontend - Results display
  - [x] 16.1 Implement TrustScoreMeter component
    - Create `frontend/src/components/TrustScoreMeter.tsx`
    - Display color-coded gauge: green for 70–100, yellow for 40–69, red for 0–39
    - Show numerical trust score value
    - Display ClassificationLabel badge alongside trust score
    - _Requirements: 10.1, 10.5_

  - [x] 16.2 Implement ExplanationPanel component
    - Create `frontend/src/components/ExplanationPanel.tsx`
    - Render explanation text in a dedicated panel
    - _Requirements: 10.2_

  - [x] 16.3 Implement RiskyPhraseHighlighter component
    - Create `frontend/src/components/RiskyPhraseHighlighter.tsx`
    - Highlight claims in original input text using `start_index` and `end_index` from extracted Claims
    - _Requirements: 10.3_

  - [x] 16.4 Implement SourceList component
    - Create `frontend/src/components/SourceList.tsx`
    - Display list of retrieved sources with titles and source names
    - _Requirements: 10.4, 11.3_

  - [x] 16.5 Implement SourceTransparencyPanel and DeductionReferenceCard
    - Create `frontend/src/components/SourceTransparencyPanel.tsx` — groups DeductionReferences under their corresponding Claims
    - Create `frontend/src/components/DeductionReferenceCard.tsx` — shows source name, summary, contradiction rationale, and clickable link (opens in new tab with `target="_blank"`)
    - Display NoCorroborationDeduction distinctly (deduction due to lack of evidence, not contradicting sources)
    - Do not display references section for claims with no deductions
    - _Requirements: 28.5, 28.6, 28.7, 28.8_

  - [x] 16.6 Implement DisclaimerBanner component
    - Create `frontend/src/components/DisclaimerBanner.tsx`
    - Display persistent disclaimer: "This analysis is an automated assessment and not a definitive judgment of truth. Please review the referenced sources to form your own conclusions."
    - _Requirements: 11.1_

  - [x] 16.7 Wire results display into AnalyzePage
    - Integrate TrustScoreMeter, ExplanationPanel, RiskyPhraseHighlighter, SourceList, SourceTransparencyPanel, and DisclaimerBanner into AnalyzePage
    - Show results panel only after successful analysis response
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 28.5_

- [x] 17. Checkpoint - Verify full-stack MVP integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 18. Phase 2 - Real search providers and enhanced scoring (Optional)
  - [ ] 18.1 Implement Live Search Provider
    - Create `backend/app/services/live_search_provider.py` implementing `SearchProvider` protocol
    - Integrate real news APIs (Reuters, Bloomberg, AP) for evidence retrieval
    - Add API key configuration via environment variables
    - Swap provider based on config: use LiveSearchProvider when API keys are present
    - _Requirements: 3.1, 4.1_

  - [ ] 18.2 Implement Fin-Fact Benchmark integration
    - Create `backend/app/services/finfact_provider.py` implementing `SearchProvider` protocol
    - Query Fin-Fact benchmark dataset as primary grounding source
    - Include results with `source_type: "benchmark"` to distinguish from external results
    - Handle unavailability: proceed with external providers only, flag claim as lacking benchmark grounding
    - _Requirements: 26.1, 26.2, 26.3_

  - [ ] 18.3 Enhance scoring with real source credibility data
    - Update `TrustScoreEngine._compute_source_credibility` to use real source reliability ratings
    - Improve evidence strength computation with real search result quality signals
    - _Requirements: 6.2, 6.3_

- [ ] 19. Phase 3 - Multi-modal support (Optional)
  - [ ] 19.1 Implement Video Transcription Engine
    - Create `backend/app/services/transcription_engine.py` with `TranscriptionEngine` class
    - Produce timestamped text transcript from audio track
    - Output `TranscriptSegment` objects with `text`, `start_time`, `end_time`
    - Handle silent/unintelligible audio: return empty transcript, flag as audio-absent
    - _Requirements: 16.1, 16.2, 16.3_

  - [ ] 19.2 Implement Visual-Text Aligner
    - Create `backend/app/services/visual_text_aligner.py` with `VisualTextAligner` class
    - Extract on-screen text elements with timestamp ranges
    - Merge audio transcript with on-screen text into unified timeline based on overlapping timestamps
    - Flag intra-modal discrepancies when on-screen text contradicts audio
    - _Requirements: 17.1, 17.2, 17.3_

  - [ ] 19.3 Implement Intent Classifier for video content
    - Create `backend/app/services/intent_classifier.py` with `IntentClassifier` class
    - Categorize claim segments as EDUCATIONAL_ADVICE, RHETORICAL_HYPE, or ACTIONABLE_INVESTMENT_CLAIM
    - Apply intent-aware framework (MICE) for linguistic cue assessment
    - Include confidence score for RHETORICAL_HYPE classifications
    - _Requirements: 18.1, 18.2, 18.3, 18.4_

  - [ ] 19.4 Implement OCR Module and Visualization Bias Detector
    - Create `backend/app/services/ocr_module.py` with `OCRModule` class
    - Extract numerical data, axis labels, titles, legend text from chart/infographic images
    - Create `backend/app/services/visualization_bias_detector.py` with `VisualizationBiasDetector` class
    - Detect bias types: truncated Y-axis, inconsistent intervals, aspect ratio distortion, cherry-picked ranges, missing context labels
    - Produce bias reports with type, severity (LOW/MEDIUM/HIGH), and description
    - _Requirements: 23.1, 23.2, 23.3, 24.1, 24.2, 24.3, 24.4_

  - [ ] 19.5 Implement Article Primary Source Verifier
    - Create `backend/app/services/primary_source_verifier.py` with `PrimarySourceVerifier` class
    - Prioritize primary sources (SEC filings, press releases) over secondary reporting
    - Validate numerical financial data points against authoritative databases
    - Flag discrepancies exceeding configurable tolerance (default 5%)
    - _Requirements: 19.1, 19.2, 19.3, 20.1, 20.2, 20.3_

  - [ ] 19.6 Implement Social Media Author Credibility and Viral Claim Detection
    - Create `backend/app/services/author_credibility_scorer.py` with `AuthorCredibilityScorer` class
    - Compute credibility score (0–100) based on historical accuracy, domain expertise, platform verification
    - Default to score 20 for unavailable author metadata
    - Create `backend/app/services/viral_claim_detector.py` with `ViralClaimDetector` class
    - Cross-reference claims against fact-checked databases
    - Include prior fact-check results in evidence metadata
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 22.1, 22.2, 22.3, 22.4_

  - [ ] 19.7 Implement Cross-Modal Discrepancy Detection
    - Update Analyzer to compare claims across modalities for consistency
    - Flag contradictions as `CrossModalDiscrepancy` with conflicting claims, source modalities, and contradiction description
    - Include cross-modal conflicts in explanation generation
    - _Requirements: 25.1, 25.2, 25.3, 25.4_

  - [ ] 19.8 Implement Content Type Router
    - Update Analyzer to route by `content_type`: TEXT → normalizer, VIDEO → transcription pipeline, IMAGE → OCR pipeline, ARTICLE → primary source verifier, SOCIAL_POST → author credibility + viral detection
    - All routes feed into shared claim extraction → classification → scoring → explanation pipeline
    - _Requirements: 27.1, 27.2_

- [x] 20. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Phase 1 (MVP) covers tasks 1–17: text input, claim extraction, mock search, classification, trust scoring, explanation, REST API, and full React frontend
- Phase 2 (task 18) and Phase 3 (task 19) are optional and extend the MVP with real APIs, multi-modal support, and advanced features
