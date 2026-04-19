# Requirements Document

## Introduction

TruthNuke is a full-stack AI-powered financial misinformation detector. It accepts user-provided text, extracts financial claims, verifies them against external data sources using a Retrieval-Augmented Generation (RAG) pipeline, classifies misinformation risk, computes a trust score (0–100), and generates human-readable explanations. The MVP focuses on text input, LLM-based claim extraction, prompt-driven classification, heuristic trust scoring, and explanation output. A React/Next.js frontend provides a visual interface with a trust score meter, explanation panel, and highlighted risky phrases.

## Glossary

- **Analyzer**: The backend service responsible for orchestrating the full analysis pipeline (claim extraction, verification, classification, scoring, explanation) for a given input text.
- **Claim_Extractor**: The module that uses an LLM to identify and extract explicit financial claims from normalized input text, producing structured JSON output.
- **Claim**: A single financial assertion extracted from user-provided text, represented as a structured object with text, position indices, type, and entities.
- **RAG_Pipeline**: The Retrieval-Augmented Generation pipeline that queries external data sources to retrieve evidence for verifying extracted claims.
- **Search_Provider**: An abstraction over external data sources (news APIs, financial data APIs) that retrieves relevant articles and data for claim verification.
- **Mock_Search_Provider**: A simulated Search_Provider that returns synthetic evidence data based on claim type, used when external API keys are unavailable.
- **Classifier**: The module that categorizes each claim into a misinformation risk level (VERIFIED, MISLEADING, LIKELY_FALSE, HARMFUL) using LLM-based prompt-driven classification.
- **Trust_Score_Engine**: The module that computes a numerical trust score (0–100) from four independently computed components: Source Credibility, Evidence Strength, Language Neutrality, and Cross-Source Agreement.
- **Explanation_Engine**: The module that generates natural-language explanations justifying the classification, referencing evidence gaps, conflicting sources, and manipulative language patterns.
- **Trust_Score**: A numerical value from 0 to 100 representing the overall trustworthiness of analyzed content, computed as a weighted combination of four sub-scores.
- **Classification_Label**: One of four misinformation risk categories: VERIFIED, MISLEADING, LIKELY_FALSE, or HARMFUL.
- **Frontend**: The React/Next.js web application providing the user interface for text input, result display, and visual feedback.
- **API_Server**: The backend REST API server (FastAPI or Node.js/Express) that exposes the `/analyze` endpoint and routes requests through the analysis pipeline.
- **Transcription_Engine**: The module responsible for converting audio tracks from video and reel content into timestamped text transcripts for downstream claim analysis.
- **Visual_Text_Aligner**: The module that aligns on-screen text elements (lower thirds, overlay text, captions) with corresponding audio transcript segments to produce a unified claim timeline.
- **Intent_Classifier**: The module that applies intent-aware frameworks (such as MICE) to distinguish between educational financial advice, rhetorical hype, and actionable investment claims within transcribed content.
- **OCR_Module**: The Optical Character Recognition module that extracts numerical data and text from images, charts, and infographics for downstream verification.
- **Visualization_Bias_Detector**: The module that analyzes extracted chart data and visual properties to detect misleading visual representations such as truncated axes, non-zero baselines, and distorted scales.
- **Primary_Source_Verifier**: The module that validates extracted data points (P/E ratios, revenue growth, earnings figures) against authoritative financial databases and primary sources such as SEC filings and official press releases.
- **Author_Credibility_Scorer**: The module that computes a credibility score for content authors based on historical accuracy, domain expertise indicators, and platform verification status.
- **Viral_Claim_Detector**: The module that identifies viral claim patterns in social media posts and cross-references them against previously fact-checked claim databases.
- **Cross_Modal_Discrepancy**: A flagged condition that occurs when claims extracted from one modality (e.g., video audio) contradict claims extracted from another modality (e.g., article text) for the same financial topic.
- **Fin_Fact_Benchmark**: The Fin-Fact benchmark dataset or equivalent high-credibility financial corpus used as the grounding reference for claim verification.
- **Content_Modality**: The type of input content being analyzed, one of: TEXT, VIDEO, ARTICLE, SOCIAL_POST, or IMAGE.
- **Deduction_Reference**: A structured record of an external source that was used to justify a trust score deduction for a specific Claim, containing the source name, URL, summary, and contradiction rationale.
- **Source_Transparency_Panel**: The Frontend UI component that displays Deduction_References associated with each Claim that received a trust score deduction, enabling users to review and independently verify the sources used in the analysis.

