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

import pandas as pd

# ---------------------------------------------------------------------------
# Defaults — relative to repo root (two levels above this file)
# ---------------------------------------------------------------------------
_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_ART = _REPO / "secondary_assets" / "external_runtime_assets" / "azure" / "artifacts"
_DEFAULT_INPUT = _DEFAULT_ART / "valid_clicks.parquet"
_DEFAULT_OUTPUT = _DEFAULT_ART / "top_lists.pkl"

TOP_K = 50


def topk_list(series: pd.Series, k: int = TOP_K) -> list[int]:
    """Return top-k article IDs as plain Python ints — no numpy types.

    Using plain Python ints ensures the pickle is compatible across numpy
    versions and Python runtimes without silent key-lookup misses.
    """
    return [int(x) for x in series.value_counts().head(k).index]


def _norm_key(key: object) -> object:
    """Normalise a groupby key to plain Python types (int or str), never numpy."""
    if isinstance(key, tuple):
        # Multi-column group: normalise each element
        return tuple(_norm_key(k) for k in key)
    if isinstance(key, str):
        return key
    return int(key)  # numpy int* → plain Python int


def _groupby_topk(df: pd.DataFrame, group_cols: list[str], k: int = TOP_K) -> dict:
    """Group df by group_cols, compute top-k article IDs per group.

    Returns a dict whose keys are plain Python ints (or tuples of plain Python
    ints and strs), never numpy integer subtypes.  Dict values are plain Python
    lists of ints for maximum pickle compatibility across numpy/Python versions.
    """
    result: dict = {}
    multi = len(group_cols) > 1
    grouped = df.groupby(group_cols)["click_article_id"]
    for raw_key, series in grouped:
        articles = topk_list(series, k)
        if not articles:
            continue
        # pandas returns tuples for multi-col groups and scalars for single-col.
        # When passing a list with one element, some pandas versions still wrap
        # the key in a 1-tuple — unwrap it for single-col case.
        if multi:
            norm_key = _norm_key(raw_key if isinstance(raw_key, tuple) else (raw_key,))
        else:
            key_scalar = raw_key[0] if isinstance(raw_key, tuple) else raw_key
            norm_key = _norm_key(key_scalar)
        result[norm_key] = articles
    return result


def build(click_path: Path, out_path: Path) -> None:
    print(f"Reading click log from {click_path}")
    cols = ["click_deviceGroup", "click_os", "click_country", "click_article_id"]
    df = pd.read_parquet(click_path, columns=cols)

    # Exclude sentinel rows (cold users have click_article_id=0, not real clicks)
    df = df[df["click_article_id"] > 0].copy()

    # Convert country to str so keys match runtime behaviour:
    #   __init__.py stores country as str(row["click_country"]).upper()
    # For numeric uint8/int codes this produces "1", "10", etc.
    df["click_country"] = df["click_country"].astype(str)

    # Convert os/dev to plain Python int so dict keys are consistent
    # regardless of original numpy integer subtype (uint8, int64, …).
    df["click_os"] = df["click_os"].astype(int)
    df["click_deviceGroup"] = df["click_deviceGroup"].astype(int)

    res: dict = {}

    print("Computing global_top …")
    res["global_top"] = topk_list(df["click_article_id"])

    print("Computing by_os …")
    res["by_os"] = _groupby_topk(df, ["click_os"])

    print("Computing by_dev …")
    res["by_dev"] = _groupby_topk(df, ["click_deviceGroup"])

    print("Computing by_os_reg …")
    res["by_os_reg"] = _groupby_topk(df, ["click_os", "click_country"])

    print("Computing by_dev_reg …")
    res["by_dev_reg"] = _groupby_topk(df, ["click_deviceGroup", "click_country"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(pickle.dumps(res, protocol=4))
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
