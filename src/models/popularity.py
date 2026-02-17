"""Popularity-based recommendation models."""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .base import BaseRecommender, CandidateGenerator, ColdStartHandler

logger = logging.getLogger(__name__)


class PopularityRecommender(BaseRecommender, CandidateGenerator):
    """Global popularity-based recommender."""
    
    def __init__(self):
        super().__init__("Popularity")
        self._popularity_list: Optional[np.ndarray] = None
    
    def load(self, artifacts_path: Path) -> None:
        """Load global popularity rankings."""
        try:
            pop_file = artifacts_path / "pop_list.npy"
            self._popularity_list = np.load(pop_file, mmap_mode="r")
            
            self._loaded = True
            logger.info(f"Loaded popularity model - {len(self._popularity_list)} items")
            
        except Exception as e:
            logger.error(f"Failed to load popularity model: {e}")
            raise
    
    def get_candidates(self, user_id: int, k: int = 500) -> List[int]:
        """Get popular items as candidates."""
        if not self._loaded:
            raise RuntimeError(f"{self.name} model not loaded")
        
        return self.generate_candidates(user_id, set(), k)
    
    def generate_candidates(self, user_id: int, seen_items: set[int], k: int) -> List[int]:
        """Generate popularity candidates excluding seen items."""
        if not self._loaded:
            return []
        
        candidates = []
        for item_id in self._popularity_list:
            item_id = int(item_id)
            if item_id not in seen_items:
                candidates.append(item_id)
            if len(candidates) >= k:
                break
        
        return candidates


class ContextualPopularity(ColdStartHandler):
    """Context-aware popularity for cold-start users."""
    
    def __init__(self):
        self._loaded = False
        self._popularity_tables: Dict[str, Any] = {}
        self._global_fallback: Optional[np.ndarray] = None
    
    def load(self, artifacts_path: Path) -> None:
        """Load contextual popularity tables."""
        try:
            # Try to load contextual popularity tables
            try:
                with open(artifacts_path / "top_lists.pkl", "rb") as f:
                    self._popularity_tables = pickle.load(f)
                logger.info(f"Loaded contextual popularity tables: {list(self._popularity_tables.keys())}")
            except FileNotFoundError:
                logger.warning("Contextual popularity tables not found, using global fallback only")
                self._popularity_tables = {}
            
            # Load global fallback
            self._global_fallback = np.load(artifacts_path / "pop_list.npy", mmap_mode="r")
            
            self._loaded = True
            logger.info("Loaded contextual popularity cold-start handler")
            
        except Exception as e:
            logger.error(f"Failed to load contextual popularity: {e}")
            raise
    
    def get_recommendations(self, context: Dict[str, Any], k: int = 10) -> List[int]:
        """Get context-aware recommendations for cold users."""
        if not self._loaded:
            raise RuntimeError("Contextual popularity not loaded")
        
        device = context.get("device", -1)
        os = context.get("os", -1) 
        country = str(context.get("country", "")).upper()
        
        recommendations: List[int] = []
        seen: set[int] = set()
        
        # Calculate allocation for each context dimension
        allocation = self._calculate_allocation(k)
        
        # Try to get recommendations from each context dimension
        self._extend_from_context("by_os", os, allocation["os_global"], recommendations, seen)
        self._extend_from_context("by_dev", device, allocation["device_global"], recommendations, seen)
        
        # Regional context (OS + country)
        if "by_os_reg" in self._popularity_tables:
            os_country_key = (os, country)
            self._extend_from_table(
                self._popularity_tables["by_os_reg"].get(os_country_key), 
                allocation["os_regional"], 
                recommendations, 
                seen
            )
        
        # Regional context (device + country)
        if "by_dev_reg" in self._popularity_tables:
            dev_country_key = (device, country)
            self._extend_from_table(
                self._popularity_tables["by_dev_reg"].get(dev_country_key),
                allocation["device_regional"],
                recommendations,
                seen
            )
        
        # Fill remaining slots with global popularity
        if len(recommendations) < k and self._global_fallback is not None:
            remaining = k - len(recommendations)
            self._extend_from_table(self._global_fallback, remaining, recommendations, seen)
        
        return recommendations[:k]
    
    def _calculate_allocation(self, k: int) -> Dict[str, int]:
        """Calculate how many recommendations to get from each context dimension."""
        return {
            "os_global": max(1, k * 2 // 10),
            "device_global": max(1, k * 2 // 10),
            "os_regional": max(1, k * 3 // 10),
            "device_regional": k - max(1, k * 2 // 10) * 2 - max(1, k * 3 // 10)
        }
    
    def _extend_from_context(self, table_name: str, key: Any, n: int, 
                           recommendations: List[int], seen: set[int]) -> int:
        """Extend recommendations from a specific context table."""
        if table_name not in self._popularity_tables:
            return 0
        
        table = self._popularity_tables[table_name].get(key)
        return self._extend_from_table(table, n, recommendations, seen)
    
    def _extend_from_table(self, items: Optional[Any], n: int, 
                          recommendations: List[int], seen: set[int]) -> int:
        """Extend recommendations from an item array."""
        if items is None or n <= 0:
            return 0
        
        added = 0
        for item in items:
            item = int(item)
            if item not in seen:
                seen.add(item)
                recommendations.append(item)
                added += 1
                if added == n or len(recommendations) >= 100:  # Safety limit
                    break
        
        return added
    
    def is_loaded(self) -> bool:
        """Check if the cold-start handler is ready."""
        return self._loaded