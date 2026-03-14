"""Azure Functions Python v2 – HTTP-triggered recommender

New programming model (decorator-based, no function.json).
Deploy on Consumption plan for free-tier showcase.
"""
from __future__ import annotations
import json
import logging
import pickle
from pathlib import Path

import numpy as np
import lightgbm as lgb
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ---------------------------------------------------------------------------
# Cold-start: load artifacts once
# ---------------------------------------------------------------------------
# Prefer non-Git runtime assets folder; keep legacy fallback for compatibility.
ROOT = Path(__file__).resolve().parent.parent  # HttpReco/ → wwwroot/
ART_CANDIDATES = [
    ROOT / "external_runtime_assets" / "azure" / "artifacts",
    ROOT / "artifacts",
]
ART = next((p for p in ART_CANDIDATES if p.exists()), ART_CANDIDATES[0])
logging.info("[Reco] Cold-start - loading artifacts from %s", ART)
model      = lgb.Booster(model_file=str(ART / "reranker.txt"))
last_click = np.load(ART / "last_click.npy",          allow_pickle=True)
cf_top300  = np.load(ART / "cf_i2i_top300.npy",       mmap_mode="r")
als_top100 = np.load(ART / "als_top100.npy",          mmap_mode="r")
tt_top200  = np.load(ART / "tt_top200.npy",           mmap_mode="r")
pop_list   = np.load(ART / "pop_list.npy",            mmap_mode="r")
item_vec   = np.load(ART / "final_twotower_item_vec.npy", mmap_mode="r")
user_vec   = np.load(ART / "final_twotower_user_vec.npy",  mmap_mode="r")

# ---- cold-start popularity tables ------------------------------------------
try:
    with open(ART / "top_lists.pkl", "rb") as fh:
        TOP = pickle.load(fh)
    logging.info("[Reco] Popularity tables loaded: %s", list(TOP))
except Exception as e:
    logging.warning("[Reco] Popularity tables unavailable: %s", e)
    TOP = {"global_top": pop_list}


# Load ground-truth clicks for demo display (valid_clicks.parquet).
# Ensure the file is copied into runtime artifacts before deployment.
try:
    import pandas as pd
    NUM_ITEMS = item_vec.shape[0]
    _gt_df = pd.read_parquet(ART / "valid_clicks.parquet", columns=["user_id", "click_article_id", "click_deviceGroup", "click_os", "click_country"])

    user_profiles = {}
    for _, row in _gt_df.iterrows():
        uid = int(row["user_id"])
        user_profiles[uid] = {
            "device": int(row["click_deviceGroup"]) if pd.notna(row["click_deviceGroup"]) else -1,
            "os":     int(row["click_os"])          if pd.notna(row["click_os"])          else -1,
            "country": str(row["click_country"]).upper() if pd.notna(row["click_country"]) else "",
        }

    _gt_valid = _gt_df[
        _gt_df.click_article_id.notna()
        & (_gt_df.click_article_id >= 0)
        & (_gt_df.click_article_id < NUM_ITEMS)
    ]
    ground_truth = dict(zip(_gt_valid.user_id.astype(int), _gt_valid.click_article_id.astype(int)))

    logging.info("[Reco] Ground-truth table loaded (%d users)", len(ground_truth))
    logging.info("[Reco] User profiles loaded (%d users)", len(user_profiles))
    if ground_truth:
        sample_items = list(ground_truth.items())[:5]
        logging.info("[Reco] First 5 ground-truth pairs: %s", sample_items)
except Exception as e:  # noqa: BLE001 – tolerate missing file in prod
    logging.warning("[Reco] Ground-truth and profiles not available: %s", e)
    ground_truth = {}
    user_profiles = {}

# ---------------------------------------------------------------------------
# Helpers (identical to offline pipeline)
# ---------------------------------------------------------------------------

