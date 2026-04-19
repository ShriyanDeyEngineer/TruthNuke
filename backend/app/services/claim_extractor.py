"""Claim Extractor for TruthNuke.

This module provides LLM-based extraction of financial claims from text.
It uses structured prompts to identify claims and validates their indices
against the original text.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 14.3
"""

import logging
import uuid
from typing import Any

from app.models.schemas import Claim
from app.services.llm_client import LLMClient, LLMParsingError


logger = logging.getLogger(__name__)


class ClaimExtractionError(Exception):
    """Raised when claim extraction fails due to malformed LLM response.
    
    This error indicates that the LLM returned a response that could not
    be parsed into valid Claim objects, either due to invalid JSON format
    or missing required fields.
    
    Requirements: 14.3
    """
    pass


# System prompt for claim extraction
CLAIM_EXTRACTION_SYSTEM_PROMPT = """You are a financial claim extractor. Your task is to identify and extract explicit financial claims from the provided text.

A financial claim is a statement that makes an assertion about:
- Banking (interest rates, bank policies, account features)
- Market (stock prices, market trends, indices)
- Investment (returns, portfolio performance, investment advice)
- Crypto (cryptocurrency prices, blockchain, digital assets)
- Economic (GDP, inflation, employment, economic indicators)

For each claim found, you must provide:
1. The exact text of the claim as it appears in the original text
2. The start_index (0-based position where the claim starts in the original text)
3. The end_index (0-based position where the claim ends, exclusive)
4. The type (one of: "banking", "market", "investment", "crypto", "economic")
5. A list of named entities mentioned in the claim (company names, people, currencies, etc.)

IMPORTANT: The text at original_text[start_index:end_index] MUST exactly match the claim text you provide.

Respond with a JSON object in this exact format:
{
    "claims": [
        {
            "text": "exact claim text from the original",
            "start_index": 0,
            "end_index": 10,
            "type": "market",
            "entities": ["Entity1", "Entity2"]
        }
    ]
}

If no financial claims are found, respond with:
{
    "claims": []
}

Only extract explicit financial claims. Do not infer or create claims that are not directly stated in the text."""


class ClaimExtractor:
    """Extracts financial claims from text using LLM-based analysis.
    
    This class uses an LLM to identify and extract financial claims from
    normalized text. It validates the extracted claims' indices against
    the original text and filters out invalid claims.
    
    Attributes:
        llm_client: The LLM client used for claim extraction.
    
    Example:
        >>> extractor = ClaimExtractor(llm_client)
        >>> claims = await extractor.extract_claims("Apple stock rose 10% today.")
        >>> print(claims[0].text)
        "Apple stock rose 10% today."
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 14.3
    """
    
    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize the ClaimExtractor.
        
        Args:
            llm_client: The LLM client to use for claim extraction.
        """
        self.llm_client = llm_client
    
    async def extract_claims(self, text: str) -> list[Claim]:
        """Extract financial claims from the provided text.
        
        This method sends the text to the LLM with a structured extraction
        prompt, parses the JSON response into Claim objects, and validates
        each claim's indices against the original text.
        
        Args:
            text: The normalized text to extract claims from.
        
        Returns:
            A list of valid Claim objects extracted from the text.
            Returns an empty list if no financial claims are found.
        
        Raises:
            ClaimExtractionError: If the LLM returns malformed JSON that
                cannot be parsed into valid claims.
        
        Requirements: 2.1, 2.2, 2.5, 14.3
        """
        # Build the extraction prompt
        prompt = f"""Extract all financial claims from the following text:

---
{text}
---

