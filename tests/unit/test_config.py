"""Lightweight tests for active configuration behavior."""
from pathlib import Path

import pytest

from src.config import Config, EnvironmentConfig


def test_environment_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DEBUG_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")

    cfg = EnvironmentConfig.from_env()
    assert cfg.log_level == "DEBUG"
    assert cfg.debug_mode is True
    assert cfg.environment == "development"


def test_config_validate_raises_when_artifacts_dir_missing(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does_not_exist"
    cfg = Config.load(missing_dir)

    with pytest.raises(ValueError):
        cfg.validate()


def test_config_validate_passes_with_required_files(tmp_path: Path) -> None:
    art = tmp_path / "artifacts"
    art.mkdir(parents=True)

    # Minimal critical files required by Config.validate
    required = [
        "reranker.txt",
        "last_click.npy",
        "cf_i2i_top300.npy",
        "als_top100.npy",
        "pop_list.npy",
    ]
    for fname in required:
        (art / fname).write_bytes(b"test")

    cfg = Config.load(art)
    cfg.validate()  # Should not raise
