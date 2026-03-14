#!/usr/bin/env python
"""Build segment-based popularity lists for cold-start recommendations.

The script reads a click log parquet that contains columns:
    click_deviceGroup  (numeric code, matches runtime user profile)
    click_os           (numeric code, matches runtime user profile)
    click_country      (numeric code stored as uint8 in valid_clicks.parquet;
                        converted to str here so keys match what the runtime
                        stores via str(row["click_country"]).upper())
    click_article_id

It outputs top_lists.pkl with keys:
    global_top: np.ndarray
    by_os: Dict[int, np.ndarray]
    by_dev: Dict[int, np.ndarray]
    by_os_reg: Dict[Tuple[int, str], np.ndarray]
    by_dev_reg: Dict[Tuple[int, str], np.ndarray]

Keys are derived directly from the source parquet, so they always match
the encoding stored in user_profiles at runtime — no separate mapping needed.

Usage:
    # rebuild from valid_clicks.parquet into the standard artifacts dir
    python src/training/build_popularity_lists.py

    # explicit paths
    python src/training/build_popularity_lists.py \\
        --input  secondary_assets/external_runtime_assets/azure/artifacts/valid_clicks.parquet \\
        --output secondary_assets/external_runtime_assets/azure/artifacts/top_lists.pkl
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Defaults — relative to repo root (two levels above this file)
# ---------------------------------------------------------------------------
_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_ART = _REPO / "secondary_assets" / "external_runtime_assets" / "azure" / "artifacts"
_DEFAULT_INPUT = _DEFAULT_ART / "valid_clicks.parquet"
_DEFAULT_OUTPUT = _DEFAULT_ART / "top_lists.pkl"

TOP_K = 50


def topk(series: pd.Series, k: int = TOP_K) -> np.ndarray:
    return series.value_counts().head(k).index.to_numpy(dtype=np.int32)


def build(click_path: Path, out_path: Path) -> None:
    print(f"Reading click log from {click_path}")
    cols = ["click_deviceGroup", "click_os", "click_country", "click_article_id"]
    df = pd.read_parquet(click_path, columns=cols)

    # Convert country to str so keys match runtime behaviour:
    #   __init__.py stores country as str(row["click_country"]).upper()
    # For numeric uint8 codes this produces "1", "10", etc.
    df["click_country"] = df["click_country"].astype(str)

    # Convert os/dev to plain Python int so dict keys are consistent
    # regardless of original numpy integer subtype (uint8, int64, …).
    df["click_os"] = df["click_os"].astype(int)
    df["click_deviceGroup"] = df["click_deviceGroup"].astype(int)

    res: dict = {}

    print("Computing global_top …")
    res["global_top"] = topk(df["click_article_id"])

    print("Computing by_os …")
    res["by_os"] = (
        df.groupby("click_os")["click_article_id"]
        .apply(topk)
        .to_dict()
    )

    print("Computing by_dev …")
    res["by_dev"] = (
        df.groupby("click_deviceGroup")["click_article_id"]
        .apply(topk)
        .to_dict()
    )

    print("Computing by_os_reg …")
    res["by_os_reg"] = (
        df.groupby(["click_os", "click_country"])["click_article_id"]
        .apply(topk)
        .to_dict()
    )

    print("Computing by_dev_reg …")
    res["by_dev_reg"] = (
        df.groupby(["click_deviceGroup", "click_country"])["click_article_id"]
        .apply(topk)
        .to_dict()
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(pickle.dumps(res))
    print(f"Saved → {out_path}")
    print(f"  by_os keys     : {sorted(res['by_os'].keys())}")
    print(f"  by_dev keys    : {sorted(res['by_dev'].keys())}")
    print(f"  by_os_reg keys : {sorted(res['by_os_reg'].keys())}")
    print(f"  by_dev_reg keys: {sorted(res['by_dev_reg'].keys())}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input",  type=Path, default=_DEFAULT_INPUT,
                        help=f"Source parquet. Default: {_DEFAULT_INPUT}")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT,
                        help=f"Output pkl. Default: {_DEFAULT_OUTPUT}")
    args = parser.parse_args()
    build(args.input, args.output)


if __name__ == "__main__":
    main()