def get_candidates(u: int) -> list[int]:
    seen, cand = set(), []
    last = int(last_click[u])
    if last != -1:
        for it in cf_top300[last]:
            if it not in seen:
                seen.add(int(it)); cand.append(int(it))
            if len(cand) == 300:
                break
    for it in als_top100[u]:
        if it not in seen:
            seen.add(int(it)); cand.append(int(it))
        if len(cand) == 400:
            break
    for it in pop_list:
        if it not in seen:
            seen.add(int(it)); cand.append(int(it))
        if len(cand) == 600:
            break
    for it in tt_top200[u]:
        if it not in seen:
            seen.add(int(it)); cand.append(int(it))
        if len(cand) == 800:
            break
    for it in pop_list:
        if len(cand) == 1000:
            break
        if it not in seen:
            seen.add(int(it)); cand.append(int(it))
    return cand


def build_features(u: int, cand: list[int]) -> np.ndarray:
    """Return (1000, 6) feature array"""
    uvec = user_vec[u]
    rows = []
    for r, it in enumerate(cand, start=1):
        rows.append([
            r if r <= 300 else 1001,
            r - 300 if 300 < r <= 400 else 1001,
            r - 400 if 400 < r <= 600 else 1001,
            r - 600 if 600 < r <= 800 else 1001,
            r,
            float(np.dot(uvec, item_vec[it]) / (
                np.linalg.norm(uvec) * np.linalg.norm(item_vec[it]) + 1e-9)),
        ])
    return np.asarray(rows, dtype=np.float32)

# ---------------------------------------------------------------------------
# HTTP route (POST /api/reco)
# ---------------------------------------------------------------------------


def _cold_reco(env: dict[str, object], k: int = 10) -> list[int]:
    """Return top-k from global popularity for cold users.

    Uses pop_list.npy which was built from TRAIN data in the notebooks,
    ensuring no data leakage when evaluating on validation/test users.
    """
    return [int(x) for x in pop_list[:k]]


@app.route(route="reco", methods=["POST"])
def http_reco(req: func.HttpRequest) -> func.HttpResponse:  # noqa: N802 – Azure signature
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}), status_code=400, mimetype="application/json")

    user_id = int(body.get("user_id", -1))
    if user_id < 0 or user_id >= len(last_click):
        return func.HttpResponse(
            json.dumps({"error": "user_id out of range"}), status_code=400, mimetype="application/json")

    k = max(1, min(int(body.get("k", 10)), 100))
    env_override = body.get("env", {}) if isinstance(body.get("env", {}), dict) else {}

    # Start with stored user profile if available, then apply manual overrides
    stored_profile = user_profiles.get(user_id, {})
    env = {
        "device": stored_profile.get("device", -1),
        "os": stored_profile.get("os", -1), 
        "country": stored_profile.get("country", "")
    }
    
    # Apply manual overrides if provided
    if "device" in env_override:
        env["device"] = env_override["device"]
    if "os" in env_override:
        env["os"] = env_override["os"]
    if "country" in env_override:
        env["country"] = str(env_override["country"]).upper()

    force_cold = bool(body.get("force_cold", False))
    is_cold = force_cold or last_click[user_id] == -1

    if is_cold:
        topk_ids = _cold_reco(env, k)
        logging.info("[Reco] cold user=%d stored=%s final_env=%s rec0=%s", 
                    user_id, stored_profile, env, topk_ids[:1] if topk_ids else None)
    else:
        cand = get_candidates(user_id)
        X = build_features(user_id, cand)
        scores = model.predict(X)
        topk_ids = [cand[i] for i in np.argsort(-scores)[:k]]
        logging.info("[Reco] warm user=%d stored=%s gt=%s rec0=%s", 
                    user_id, stored_profile, ground_truth.get(user_id), topk_ids[:1] if topk_ids else None)

    return func.HttpResponse(
        json.dumps({
            "recommendations": topk_ids,
            "ground_truth": ground_truth.get(user_id),
            "user_profile": {
                "stored": stored_profile,
                "used": env,
                "overrides_applied": bool(env_override)
            }
        }),
        mimetype="application/json")