## Requirements

### Requirement 1: Input Text Acceptance and Normalization

**User Story:** As a user, I want to submit raw text containing financial claims, so that the system can analyze it for misinformation.

#### Acceptance Criteria

1. WHEN raw text is submitted to the Analyzer, THE Analyzer SHALL accept the text and pass it to the normalization step.
2. WHEN raw text is submitted, THE Analyzer SHALL normalize the text by trimming leading and trailing whitespace and collapsing consecutive whitespace characters into single spaces.
3. IF empty text or whitespace-only text is submitted, THEN THE Analyzer SHALL return a validation error indicating that non-empty text is required.
4. IF text exceeding 50,000 characters is submitted, THEN THE Analyzer SHALL return a validation error indicating the maximum allowed length.

### Requirement 2: Claim Extraction

**User Story:** As a user, I want the system to extract individual financial claims from my text, so that each claim can be independently verified.

#### Acceptance Criteria

1. WHEN normalized text is provided to the Claim_Extractor, THE Claim_Extractor SHALL identify and extract all explicit financial claims from the text.
2. THE Claim_Extractor SHALL output each extracted Claim as a structured JSON object containing: `text` (the claim string), `start_index` (integer position of the claim start in the original text), `end_index` (integer position of the claim end in the original text), `type` (a category string such as "banking", "market", "investment", "crypto", or "economic"), and `entities` (an array of named entities referenced in the claim).
3. WHEN the Claim_Extractor produces a list of Claims, THE Claim_Extractor SHALL ensure that each Claim has a `start_index` value that is greater than or equal to 0 and less than the `end_index` value.
4. WHEN the Claim_Extractor produces a list of Claims, THE Claim_Extractor SHALL ensure that the substring of the original text from `start_index` to `end_index` corresponds to the extracted claim text.
5. IF no financial claims are found in the text, THEN THE Claim_Extractor SHALL return an empty claims array.

### Requirement 3: Retrieval-Augmented Verification

**User Story:** As a user, I want each claim to be checked against external data sources, so that the system's analysis is grounded in real-world evidence.

#### Acceptance Criteria

1. WHEN a Claim is passed to the RAG_Pipeline, THE RAG_Pipeline SHALL query the configured Search_Provider to retrieve relevant articles and data for that Claim.
2. THE RAG_Pipeline SHALL store the top-k retrieved results (where k is configurable, default 5) for each Claim, with each result containing: `title`, `source`, `summary`, `timestamp`, and `relevance_score`.
3. WHEN retrieved results are available, THE RAG_Pipeline SHALL rank results by relevance_score in descending order before passing them to downstream modules.
4. IF the Search_Provider returns no results for a Claim, THEN THE RAG_Pipeline SHALL proceed with an empty evidence set and flag the Claim as having insufficient evidence.

### Requirement 4: Dynamic Mock Search Provider

**User Story:** As a developer, I want a mock data provider that simulates external search results, so that the RAG pipeline can be tested without requiring API keys.

#### Acceptance Criteria

1. IF external API keys for news or financial data services are not configured, THEN THE Analyzer SHALL use the Mock_Search_Provider instead of live Search_Providers.
2. WHEN the Mock_Search_Provider receives a Claim, THE Mock_Search_Provider SHALL return simulated evidence data that varies based on the Claim type (banking, market, investment, crypto, economic).
3. THE Mock_Search_Provider SHALL return results in the same structured format as a live Search_Provider, including `title`, `source`, `summary`, `timestamp`, and `relevance_score`.

### Requirement 5: Misinformation Classification

**User Story:** As a user, I want each claim classified by misinformation risk level, so that I can quickly understand how trustworthy a claim is.

#### Acceptance Criteria

