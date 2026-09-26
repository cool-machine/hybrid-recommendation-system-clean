"""AWS Lambda backend for the OCP9 hybrid-recommender demo."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

BUCKET = os.environ.get("OCP9_BUCKET", "")
PREFIX = os.environ.get("ARTIFACT_PREFIX", "artifacts/")
ARTIFACT_DIR = Path(os.environ.get("OCP9_ARTIFACT_DIR", "/tmp/ocp9-artifacts"))

# These are the ten files read by the serving path. The bucket also retains the
# three training-evidence files from the verified 13-file migration set.
REQUIRED_ARTIFACTS = {
    "als_top100.npy": "47f65aaf7cc3f7838a1d94b85c1895fc464f17397b7cbae53e67b78dd0592f7c",
    "cf_i2i_top300.npy": "574001651639c6acc2806a07c977f7df4ae1e402adeb991aae56dbcc58b5b4bd",
    "final_twotower_item_vec.npy": "d8087ddb58d284304252df2b45dca8c77d47417feb99dd89d84e84b1c84ff246",
    "final_twotower_user_vec.npy": "b61fc80335f7b684c38e600685fa934aebf3c4f4fb62c5e4177f02554d8c2412",
    "last_click.npy": "d23da1a456196e6d0246dcbc501158bea7688a4bc9958e86cfdb2e00743fe897",
    "pop_list.npy": "7f1b3679199536b45c1867f02b18ea9b05d6f331b7c1ac674542f668df4632a6",
    "reranker.txt": "65f4f3279409282268f915caa9fb755c208f5d481065e181c40654b6db25a733",
    "top_lists.pkl": "8e8bd04e6db8745eea90e37fe4c6a3506cf7b9fcf5eb2e62d6a1b2f4ef3672b0",
    "tt_top200.npy": "225ee70299e92eafdee82e2f347602fafcc15cc3379e369462a71cc848233550",
    "valid_clicks.parquet": "59547c6babc35f732d1386ff8a83e493fa9fa3e0283f16a6235bf8bdcce0c978",
}

_RUNTIME: dict[str, Any] | None = None
_S3 = None


def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _s3_client():
    global _S3
    if _S3 is None:
        import boto3

        _S3 = boto3.client("s3")
    return _S3


def _ensure_artifacts() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    for name, expected in REQUIRED_ARTIFACTS.items():
        destination = ARTIFACT_DIR / name
        if destination.exists() and _sha256(destination) == expected:
            continue
        if not BUCKET:
            raise RuntimeError(f"OCP9_BUCKET is required to retrieve {name}")
        temporary = destination.with_suffix(destination.suffix + ".download")
        LOGGER.info("Downloading s3://%s/%s%s", BUCKET, PREFIX, name)
        _s3_client().download_file(BUCKET, f"{PREFIX}{name}", str(temporary))
        actual = _sha256(temporary)
        if actual != expected:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"Artifact integrity check failed for {name}")
        temporary.replace(destination)


def _load_runtime() -> dict[str, Any]:
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME

    _ensure_artifacts()
    model = lgb.Booster(model_file=str(ARTIFACT_DIR / "reranker.txt"))
    last_click = np.load(ARTIFACT_DIR / "last_click.npy", allow_pickle=True)
    cf_top300 = np.load(ARTIFACT_DIR / "cf_i2i_top300.npy", mmap_mode="r")
    als_top100 = np.load(ARTIFACT_DIR / "als_top100.npy", mmap_mode="r")
    tt_top200 = np.load(ARTIFACT_DIR / "tt_top200.npy", mmap_mode="r")
    pop_list = np.load(ARTIFACT_DIR / "pop_list.npy", mmap_mode="r")
    item_vec = np.load(ARTIFACT_DIR / "final_twotower_item_vec.npy", mmap_mode="r")
    user_vec = np.load(ARTIFACT_DIR / "final_twotower_user_vec.npy", mmap_mode="r")

    with (ARTIFACT_DIR / "top_lists.pkl").open("rb") as stream:
        top_lists = pickle.load(stream)

    frame = pd.read_parquet(
        ARTIFACT_DIR / "valid_clicks.parquet",
        columns=[
            "user_id",
            "click_article_id",
            "click_deviceGroup",
            "click_os",
            "click_country",
        ],
    )
    profiles = {}
    for row in frame.itertuples(index=False):
        user_id = int(row.user_id)
        profiles[user_id] = {
            "device": int(row.click_deviceGroup) if pd.notna(row.click_deviceGroup) else -1,
            "os": int(row.click_os) if pd.notna(row.click_os) else -1,
            "country": str(row.click_country).upper() if pd.notna(row.click_country) else "",
        }

    valid = frame[
        frame.click_article_id.notna()
        & (frame.click_article_id >= 0)
        & (frame.click_article_id < item_vec.shape[0])
    ]
    ground_truth = dict(
        zip(valid.user_id.astype(int), valid.click_article_id.astype(int), strict=False)
    )

    _RUNTIME = {
        "model": model,
        "last_click": last_click,
        "cf_top300": cf_top300,
        "als_top100": als_top100,
        "tt_top200": tt_top200,
        "pop_list": pop_list,
        "item_vec": item_vec,
        "user_vec": user_vec,
        "top_lists": top_lists,
        "profiles": profiles,
        "ground_truth": ground_truth,
    }
    LOGGER.info("OCP9 runtime loaded with %d user profiles", len(profiles))
    return _RUNTIME


def _candidates(runtime: dict[str, Any], user_id: int) -> list[int]:
    seen: set[int] = set()
    candidates: list[int] = []
    last = int(runtime["last_click"][user_id])
    if last != -1:
        for item in runtime["cf_top300"][last]:
            value = int(item)
            if value not in seen:
                seen.add(value)
                candidates.append(value)
            if len(candidates) == 300:
                break
    for item in runtime["als_top100"][user_id]:
        value = int(item)
        if value not in seen:
            seen.add(value)
            candidates.append(value)
        if len(candidates) == 400:
            break
    for item in runtime["pop_list"]:
        value = int(item)
        if value not in seen:
            seen.add(value)
            candidates.append(value)
        if len(candidates) == 600:
            break
    for item in runtime["tt_top200"][user_id]:
        value = int(item)
        if value not in seen:
            seen.add(value)
            candidates.append(value)
        if len(candidates) == 800:
            break
    for item in runtime["pop_list"]:
        if len(candidates) == 1000:
            break
        value = int(item)
        if value not in seen:
            seen.add(value)
            candidates.append(value)
    return candidates


def _features(runtime: dict[str, Any], user_id: int, candidates: list[int]) -> np.ndarray:
    user_vector = runtime["user_vec"][user_id]
    rows = []
    for rank, item in enumerate(candidates, start=1):
        item_vector = runtime["item_vec"][item]
        rows.append(
            [
                rank if rank <= 300 else 1001,
                rank - 300 if 300 < rank <= 400 else 1001,
                rank - 400 if 400 < rank <= 600 else 1001,
                rank - 600 if 600 < rank <= 800 else 1001,
                rank,
                float(
                    np.dot(user_vector, item_vector)
                    / (np.linalg.norm(user_vector) * np.linalg.norm(item_vector) + 1e-9)
                ),
            ]
        )
    return np.asarray(rows, dtype=np.float32)


def _body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict):
        raise ValueError("JSON body must be an object")
    return value


def _recommend(body: dict[str, Any]) -> dict[str, Any]:
    runtime = _load_runtime()
    user_id = int(body.get("user_id", -1))
    if user_id < 0 or user_id >= len(runtime["last_click"]):
        return _response(400, {"error": "user_id out of range"})

    k = max(1, min(int(body.get("k", 10)), 100))
    override = body.get("env", {}) if isinstance(body.get("env", {}), dict) else {}
    stored = runtime["profiles"].get(user_id, {})
    environment = {
        "device": stored.get("device", -1),
        "os": stored.get("os", -1),
        "country": stored.get("country", ""),
    }
    if "device" in override:
        environment["device"] = override["device"]
    if "os" in override:
        environment["os"] = override["os"]
    if "country" in override:
        environment["country"] = str(override["country"]).upper()

    is_cold = bool(body.get("force_cold", False)) or runtime["last_click"][user_id] == -1
    if is_cold:
        recommendations = [int(value) for value in runtime["pop_list"][:k]]
    else:
        candidates = _candidates(runtime, user_id)
        scores = runtime["model"].predict(_features(runtime, user_id, candidates))
        recommendations = [candidates[index] for index in np.argsort(-scores)[:k]]

    return _response(
        200,
        {
            "recommendations": recommendations,
            "ground_truth": runtime["ground_truth"].get(user_id),
            "user_profile": {
                "stored": stored,
                "used": environment,
                "overrides_applied": bool(override),
            },
        },
    )


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    method = event.get("requestContext", {}).get("http", {}).get("method", "POST")
    path = (event.get("rawPath") or event.get("path") or "/").rstrip("/") or "/"
    if method == "GET" and path in {"/", "/health"}:
        return _response(
            200,
            {
                "status": "ok",
                "service": "ocp9-recommender",
                "artifacts_loaded": _RUNTIME is not None,
            },
        )
    if method != "POST" or path not in {"/api/reco", "/reco", "/"}:
        return _response(404, {"error": "Not found"})
    try:
        return _recommend(_body(event))
    except (ValueError, TypeError, json.JSONDecodeError):
        return _response(400, {"error": "Invalid JSON"})
    except Exception:
        LOGGER.exception("OCP9 request failed")
        return _response(500, {"error": "Recommendation service failed"})
