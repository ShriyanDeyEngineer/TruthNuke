"""Classifier for TruthNuke.

This module provides LLM-based misinformation classification for financial claims.
It assigns exactly one label from {VERIFIED, MISLEADING, LIKELY_FALSE, HARMFUL}
and produces reasoning explaining the classification decision.

Requirements: 5.1, 5.2, 5.3, 5.4, 12.2
"""

import logging
from typing import Any

from app.models.schemas import (
    Claim,
    ClassificationLabel,
    ClassificationResult,
    EvidenceSet,
)
from app.services.llm_client import LLMClient


logger = logging.getLogger(__name__)


class ClassificationError(Exception):
    """Raised when classification fails due to invalid LLM response.
    
    This error is raised when the LLM returns a label that is not in the
    valid set {VERIFIED, MISLEADING, LIKELY_FALSE, HARMFUL}.
    
    Requirements: 5.1
    """
    pass


# Valid classification labels
VALID_LABELS = {label.value for label in ClassificationLabel}

# System prompt for classification
CLASSIFICATION_SYSTEM_PROMPT = """You are a financial misinformation classifier. Your task is to analyze financial claims and classify them based on the provided evidence.

You must assign exactly ONE label from the following set:
- VERIFIED: The claim is supported by credible evidence and appears accurate
- MISLEADING: The claim contains some truth but is presented in a way that could deceive
- LIKELY_FALSE: The claim contradicts available evidence or makes unsupported assertions
- HARMFUL: The claim could cause financial harm if acted upon (e.g., pump-and-dump schemes, fraudulent investment advice)

Consider the following factors in your classification:
1. Evidence quality and quantity
2. Source credibility and corroboration
3. Language used in the claim (emotional, manipulative, neutral)
4. Consistency across multiple sources

Always provide clear reasoning for your classification decision.

Respond in JSON format with exactly these fields:
{
    "label": "VERIFIED" | "MISLEADING" | "LIKELY_FALSE" | "HARMFUL",
    "reasoning": "Your detailed explanation for the classification"
}"""