Remember to provide exact start_index and end_index values that correspond to the claim text positions in the original text above."""
        
        try:
            # Call the LLM for claim extraction
            response = await self.llm_client.complete_json(
                prompt=prompt,
                system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
            )
        except LLMParsingError as e:
            logger.error(f"LLM returned malformed JSON for claim extraction: {e}")
            raise ClaimExtractionError(
                f"Failed to parse LLM response as valid JSON: {e}"
            ) from e
        
        # Validate the response structure
        claims_data = self._parse_response(response)
        
        # Convert to Claim objects and validate indices
        valid_claims: list[Claim] = []
        
        for claim_data in claims_data:
            try:
                claim = self._create_claim(claim_data)
                
                # Validate indices against original text
                if self._validate_claim_indices(claim, text):
                    valid_claims.append(claim)
                else:
                    logger.warning(
                        f"Filtered out claim with invalid indices: "
                        f"text='{claim.text}', start={claim.start_index}, "
                        f"end={claim.end_index}"
                    )
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed claim data: {claim_data}. Error: {e}")
                continue
        
        logger.info(f"Extracted {len(valid_claims)} valid claims from text")
        return valid_claims
    
    def _parse_response(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse and validate the LLM response structure.
        
        Args:
            response: The parsed JSON response from the LLM.
        
        Returns:
            A list of claim data dictionaries.
        
        Raises:
            ClaimExtractionError: If the response structure is invalid.
        """
        if not isinstance(response, dict):
            raise ClaimExtractionError(
                f"Expected JSON object response, got {type(response).__name__}"
            )
        
        if "claims" not in response:
            raise ClaimExtractionError(
                "LLM response missing required 'claims' field"
            )
        
        claims_data = response["claims"]
        
        if not isinstance(claims_data, list):
            raise ClaimExtractionError(
                f"Expected 'claims' to be an array, got {type(claims_data).__name__}"
            )
        
        return claims_data
    
    def _create_claim(self, claim_data: dict[str, Any]) -> Claim:
        """Create a Claim object from parsed claim data.
        
        Args:
            claim_data: Dictionary containing claim fields.
        
        Returns:
            A Claim object with a generated UUID.
        
        Raises:
            KeyError: If required fields are missing.
            TypeError: If field types are incorrect.
            ValueError: If field values are invalid.
        """
        # Validate required fields
        required_fields = ["text", "start_index", "end_index", "type"]
        for field in required_fields:
            if field not in claim_data:
                raise KeyError(f"Missing required field: {field}")
        
        # Extract and validate field values
        text = str(claim_data["text"])
        start_index = int(claim_data["start_index"])
        end_index = int(claim_data["end_index"])
        claim_type = str(claim_data["type"]).lower()
        
        # Validate claim type
        valid_types = {"banking", "market", "investment", "crypto", "economic"}
        if claim_type not in valid_types:
            logger.warning(
                f"Unknown claim type '{claim_type}', defaulting to 'economic'"
            )
            claim_type = "economic"
        
        # Extract entities (default to empty list if not provided)
        entities = claim_data.get("entities", [])
        if not isinstance(entities, list):
            entities = []
        entities = [str(e) for e in entities]
        
        return Claim(
            id=str(uuid.uuid4()),
            text=text,
            start_index=start_index,
            end_index=end_index,
            type=claim_type,
            entities=entities,
        )
    
    def _validate_claim_indices(self, claim: Claim, original_text: str) -> bool:
        """Validate that a claim's indices are valid and match the claim text.
        
        This method verifies:
        1. start_index >= 0
        2. start_index < end_index
        3. original_text[start_index:end_index] == claim.text
        
        Args:
            claim: The Claim object to validate.
            original_text: The original text the claim was extracted from.
        
        Returns:
            True if the claim indices are valid, False otherwise.
        
        Requirements: 2.3, 2.4
        """
        # Check start_index >= 0
        if claim.start_index < 0:
            logger.warning(
                f"Invalid claim: start_index ({claim.start_index}) is negative"
            )
            return False
        
        # Check start_index < end_index
        if claim.start_index >= claim.end_index:
            logger.warning(
                f"Invalid claim: start_index ({claim.start_index}) >= "
                f"end_index ({claim.end_index})"
            )
            return False
        
        # Check end_index doesn't exceed text length
        if claim.end_index > len(original_text):
            logger.warning(
                f"Invalid claim: end_index ({claim.end_index}) exceeds "
                f"text length ({len(original_text)})"
            )
            return False
        
        # Check substring matches claim text
        extracted_text = original_text[claim.start_index:claim.end_index]
        if extracted_text != claim.text:
            logger.warning(
                f"Invalid claim: substring mismatch. "
                f"Expected '{claim.text}', got '{extracted_text}'"
            )
            return False
        
        return True
