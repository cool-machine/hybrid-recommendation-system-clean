"""Modern recommendation system package."""

__version__ = "2.0.0"
__author__ = "Production ML Team"

from .config import Config, get_config

__all__ = ["Config", "get_config", "RecommendationService"]


def __getattr__(name: str):
    """Lazily import heavy modules to keep lightweight imports/test collection."""
    if name == "RecommendationService":
        from .service import RecommendationService
        return RecommendationService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")