class Classifier:
    """LLM-based misinformation classifier for financial claims.
    
    This classifier uses an LLM to analyze financial claims against retrieved
    evidence and assign a misinformation risk label with reasoning.
    
    Attributes:
        llm_client: The LLM client for making API calls.
    
    Example:
        >>> classifier = Classifier(llm_client)
        >>> result = await classifier.classify(claim, evidence)
        >>> print(result.label)
        ClassificationLabel.VERIFIED
        >>> print(result.reasoning)
        "The claim is supported by multiple credible sources..."
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 12.2
    """
    
    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize the Classifier.
        
        Args:
            llm_client: The LLM client for making classification requests.
        """
        self.llm_client = llm_client
    
    async def classify(
        self, claim: Claim, evidence: EvidenceSet
    ) -> ClassificationResult:
        """Classify a claim based on retrieved evidence.
        
        Assigns exactly one label from {VERIFIED, MISLEADING, LIKELY_FALSE, HARMFUL}
        and produces a reasoning string explaining the classification decision.
        
        Args:
            claim: The financial claim to classify.
            evidence: The evidence set retrieved for the claim.
        
        Returns:
            ClassificationResult containing the claim_id, label, and reasoning.
        
        Raises:
            ClassificationError: If the LLM returns an invalid label.
            LLMUnavailableError: If the LLM service is unavailable.
            LLMParsingError: If the LLM response cannot be parsed as JSON.
        
        Requirements: 5.1, 5.2, 5.3, 5.4, 12.2
        """
        prompt = self._build_classification_prompt(claim, evidence)
        
        logger.debug(f"Classifying claim {claim.id}: {claim.text[:100]}...")
        
        response = await self.llm_client.complete_json(
            prompt=prompt,
            system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
        )
        
        return self._parse_classification_response(response, claim.id)
    
    def _build_classification_prompt(
        self, claim: Claim, evidence: EvidenceSet
    ) -> str:
        """Build the classification prompt for the LLM.
        
        Args:
            claim: The claim to classify.
            evidence: The evidence set for the claim.
        
        Returns:
            The formatted prompt string.
        """
        prompt_parts = [
            f"Classify the following financial claim:\n",
            f"Claim: \"{claim.text}\"\n",
            f"Claim Type: {claim.type}\n",
        ]
        
        if claim.entities:
            prompt_parts.append(f"Entities mentioned: {', '.join(claim.entities)}\n")
        
        prompt_parts.append("\n--- Evidence ---\n")
        
        # Handle empty evidence case (Req 5.4)
        if evidence.insufficient_evidence or not evidence.results:
            prompt_parts.append(
                "No evidence was found for this claim. "
                "Consider this lack of evidence in your classification. "
                "Include 'insufficient evidence' in your reasoning.\n"
            )
        else:
            # Check for conflicting evidence (Req 12.2)
            conflicting_info = self._detect_conflicting_evidence(evidence)
            
            if conflicting_info:
                prompt_parts.append(
                    "NOTE: The evidence appears to contain conflicting information. "
                    "Please reflect this conflict in your reasoning.\n\n"
                )
            
            for i, result in enumerate(evidence.results, 1):
                prompt_parts.append(
                    f"{i}. Source: {result.source}\n"
                    f"   Title: {result.title}\n"
                    f"   Summary: {result.summary}\n"
                    f"   Timestamp: {result.timestamp}\n"
                    f"   Relevance: {result.relevance_score:.2f}\n\n"
                )
        
        prompt_parts.append(
            "\nBased on the claim and evidence above, provide your classification "
            "and detailed reasoning in JSON format."
        )
        
        return "".join(prompt_parts)
    
    def _detect_conflicting_evidence(self, evidence: EvidenceSet) -> bool:
        """Detect if evidence set contains potentially conflicting information.
        
        This is a heuristic check that looks for indicators of conflicting
        evidence in the summaries. The LLM will do the actual conflict analysis.
        
        Args:
            evidence: The evidence set to analyze.
        
        Returns:
            True if conflicting evidence is detected, False otherwise.
        """
        if len(evidence.results) < 2:
            return False
        
        # Simple heuristic: check for contradiction keywords in summaries
        contradiction_keywords = [
            "however", "contrary", "disputes", "contradicts", "denies",
            "refutes", "disagrees", "opposes", "challenges", "questions",
            "false", "incorrect", "inaccurate", "misleading"
        ]
        
        summaries_lower = [r.summary.lower() for r in evidence.results]
        
        for summary in summaries_lower:
            for keyword in contradiction_keywords:
                if keyword in summary:
                    return True
        
        return False
    
    def _parse_classification_response(
        self, response: dict[str, Any], claim_id: str
    ) -> ClassificationResult:
        """Parse the LLM response into a ClassificationResult.
        
        Args:
            response: The parsed JSON response from the LLM.
            claim_id: The ID of the claim being classified.
        
        Returns:
            ClassificationResult with the parsed label and reasoning.
        
        Raises:
            ClassificationError: If the label is not in the valid set.
        """
        label_str = response.get("label", "").upper().strip()
        reasoning = response.get("reasoning", "")
        
        # Validate the label (Req 5.1)
        if label_str not in VALID_LABELS:
            logger.error(
                f"Invalid classification label from LLM: '{label_str}'. "
                f"Valid labels are: {VALID_LABELS}"
            )
            raise ClassificationError(
                f"LLM returned invalid classification label: '{label_str}'. "
                f"Expected one of: {', '.join(sorted(VALID_LABELS))}"
            )
        
        # Validate reasoning is present (Req 5.2)
        if not reasoning or not reasoning.strip():
            logger.warning(
                f"LLM returned empty reasoning for claim {claim_id}. "
                "Using default reasoning."
            )
            reasoning = "Classification based on available evidence analysis."
        
        return ClassificationResult(
            claim_id=claim_id,
            label=ClassificationLabel(label_str),
            reasoning=reasoning.strip(),
        )
