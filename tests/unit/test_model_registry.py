"""Unit tests for model registry orchestration."""

from src.models.base import (
    BaseRecommender,
    CandidateGenerator,
    ColdStartHandler,
    ModelRegistry,
    Reranker,
)


class DummyRecommender(BaseRecommender):
    def __init__(self) -> None:
        super().__init__("dummy")

    def load(self, artifacts_path) -> None:
        self._loaded = True

    def get_candidates(self, user_id: int, k: int = 100) -> list[int]:
        return [1, 2, 3][:k]


class DummyGenerator(CandidateGenerator):
    def generate_candidates(self, user_id: int, seen_items: set[int], k: int) -> list[int]:
        return [x for x in [1, 2, 3, 4] if x not in seen_items][:k]


class DummyReranker(Reranker):
    def rerank(self, user_id: int, candidates: list[int]) -> list[int]:
        return list(reversed(candidates))


class DummyColdStart(ColdStartHandler):
    def get_recommendations(self, context: dict, k: int) -> list[int]:
        return [10, 11, 12][:k]


def test_registry_is_not_ready_until_all_components_are_registered_and_loaded() -> None:
    reg = ModelRegistry()
    model = DummyRecommender()

    reg.register_model(model)
    reg.register_candidate_generator(DummyGenerator())
    reg.register_reranker(DummyReranker())
    reg.register_cold_start_handler(DummyColdStart())

    # Not ready because model is not loaded yet.
    assert reg.is_ready() is False

    model.load(None)
    assert reg.is_ready() is True


def test_registry_status_contains_expected_fields() -> None:
    reg = ModelRegistry()
    model = DummyRecommender()
    model.load(None)
    reg.register_model(model)
    reg.register_candidate_generator(DummyGenerator())
    reg.register_reranker(DummyReranker())
    reg.register_cold_start_handler(DummyColdStart())

    status = reg.get_status()
    assert "models" in status
    assert "candidate_generators" in status
    assert "reranker_ready" in status
    assert "cold_start_ready" in status
    assert status["overall_ready"] is True
