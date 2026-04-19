"""TruthNuke API Package.

This package contains the FastAPI routes and API configuration.
"""

from app.api.routes import configure_analyzer, get_analyzer, router

__all__ = [
    "router",
    "get_analyzer",
    "configure_analyzer",
]