1. WHEN a Claim and its retrieved evidence are provided to the Classifier, THE Classifier SHALL assign exactly one Classification_Label from the set: VERIFIED, MISLEADING, LIKELY_FALSE, HARMFUL.
2. THE Classifier SHALL produce a reasoning string alongside each Classification_Label that explains the basis for the classification decision.
3. WHEN the Classifier assigns a Classification_Label, THE Classifier SHALL consider the retrieved evidence, the language used in the Claim, and the presence or absence of corroborating sources.
4. IF a Claim has an empty evidence set, THEN THE Classifier SHALL factor the lack of evidence into its classification reasoning.

### Requirement 6: Trust Score Computation

**User Story:** As a user, I want a numerical trust score for the analyzed content, so that I have a quick quantitative indicator of trustworthiness.

#### Acceptance Criteria

1. WHEN classification and evidence data are available, THE Trust_Score_Engine SHALL compute a Trust_Score using the formula: Trust_Score = (Source_Credibility × 0.3) + (Evidence_Strength × 0.3) + (Language_Neutrality × 0.2) + (Cross_Source_Agreement × 0.2).
2. THE Trust_Score_Engine SHALL compute Source_Credibility as a sub-score from 0 to 100 based on the reliability ratings of the sources in the retrieved evidence.
3. THE Trust_Score_Engine SHALL compute Evidence_Strength as a sub-score from 0 to 100 based on the number and quality of supporting sources retrieved.
4. THE Trust_Score_Engine SHALL compute Language_Neutrality as a sub-score from 0 to 100 based on sentiment and emotional tone analysis of the Claim text.
5. THE Trust_Score_Engine SHALL compute Cross_Source_Agreement as a sub-score from 0 to 100 based on the consistency of information across retrieved sources.
6. THE Trust_Score_Engine SHALL produce a final Trust_Score that is an integer between 0 and 100 inclusive.
7. THE Trust_Score_Engine SHALL return each of the four sub-scores alongside the final Trust_Score.

### Requirement 7: Explanation Generation

**User Story:** As a user, I want a clear natural-language explanation of the analysis, so that I can understand why a claim was classified a certain way.

#### Acceptance Criteria

1. WHEN a Classification_Label, Trust_Score, and evidence data are available for a Claim, THE Explanation_Engine SHALL generate a natural-language explanation that justifies the classification.
2. THE Explanation_Engine SHALL reference specific missing or conflicting evidence in the explanation when applicable.
3. THE Explanation_Engine SHALL identify and call out emotional or manipulative language patterns detected in the Claim text.
4. THE Explanation_Engine SHALL include uncertainty language in the explanation, avoiding absolute statements of truth or falsehood.
5. THE Explanation_Engine SHALL reference supporting sources by name when available.

### Requirement 8: REST API Endpoint

**User Story:** As a frontend developer, I want a REST API endpoint to submit text for analysis, so that the frontend can integrate with the backend analysis pipeline.

#### Acceptance Criteria

1. THE API_Server SHALL expose a POST `/analyze` endpoint that accepts a JSON body with a `text` field.
2. WHEN a valid request is received at POST `/analyze`, THE API_Server SHALL return a JSON response containing: `claims` (array of extracted Claims), `classification` (the overall Classification_Label), `trust_score` (the computed Trust_Score integer), `explanation` (the generated explanation string), and `sources` (array of retrieved evidence sources).
3. IF the request body is missing the `text` field or the `text` field is empty, THEN THE API_Server SHALL return an HTTP 400 response with a descriptive error message.
4. IF an internal error occurs during analysis, THEN THE API_Server SHALL return an HTTP 500 response with a generic error message that does not expose internal system details.
5. THE API_Server SHALL include appropriate CORS headers to allow requests from the Frontend origin.

### Requirement 9: Frontend Text Input and Submission

**User Story:** As a user, I want a web interface where I can paste or type text and submit it for analysis, so that I can use the tool without technical knowledge.

#### Acceptance Criteria

