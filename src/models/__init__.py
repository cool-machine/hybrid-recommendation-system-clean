"""Recommendation models package."""

from .base import BaseRecommender, CandidateGenerator, ColdStartHandler, ModelRegistry, Reranker

__all__ = [
    "BaseRecommender",
    "CandidateGenerator", 
    "ColdStartHandler",
    "ModelRegistry",
    "Reranker",
    "ALSRecommender",
    "ItemToItemCF", 
    "TwoTowerRecommender",
    "ContextualPopularity",
    "PopularityRecommender",
    "LightGBMReranker",
]


def __getattr__(name: str):
    """Lazy imports to avoid loading heavy ML deps during test discovery."""
    if name in {"ALSRecommender", "ItemToItemCF", "TwoTowerRecommender"}:
        from .collaborative_filtering import ALSRecommender, ItemToItemCF, TwoTowerRecommender
        return {
            "ALSRecommender": ALSRecommender,
            "ItemToItemCF": ItemToItemCF,
            "TwoTowerRecommender": TwoTowerRecommender,
        }[name]
    if name in {"ContextualPopularity", "PopularityRecommender"}:
        from .popularity import ContextualPopularity, PopularityRecommender
        return {
            "ContextualPopularity": ContextualPopularity,
            "PopularityRecommender": PopularityRecommender,
        }[name]
    if name == "LightGBMReranker":
        from .reranking import LightGBMReranker
        return LightGBMReranker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")