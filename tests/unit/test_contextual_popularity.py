"""Unit tests for cold-start contextual popularity logic."""

import numpy as np

from src.models.popularity import ContextualPopularity


def _build_loaded_handler() -> ContextualPopularity:
    h = ContextualPopularity()
    h._loaded = True
    h._popularity_tables = {
        "by_os": {1: [101, 102, 103]},
        "by_dev": {0: [102, 104, 105]},
        "by_os_reg": {(1, "US"): [106, 107]},
        "by_dev_reg": {(0, "US"): [107, 108]},
    }
    h._global_fallback = np.array([109, 110, 111, 112], dtype=np.int64)
    return h


def test_get_recommendations_returns_k_and_unique_items() -> None:
    h = _build_loaded_handler()
    recs = h.get_recommendations({"device": 0, "os": 1, "country": "us"}, k=8)

    assert len(recs) == 8
    assert len(set(recs)) == len(recs)


def test_get_recommendations_uses_global_fallback_when_context_missing() -> None:
    h = _build_loaded_handler()
    recs = h.get_recommendations({"device": 9, "os": 99, "country": "zz"}, k=3)

    assert recs == [109, 110, 111]