1. THE Frontend SHALL display a text input area where the user can enter or paste text.
2. THE Frontend SHALL display a submit button that sends the entered text to the POST `/analyze` endpoint.
3. WHILE the analysis request is in progress, THE Frontend SHALL display a loading indicator to the user.
4. IF the API_Server returns an error response, THEN THE Frontend SHALL display a user-friendly error message.

### Requirement 10: Frontend Results Display

**User Story:** As a user, I want to see the analysis results in a clear visual format, so that I can quickly understand the trustworthiness of the content.

#### Acceptance Criteria

1. WHEN analysis results are received, THE Frontend SHALL display a color-coded trust score meter showing the Trust_Score value (green for 70–100, yellow for 40–69, red for 0–39).
2. WHEN analysis results are received, THE Frontend SHALL display the explanation text in a dedicated explanation panel.
3. WHEN analysis results are received, THE Frontend SHALL highlight risky phrases in the original input text using the `start_index` and `end_index` values from extracted Claims.
4. WHEN analysis results are received, THE Frontend SHALL display the list of retrieved sources with their titles and source names.
5. THE Frontend SHALL display the Classification_Label alongside the Trust_Score.

### Requirement 11: Safety and Uncertainty Disclosure

**User Story:** As a user, I want the system to clearly communicate that its outputs are assessments rather than absolute truths, so that I can make informed decisions.

#### Acceptance Criteria

1. THE Frontend SHALL display a disclaimer stating that analysis results are automated assessments and not definitive judgments of truth.
2. THE Explanation_Engine SHALL avoid language that presents classifications as absolute facts.
3. WHEN sources are available, THE Frontend SHALL display them so the user can independently verify the analysis.

### Requirement 12: Graceful Handling of Edge Cases

**User Story:** As a user, I want the system to handle unusual or difficult inputs gracefully, so that I always receive a meaningful response.

#### Acceptance Criteria

1. IF the input text contains no financial claims, THEN THE Analyzer SHALL return a response indicating that no financial claims were detected, with a Trust_Score of null and an empty claims array.
2. IF retrieved sources provide conflicting information about a Claim, THEN THE Classifier SHALL reflect the conflict in its reasoning and THE Explanation_Engine SHALL describe the conflicting evidence.
3. IF the LLM service is unavailable or returns an error, THEN THE Analyzer SHALL return an HTTP 503 response with a message indicating temporary unavailability.

### Requirement 13: Configuration and Environment Management

**User Story:** As a developer, I want API keys and configuration values managed through environment variables, so that secrets are not hardcoded and deployment is flexible.

#### Acceptance Criteria

1. THE API_Server SHALL read all external API keys (news API, financial data API, LLM API) from environment variables.
2. THE API_Server SHALL read configurable parameters (top-k retrieval count, maximum input length, Trust_Score weights) from environment variables with sensible defaults.
3. IF a required LLM API key environment variable is not set, THEN THE API_Server SHALL fail to start and log a descriptive error message indicating the missing configuration.

### Requirement 14: Claim Extraction JSON Serialization and Deserialization

**User Story:** As a developer, I want claim extraction results to be reliably serialized to and deserialized from JSON, so that data integrity is maintained across the pipeline.

#### Acceptance Criteria

1. THE Claim_Extractor SHALL serialize extracted Claims to JSON format conforming to the defined Claim schema.
2. WHEN a serialized Claim JSON string is deserialized back into a Claim object, THE Claim_Extractor SHALL produce an object equivalent to the original Claim (round-trip property).
3. IF the LLM returns malformed JSON for claim extraction, THEN THE Claim_Extractor SHALL return a parsing error rather than silently producing incorrect Claims.

### Requirement 15: Trust Score Serialization and Deserialization

**User Story:** As a developer, I want trust score results to be reliably serialized to and deserialized from JSON, so that scores are accurately transmitted between backend and frontend.

#### Acceptance Criteria

1. THE Trust_Score_Engine SHALL serialize Trust_Score results (including all four sub-scores and the final score) to JSON format.
2. WHEN a serialized Trust_Score JSON string is deserialized back into a Trust_Score object, THE Trust_Score_Engine SHALL produce an object equivalent to the original (round-trip property).

### Requirement 16: Video and Reel Transcription

