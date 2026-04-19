"""Mock Search Provider.

This module provides a mock implementation of the SearchProvider protocol
for development and testing purposes when external API keys are not configured.

Requirements: 4.1, 4.2, 4.3
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.schemas import SearchResult
from app.services.search_provider import SearchProvider


class MockSearchProvider:
    """Mock search provider that returns synthetic evidence data.
    
    This provider simulates external search results for development and testing.
    It generates type-aware synthetic data that varies based on the claim type,
    ensuring realistic-looking evidence sets for different financial domains.
    
    The output format matches the live SearchProvider schema exactly.
    
    Requirements: 4.1, 4.2, 4.3
    """

    # Type-specific source configurations for realistic synthetic data
    _SOURCE_DATA: dict[str, dict[str, Any]] = {
        "banking": {
            "sources": [
                "Federal Reserve",
                "FDIC",
                "Reuters Finance",
                "Bloomberg Banking",
                "Wall Street Journal",
                "Financial Times",
                "American Banker",
            ],
            "topics": [
                "interest rate policy",
                "bank lending practices",
                "deposit insurance",
                "banking regulations",
                "credit availability",
                "bank capital requirements",
                "consumer banking trends",
            ],
            "title_templates": [
                "Federal Reserve {action} on {topic}",
                "Banking sector {action} amid {topic} concerns",
                "FDIC report highlights {topic} developments",
                "{source} analysis: {topic} outlook",
                "Banks {action} as {topic} shifts",
            ],
            "summary_templates": [
                "Analysis indicates {finding} regarding {topic}. Experts suggest {implication}.",
                "Recent data shows {finding} in the banking sector. {source} reports {detail}.",
                "The {topic} situation has {change}. Industry analysts note {observation}.",
                "{source} confirms {finding} related to {topic}. This may affect {impact}.",
            ],
        },
        "market": {
            "sources": [
                "Bloomberg Markets",
                "CNBC",
                "MarketWatch",
                "Yahoo Finance",
                "Reuters Markets",
                "The Motley Fool",
                "Seeking Alpha",
            ],
            "topics": [
                "stock market performance",
                "market volatility",
                "sector rotation",
                "earnings reports",
                "market sentiment",
                "trading volumes",
                "index movements",
            ],
            "title_templates": [
                "Markets {action} as {topic} dominates trading",
                "{source} reports: {topic} drives market {direction}",
                "Stock indices {action} amid {topic}",
                "Traders react to {topic} developments",
                "Market analysis: {topic} implications",
            ],
            "summary_templates": [
                "Market data indicates {finding} in recent sessions. Analysts at {source} suggest {implication}.",
                "Trading activity shows {finding} related to {topic}. {source} reports {detail}.",
                "The {topic} has led to {change} in market behavior. Experts observe {observation}.",
                "{source} analysis reveals {finding}. This development may impact {impact}.",
            ],
        },
        "investment": {
            "sources": [
                "Morningstar",
                "Vanguard Research",
                "Fidelity Insights",
                "BlackRock Investment Institute",
                "J.P. Morgan Asset Management",
                "Goldman Sachs Research",
                "Barron's",
            ],
            "topics": [
                "portfolio allocation",
                "investment returns",
                "risk management",
                "asset diversification",
                "fund performance",
                "investment strategies",
                "retirement planning",
            ],
            "title_templates": [
                "{source} research on {topic}",
                "Investment outlook: {topic} considerations",
                "Portfolio managers discuss {topic}",
                "{source} analysis: {topic} trends",
                "Expert insights on {topic}",
            ],
            "summary_templates": [
                "Research from {source} indicates {finding} for {topic}. Investors should consider {implication}.",
                "Analysis shows {finding} in {topic} strategies. {source} recommends {detail}.",
                "The {topic} landscape has {change}. Investment professionals note {observation}.",
                "{source} data reveals {finding}. This may influence {impact} decisions.",
            ],
        },
        "crypto": {
            "sources": [
                "CoinDesk",
                "Cointelegraph",
                "The Block",
                "Decrypt",
                "CryptoSlate",
                "Bitcoin Magazine",
                "Messari",
            ],
            "topics": [
                "cryptocurrency prices",
                "blockchain adoption",
                "regulatory developments",
                "DeFi protocols",
                "NFT markets",
                "crypto exchange activity",
                "institutional adoption",
            ],
            "title_templates": [
                "Crypto markets {action} as {topic} evolves",
                "{source} reports on {topic}",
                "Blockchain analysis: {topic} trends",
                "Digital asset {action} amid {topic}",
                "{source} coverage: {topic} developments",
            ],
            "summary_templates": [
                "Cryptocurrency data shows {finding} in {topic}. {source} analysts suggest {implication}.",
                "Blockchain metrics indicate {finding}. {source} reports {detail} regarding {topic}.",
                "The {topic} sector has {change}. Industry observers note {observation}.",
                "{source} analysis reveals {finding} in crypto markets. This may affect {impact}.",
            ],
        },
        "economic": {
            "sources": [
                "Bureau of Economic Analysis",
                "Bureau of Labor Statistics",
                "IMF",
                "World Bank",
                "The Economist",
                "OECD",
                "Congressional Budget Office",
            ],
            "topics": [
                "GDP growth",
                "inflation rates",
                "employment figures",
                "trade balances",
                "fiscal policy",
                "monetary policy",
                "economic indicators",
            ],
            "title_templates": [
                "Economic data shows {topic} {direction}",
                "{source} releases {topic} report",
                "Economists analyze {topic} trends",
                "{source} forecast: {topic} outlook",
                "Policy implications of {topic}",
            ],
            "summary_templates": [
                "Official data from {source} indicates {finding} for {topic}. Economists suggest {implication}.",
                "Economic indicators show {finding}. {source} reports {detail} on {topic}.",
                "The {topic} situation has {change}. Policy analysts note {observation}.",
                "{source} data reveals {finding}. This may influence {impact} in the economy.",
            ],
        },
    }

    # Generic fill-in values for templates
    _ACTIONS = ["surge", "decline", "stabilize", "shift", "respond", "adjust", "react"]
    _DIRECTIONS = ["upward", "downward", "sideways", "mixed", "positive", "negative"]
    _FINDINGS = [
        "significant changes",
        "notable trends",
        "mixed signals",
        "positive developments",
        "concerning patterns",
        "stable conditions",
        "emerging opportunities",
    ]
    _CHANGES = [
        "evolved significantly",
        "remained stable",
        "shown volatility",
        "improved notably",
        "faced challenges",
        "demonstrated resilience",
    ]
    _IMPLICATIONS = [
        "careful monitoring is warranted",
        "opportunities may emerge",
        "caution is advised",
        "further analysis is needed",
        "positive outcomes are possible",
        "risks should be considered",
    ]
    _OBSERVATIONS = [
        "this aligns with broader trends",
        "this represents a departure from norms",
        "historical patterns suggest caution",
        "similar conditions have preceded growth",
        "market participants are watching closely",
    ]
    _IMPACTS = [
        "investor sentiment",
        "market dynamics",
        "policy decisions",
        "consumer behavior",
        "institutional strategies",
    ]
    _DETAILS = [
        "ongoing developments",
        "recent changes",
        "emerging patterns",
        "key metrics",
        "important factors",
    ]

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the mock search provider.
        
        Args:
            seed: Optional random seed for reproducible results in testing.
        """
        self._rng = random.Random(seed)

    async def search(self, query: str, claim_type: str) -> list[SearchResult]:
        """Search for synthetic evidence based on query and claim type.
        
        Generates type-aware synthetic data that varies based on the claim type.
        Different claim types (banking, market, investment, crypto, economic)
        produce different evidence sets with domain-specific sources and content.
        
        Args:
            query: The search query text (used to influence result count).
            claim_type: The category of the claim to generate appropriate evidence.
        
        Returns:
            A list of SearchResult objects with synthetic but realistic-looking
            evidence data. Returns 3-7 results depending on query characteristics.
        """
        # Normalize claim type to lowercase, default to "economic" if unknown
        normalized_type = claim_type.lower() if claim_type else "economic"
        if normalized_type not in self._SOURCE_DATA:
            normalized_type = "economic"

        # Generate variable number of results (3-7) based on query hash
        query_hash = hash(query) if query else 0
        num_results = 3 + (abs(query_hash) % 5)

        results: list[SearchResult] = []
        source_data = self._SOURCE_DATA[normalized_type]

        for i in range(num_results):
            result = self._generate_result(source_data, normalized_type, i, num_results)
            results.append(result)

        # Sort by relevance score descending
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        return results

    def _generate_result(
        self,
        source_data: dict[str, Any],
        claim_type: str,
        index: int,
        total: int,
    ) -> SearchResult:
        """Generate a single synthetic search result.
        
        Args:
            source_data: Type-specific configuration for generating content.
            claim_type: The claim type for context.
            index: The result index (affects relevance score).
            total: Total number of results being generated.
        
        Returns:
            A SearchResult with synthetic but realistic content.
        """
        # Select source and topic
        source = self._rng.choice(source_data["sources"])
        topic = self._rng.choice(source_data["topics"])

        # Generate title
        title_template = self._rng.choice(source_data["title_templates"])
        title = self._fill_template(title_template, source, topic)

        # Generate summary
        summary_template = self._rng.choice(source_data["summary_templates"])
        summary = self._fill_template(summary_template, source, topic)

        # Generate timestamp (within last 30 days)
        days_ago = self._rng.randint(0, 30)
        hours_ago = self._rng.randint(0, 23)
        timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)

        # Generate relevance score (higher for earlier results)
        base_score = 0.95 - (index * 0.1)
        noise = self._rng.uniform(-0.05, 0.05)
        relevance_score = max(0.0, min(1.0, base_score + noise))

        return SearchResult(
            title=title,
            source=source,
            summary=summary,
            timestamp=timestamp.isoformat(),
            relevance_score=round(relevance_score, 3),
        )

    def _fill_template(self, template: str, source: str, topic: str) -> str:
        """Fill in a template string with random appropriate values.
        
        Args:
            template: Template string with {placeholder} markers.
            source: The source name to use.
            topic: The topic to use.
        
        Returns:
            Filled template string.
        """
        return template.format(
            source=source,
            topic=topic,
            action=self._rng.choice(self._ACTIONS),
            direction=self._rng.choice(self._DIRECTIONS),
            finding=self._rng.choice(self._FINDINGS),
            change=self._rng.choice(self._CHANGES),
            implication=self._rng.choice(self._IMPLICATIONS),
            observation=self._rng.choice(self._OBSERVATIONS),
            impact=self._rng.choice(self._IMPACTS),
            detail=self._rng.choice(self._DETAILS),
        )