**User Story:** As a user, I want to submit video or reel content for analysis, so that financial claims made in audio and visual overlays are fact-checked.

#### Acceptance Criteria

1. WHEN video or reel content is submitted to the Analyzer, THE Transcription_Engine SHALL produce a timestamped text transcript from the audio track before any claim analysis begins.
2. THE Transcription_Engine SHALL output each transcript segment as a structured object containing: `text` (the transcribed string), `start_time` (float, seconds from video start), and `end_time` (float, seconds from video start).
3. IF the audio track is silent or contains no intelligible speech, THEN THE Transcription_Engine SHALL return an empty transcript array and flag the content as audio-absent.

### Requirement 17: Visual-Text Alignment for Video Content

**User Story:** As a user, I want on-screen text in videos (lower thirds, overlays, captions) to be captured alongside audio claims, so that the full context of financial assertions is analyzed.

#### Acceptance Criteria

1. WHEN video content contains on-screen text elements, THE Visual_Text_Aligner SHALL extract those text elements and associate each with its display timestamp range.
2. WHEN both a transcript and on-screen text elements are available, THE Visual_Text_Aligner SHALL produce a unified claim timeline that merges audio transcript segments with corresponding on-screen text segments based on overlapping timestamp ranges.
3. IF on-screen text contradicts the audio transcript at the same timestamp, THEN THE Visual_Text_Aligner SHALL flag the segment as containing an intra-modal discrepancy.

### Requirement 18: Intent-Aware Claim Classification for Video Content

**User Story:** As a user, I want the system to distinguish between educational financial commentary and rhetorical hype in videos, so that classification reflects the speaker's intent.

#### Acceptance Criteria

1. WHEN a unified claim timeline is produced from video content, THE Intent_Classifier SHALL categorize each claim segment as one of: EDUCATIONAL_ADVICE, RHETORICAL_HYPE, or ACTIONABLE_INVESTMENT_CLAIM.
2. THE Intent_Classifier SHALL apply an intent-aware framework (such as MICE) to assess linguistic cues, tone, and contextual markers when determining the intent category.
3. WHEN a claim segment is categorized as RHETORICAL_HYPE, THE Intent_Classifier SHALL include a confidence score (0 to 100) indicating the strength of the hype classification.
4. THE Classifier SHALL factor the intent category assigned by the Intent_Classifier into its misinformation risk classification for video-sourced claims.

### Requirement 19: Article and Long-Form Content Primary Source Verification

**User Story:** As a user, I want claims in articles verified against primary sources like SEC filings and official press releases, so that fact-checking relies on authoritative data rather than secondary reporting.

#### Acceptance Criteria

1. WHEN an article or long-form content is submitted, THE Primary_Source_Verifier SHALL prioritize verification against primary sources (SEC filings, official press releases, regulatory filings) over secondary news reporting.
2. WHEN the Primary_Source_Verifier retrieves both primary and secondary sources for a Claim, THE Primary_Source_Verifier SHALL rank primary sources higher than secondary sources in the evidence set regardless of retrieval order.
3. IF no primary sources are found for a Claim extracted from an article, THEN THE Primary_Source_Verifier SHALL flag the Claim as lacking primary source corroboration and include this flag in the evidence metadata.

### Requirement 20: Financial Data Point Validation

**User Story:** As a user, I want specific financial figures cited in articles (P/E ratios, revenue growth, earnings) validated against authoritative databases, so that numerical inaccuracies are detected.

#### Acceptance Criteria

1. WHEN a Claim contains numerical financial data points (such as P/E ratios, revenue growth percentages, earnings figures, or market capitalization values), THE Primary_Source_Verifier SHALL extract those data points and validate each against authoritative financial databases.
2. WHEN a data point extracted from a Claim deviates from the authoritative database value by more than a configurable tolerance threshold (default 5%), THE Primary_Source_Verifier SHALL flag the data point as a numerical discrepancy and include both the claimed value and the authoritative value in the evidence metadata.
3. IF the authoritative financial database is unavailable, THEN THE Primary_Source_Verifier SHALL proceed with available secondary sources and flag the Claim as having unverified numerical data.

### Requirement 21: Social Media Author Credibility Analysis

**User Story:** As a user, I want the system to assess the credibility of social media post authors, so that claims from unreliable sources are weighted accordingly.

#### Acceptance Criteria

1. WHEN a social media post is submitted, THE Author_Credibility_Scorer SHALL compute a credibility score (0 to 100) for the post author based on historical accuracy, domain expertise indicators, and platform verification status.
2. THE Author_Credibility_Scorer SHALL include the computed credibility score in the evidence metadata for all Claims extracted from that social media post.
3. THE Trust_Score_Engine SHALL factor the author credibility score into the Source_Credibility sub-score computation for social media content.
4. IF author metadata is unavailable or insufficient, THEN THE Author_Credibility_Scorer SHALL assign a default low credibility score of 20 and flag the author as having unverifiable credentials.

### Requirement 22: Social Media Timestamp and Viral Claim Detection

**User Story:** As a user, I want the system to verify original timestamps on social posts and detect viral claim patterns, so that recycled or outdated misinformation is identified.

#### Acceptance Criteria

1. WHEN a social media post is submitted, THE Analyzer SHALL extract and validate the original publication timestamp from the post metadata.
2. IF the original publication timestamp is missing or cannot be verified, THEN THE Analyzer SHALL flag the post as having an unverifiable timestamp.
3. WHEN a Claim is extracted from a social media post, THE Viral_Claim_Detector SHALL cross-reference the Claim against previously fact-checked claim databases to identify matching or substantially similar claims.
4. WHEN the Viral_Claim_Detector identifies a match with a previously fact-checked claim, THE Viral_Claim_Detector SHALL include the prior fact-check result and its source in the evidence metadata.

### Requirement 23: OCR Data Extraction from Visual Content

**User Story:** As a user, I want the system to extract numerical data from charts and infographics, so that visual financial claims are subjected to the same verification as text claims.

#### Acceptance Criteria

1. WHEN an image containing a chart, graph, or infographic is submitted, THE OCR_Module SHALL extract all visible numerical data, axis labels, titles, and legend text from the image.
2. THE OCR_Module SHALL output extracted data as structured objects containing: `data_points` (array of numerical values with labels), `chart_type` (detected chart type such as bar, line, pie), `title` (extracted chart title), and `axis_labels` (extracted axis label strings).
3. IF the OCR_Module cannot extract readable data from an image, THEN THE OCR_Module SHALL return an empty extraction result and flag the image as unreadable.
4. WHEN numerical data is extracted from an image, THE Primary_Source_Verifier SHALL validate the extracted data points against authoritative financial databases using the same process as text-based data point validation.

### Requirement 24: Visualization Bias Detection

**User Story:** As a user, I want the system to detect misleading chart techniques like truncated axes or distorted scales, so that visual manipulation of financial data is flagged.

#### Acceptance Criteria

1. WHEN the OCR_Module extracts chart data from an image, THE Visualization_Bias_Detector SHALL analyze the chart for misleading visual representations.
2. THE Visualization_Bias_Detector SHALL detect the following bias types: truncated Y-axis (non-zero baseline), inconsistent axis intervals, aspect ratio distortion, cherry-picked date ranges, and missing context labels.
3. WHEN one or more visualization biases are detected, THE Visualization_Bias_Detector SHALL produce a bias report containing: `bias_type` (the category of detected bias), `severity` (LOW, MEDIUM, or HIGH), and `description` (a human-readable explanation of the detected bias).
4. WHEN visualization biases are detected, THE Explanation_Engine SHALL include the bias findings in the generated explanation for Claims associated with that image.

### Requirement 25: Cross-Modal Discrepancy Detection

**User Story:** As a user, I want the system to flag contradictions between different content types covering the same financial topic, so that conflicting information across modalities is surfaced.

#### Acceptance Criteria

1. WHEN the Analyzer processes multiple content modalities (video, article, social post, image) related to the same financial topic, THE Analyzer SHALL compare extracted claims across modalities for consistency.
2. IF claims extracted from one Content_Modality contradict claims extracted from another Content_Modality on the same financial topic, THEN THE Analyzer SHALL flag the contradiction as a Cross_Modal_Discrepancy.
3. WHEN a Cross_Modal_Discrepancy is detected, THE Analyzer SHALL include in the discrepancy record: the conflicting claims, their respective source modalities, and a description of the contradiction.
4. WHEN a Cross_Modal_Discrepancy is detected, THE Explanation_Engine SHALL describe the cross-modal conflict in the generated explanation and reference both source modalities.

### Requirement 26: Fin-Fact Benchmark Grounding

**User Story:** As a user, I want all financial claims grounded against a high-credibility benchmark dataset, so that verification is anchored in established financial facts.

#### Acceptance Criteria

1. WHEN a Claim is verified, THE RAG_Pipeline SHALL query the Fin_Fact_Benchmark dataset as a primary grounding source in addition to external Search_Providers.
2. THE RAG_Pipeline SHALL include Fin_Fact_Benchmark results in the evidence set with a source type indicator of "benchmark" to distinguish them from external search results.
3. IF the Fin_Fact_Benchmark dataset is unavailable, THEN THE RAG_Pipeline SHALL proceed with external Search_Providers only and flag the Claim as lacking benchmark grounding.

### Requirement 27: Multi-Modal Content Type Routing

**User Story:** As a user, I want to submit different content types (text, video, article, social post, image) through a single interface, so that the system automatically applies the appropriate analysis pipeline.

#### Acceptance Criteria

1. WHEN content is submitted to the Analyzer, THE Analyzer SHALL detect the Content_Modality of the input and route it to the appropriate processing pipeline (text analysis, video transcription, article verification, social media analysis, or image OCR).
2. THE API_Server SHALL accept a `content_type` field in the request body with valid values: TEXT, VIDEO, ARTICLE, SOCIAL_POST, or IMAGE.
3. IF the `content_type` field is omitted, THEN THE Analyzer SHALL default to TEXT processing.
4. IF an unsupported `content_type` value is provided, THEN THE API_Server SHALL return an HTTP 400 response with a descriptive error message listing the supported content types.

### Requirement 28: Source Transparency for Trust Score Deductions

**User Story:** As a user, I want to see the specific references and sources that led to trust score deductions on my analyzed content, so that I can independently verify the basis for each deduction and assess the analysis quality.

#### Acceptance Criteria

1. WHEN the Trust_Score_Engine deducts points from the Trust_Score for a Claim being inaccurate or unsupported, THE Analyzer SHALL record each external source that contributed to that deduction as a Deduction_Reference.
2. THE Analyzer SHALL structure each Deduction_Reference as a JSON object containing: `source_name` (the name of the publishing outlet or account), `url` (a direct link to the original source material), `summary` (a brief description of what the source states), and `contradiction_rationale` (an explanation of how the source contradicts or fails to support the Claim).
3. THE Analyzer SHALL associate each Deduction_Reference with the specific Claim it relates to, using the Claim identifier, rather than presenting references as an unassociated list.
4. THE Analyzer SHALL source Deduction_References from major established news outlets (such as Reuters, Associated Press, Bloomberg, BBC, and Financial Times) and verified or authoritative social media accounts with a demonstrated track record of accuracy.
5. WHEN Deduction_References are available for a Claim, THE Frontend SHALL display them in the Source_Transparency_Panel grouped under the corresponding Claim, with each reference showing the source name, summary, contradiction rationale, and a clickable link to the original source.
6. WHEN a user clicks a Deduction_Reference link in the Source_Transparency_Panel, THE Frontend SHALL open the original source URL in a new browser tab so the user can independently verify the information.
7. IF the Trust_Score_Engine deducts points from a Claim but no trustworthy contradicting references were found, THEN THE Analyzer SHALL indicate in the Deduction_Reference that the deduction was based on a lack of corroborating evidence rather than on directly contradicting sources, and THE Frontend SHALL display this distinction clearly in the Source_Transparency_Panel.
8. IF a Claim receives no trust score deductions, THEN THE Source_Transparency_Panel SHALL not display a references section for that Claim.
