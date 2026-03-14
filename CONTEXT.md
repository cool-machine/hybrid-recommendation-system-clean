# CONTEXT — OCP9 Hybrid Recommender

> Single source of truth for session handoff. Update after every completed step and before ending any session.

---

## System summary

OpenClassrooms project P9: a production hybrid news recommendation system. A **Streamlit Cloud** frontend calls a **single Azure Functions endpoint** (`POST /api/reco`) that routes each user to one of two paths:

- **Cold path** (no click history): context-aware popularity blend drawn from precomputed `top_lists.pkl`
- **Warm path** (has history): 4-source candidate assembly (CF + ALS + Popularity + Two-Tower) → LightGBM reranker

All artifacts (≈ 433 MB) are bundled into the deploy zip and memory-mapped at Azure Functions cold start — no external database or cache at runtime. The system covers 65 536 users and 65 536 article IDs.

---

## Repo map

| Path | Role |
|---|---|
| `streamlit_app.py` | Streamlit Cloud wrapper entry point |
| `deployment/streamlit/app.py` | Canonical Streamlit frontend |
| `deployment/azure_functions/HttpReco/__init__.py` | **Deployed production function** — artifact loading, routing, inference |
| `src/service.py` | Clean OOP service layer (mirrors deployed logic) |
| `src/config.py` | Artifact names, limits, runtime config |
| `src/models/collaborative_filtering.py` | ItemToItemCF, ALSRecommender, TwoTowerRecommender |
| `src/models/popularity.py` | PopularityRecommender, ContextualPopularity |
| `src/models/reranking.py` | LightGBMReranker |
| `src/models/base.py` | BaseRecommender, CandidateGenerator, Reranker, ModelRegistry |
| `notebooks/collaborative-filtering.ipynb` | U2U CF and I2I CF research + metrics |
| `notebooks/matrix-factorization-als.ipynb` | ALS research + hyperparameter search |
| `notebooks/hybrid-ensemble-recommendation.ipynb` | Two-Tower, popularity, ensemble, LightGBM |
| `tests/unit/` | pytest tests for config, registry, contextual popularity |
| `docs/` | Architecture, API reference, getting-started guide |
| `ALGORITHMS.md` | Full algorithm story: results, verdicts, design rationale |
| `secondary_assets/external_runtime_assets/azure/artifacts/` | Local copy of all deployed artifacts (gitignored) |
| `secondary_assets/azure_ml_notebooks/` | Downloaded AzureML notebooks + metrics (gitignored) |
| `livrables/My_Content_Gvishiani_George/` | OpenClassrooms submission deck (PPTX) |

---

## Azure deployment (verified live 2026-03-14)

| Resource | Value |
|---|---|
| Resource group | `ocp9` (Central US) |
| Function App | `ocp9funcapp-recsys` — **Running**, Python 3.10, Consumption plan |
| Live endpoint | `POST https://ocp9funcapp-recsys.azurewebsites.net/api/reco` |
| Auth level | Anonymous (no API key required) |
| Storage account | `ocp95449056669` (Standard LRS, StorageV2) |
| Last deploy zip | `scm-latest-ocp9funcapp-recsys.zip` — 409 MB Squashfs, **redeployed 2026-03-14** |
| AzureML workspace | `ocp9` (used for training; not involved in serving) |

> **Note:** Azure stores the app as a Squashfs filesystem image (not a plain zip). You deploy by uploading a normal zip via `func azure functionapp publish`; Oryx converts it automatically. Never upload Squashfs directly.

**Other resources in `ocp9`:** Application Insights (`p9cpu`), AzureML compute (`CF-II`, `may23-2025`), storage blobs.

---

## Deployed artifact manifest (all shape-verified locally)

| File | Shape / Type | What it encodes |
|---|---|---|
| `last_click.npy` | (65 536,) int32 | Last clicked article per user; **−1 = cold user** |
| `cf_i2i_top300.npy` | (65 536, 300) int32 | For every article: 300 most similar articles (item-to-item CF) |
| `als_top100.npy` | (65 536, 100) int32 | For every user: ALS top-100 personalized candidates |
| `tt_top200.npy` | (65 536, 200) int32 | For every user: Two-Tower cosine-similarity top-200 candidates |
| `pop_list.npy` | (65 536,) int32 | All articles ranked by global click frequency |
| `final_twotower_user_vec.npy` | (65 536, 250) float32 | Two-Tower user embedding vectors |
| `final_twotower_item_vec.npy` | (65 536, 250) float32 | Two-Tower item embedding vectors |
| `reranker.txt` | LightGBM Booster | 6-feature gradient-boosted ranker |
| `top_lists.pkl` | dict, 5 keys | Precomputed contextual popularity tables (see below) |
| `valid_clicks.parquet` | DataFrame | Ground-truth next click + stored user profiles (device/os/country) |

### top_lists.pkl keys

Rebuilt 2026-03-14 from `valid_clicks.parquet` so keys match runtime encoding exactly (numeric OS/device codes, country as str e.g. `"1"`).

| Key | Type | Segments | Example top-3 |
|---|---|---|---|
| `global_top` | ndarray (50,) int32 | — | `#3436, #14963, #26859` |
| `by_os` | dict[int → ndarray] | 8 OS codes from parquet | OS 17 → `#14963, #3436, #26859` |
| `by_dev` | dict[int → ndarray] | 4 device codes from parquet | dev 1 → `#14963, #3436, #26859` |
| `by_os_reg` | dict[(int,str) → ndarray] | 56 (OS, country-str) combos | (17,'1') → `#14963, #3436, #26859` |
| `by_dev_reg` | dict[(int,str) → ndarray] | 34 (dev, country-str) combos | (1,'1') → `#14963, #3436, #26859` |

---

## Hybrid model: full data flow

> Detailed call sequences with excluded-algorithm tables: [`ALGORITHMS.md § Production Call Sequence`](ALGORITHMS.md#production-call-sequence) and [`docs/architecture/README.md § Algorithm Call Sequences`](docs/architecture/README.md).

### Request entry

```
POST /api/reco  { user_id, k=10, env={device, os, country} }
      │
      ├─ JSON parse + user_id range check
      ├─ Load stored profile from valid_clicks.parquet
      ├─ Apply env overrides if provided
      └─ Check: last_click[user_id] == -1 ?
              │
         Yes (cold) ──────────────────────────────────────────►  COLD PATH
              │
         No (warm) ──────────────────────────────────────────►  WARM PATH
```

### Cold path — contextual popularity blend (no inference)

```
env: { device, os, country }
  │
  ├─ by_os[os]              → 2 items
  ├─ by_dev[device]         → 2 items
  ├─ by_os_reg[(os,country)]→ 3 items
  ├─ by_dev_reg[(dev,ctry)] → 3 items
  └─ global_top             → fill to k (safety net)
       (dedup with seen-set at every step)
  └─►  top-k response
```

Allocation formula for k=10: `⌊k×2/10⌋` × 2 sources + `⌊k×3/10⌋` × 1 source + remainder. No model inference. Pure precomputed table lookup.

### Warm path — candidate assembly → LightGBM rerank

**Step 1: Build candidate pool (up to 1 000 items, deduplicated)**

```
last_click[user_id] → article i
  cf_i2i_top300[i]   → up to 300 items  │ I2I CF: "similar to last read"
  als_top100[user]   → up to 100 items  │ ALS: "personal latent taste"
  pop_list           → fill to  600     │ Popularity: safety + diversity
  tt_top200[user]    → up to 200 items  │ Two-Tower: "semantic affinity"
  pop_list (cont.)   → fill to 1 000    │ Final safety net
```

**Step 2: Build 6-feature matrix (1000 × 6)**

| # | Feature | Value when item NOT from that source |
|---|---|---|
| 0 | CF rank (1–300) | 1001 |
| 1 | ALS rank (1–100) | 1001 |
| 2 | Popularity rank (1–200) | 1001 |
| 3 | Two-Tower rank (1–200) | 1001 |
| 4 | Global pool rank (1–1000) | always set |
| 5 | Cosine sim: `dot(user_vec[u], item_vec[i]) / (‖u‖·‖i‖ + 1e-9)` | always set |

**Step 3: LightGBM scoring + sort**

```python
scores   = model.predict(X_1000x6)          # LightGBM Booster
topk_ids = [cand[i] for i in argsort(-scores)[:k]]
```

### Response payload

```json
{
  "recommendations": [30077, 30650, 26551, 31411, 30545],
  "ground_truth": 36162,
  "user_profile": {
    "stored": { "device": 1, "os": 17, "country": "1" },
    "used":   { "device": 1, "os": 17, "country": "1" },
    "overrides_applied": false
  }
}
```

---

## Algorithm performance summary

| Algorithm | recall@10 | recall@100 | Mean rank | Role |
|---|---|---|---|---|
| U2U CF | 0.59% | 3.32% | 22 985 | Baseline only, not deployed |
| **I2I CF** | 1.55% | **19.69%** | 2 460 | 300 candidates (highest priority) |
| **ALS** | 1.98% | 16.54% | 7 554 | 100 candidates (diversity) |
| Two-Tower | — | 3.13% | 23 659 | 200 candidates + cosine feature |
| Popularity (global) | 12.11% | — | — | Cold start backbone |
| Popularity (contextual) | 17.21% | — | — | Cold start with context |
| LightGBM reranker | 18.58%* | — | — | Final ranker (warm only) |
| **Hybrid ensemble** | **22.99%**† | — | — | **Production** |
| Candidate pool recall | — | — (75%@1000) | — | Pre-rerank coverage |

\* hit_rate@10 on 13 108 warm users  
† recall@10 on 13 108 warm users; 17.21% across all 65 536 users  
Full details and verdicts: see `ALGORITHMS.md`

---

## Live test results (2026-03-13, endpoint verified)

```bash
# User 1 — warm user
POST /api/reco {"user_id":1,"k":5}
→ {"recommendations":[30077,30650,26551,31411,30545],"ground_truth":36162,
   "user_profile":{"stored":{"device":1,"os":17,"country":"1"},...}}

# User 0 — near-cold (global pop items visible in results)
POST /api/reco {"user_id":0,"k":5}
→ {"recommendations":[5747,3436,29902,9999,8574],"ground_truth":26859,...}

# User 5 — warm, with env override (overrides_applied: true)
POST /api/reco {"user_id":5,"k":5,"env":{"os":0,"device":0,"country":"US"}}
→ {"recommendations":[3160,27647,27947,11385,30119],"ground_truth":25207,
   "user_profile":{"stored":{"device":1,"os":12,"country":"1"},"used":{"device":0,"os":0,"country":"US"},"overrides_applied":true}}
```

---

## Known issues / technical debt

| Issue | Severity | Location | Detail |
|---|---|---|---|
| ~~**Country stored as numeric**~~ | ~~Medium~~ | — | **FIXED 2026-03-14.** `top_lists.pkl` rebuilt from `valid_clicks.parquet`; keys now match runtime encoding (numeric OS/device codes, country as `"1"` etc.). `extend()` numpy crash also fixed. Redeployed. |
| **Streamlit context dropdowns use wrong codes** | Low | `deployment/streamlit/app.py` lines 141-143 | The "Context" expander hardcodes OS 0–5 (Android…) and device 0–2, which don't match parquet codes ({2,3,5,12…} and {1,3,4,5}). Manual overrides from that panel still miss most segments. The demo's stored-profile path is correct; only the manual-override UI is misaligned. |
| **Algorithm ranks 0–3 always 1001 in `src/models/reranking.py`** | Medium | `src/models/reranking.py::_build_features` | The clean OOP reranker defaults all 4 algorithm ranks to 1001. The deployed function (`__init__.py::build_features`) correctly computes them from pool position ranges. The `src/` version is diverged from production. |
| **No health/readiness endpoint** | Low | Azure Functions | No `GET /health` — cold start check requires a real `/api/reco` POST. |

---

## What we did earlier (stable milestones)

- Downloaded and audited Azure ML notebook groups from `Users/george.gvishiani/ocp9/v2` and `/notebooks`
- Extracted consolidated evaluation metrics (popularity, CF, ALS, hybrid, LightGBM)
- Created `CONTEXT.md` as the handoff source of truth
- Audited and fixed stale docs in `docs/architecture/README.md`
- Verified backend tests: 7 passed, 1 warning
- Created `ALGORITHMS.md` with full algorithm story, metrics, and production verdicts

## What we did recently (2026-03-14 session)

- Compared local artifacts vs deployed Azure package byte-for-byte: all 13 files matched exactly (MD5 verified via `scripts/compare_artifacts.py` — see local-only tools below)
- Discovered the deployed package is a **Squashfs** image, not a zip; installed `squashfs-tools` to inspect it
- Confirmed the artifact path bug: `ROOT = parents[3]` resolved to `/home` instead of `wwwroot`; fixed to `parent.parent` in `HttpReco/__init__.py`
- Fixed **country/OS/device encoding mismatch**: `top_lists.pkl` was built from training data with different encodings (OS 0–5, device 0–2, country 'US'/'FR') vs parquet values (OS 12–20, device 1–5, country uint8 '1'–'11'). All contextual lookups were silently missing → global_top fallback for every cold user
- Rebuilt `top_lists.pkl` from `valid_clicks.parquet` via updated `src/training/build_popularity_lists.py`
- Fixed latent crash in `_cold_reco::extend()`: `if not arr` raises `ValueError` on numpy arrays; changed to `if arr is None`
- Redeployed to Azure via `func azure functionapp publish ocp9funcapp-recsys --python` — verified live (user 1 → `[30077, 30650, …]`, user 500 → `[37279, 48457, …]`)

### Previous session (2026-03-13)

- Patched PPTX slide 12 with actual precomputed popularity data → saved as `_v2.pptx`
- Connected to Azure, inspected all resources, ran three live API calls
- Recorded complete hybrid model data flow + algorithm table
- Created `docs/artifacts.md` with full per-artifact reference
- Confirmed country encoding root cause: `data-processing.ipynb` stores `click_country` as `uint8`

---

## Local-only tools (not tracked in git)

| Tool | Location | Purpose |
|---|---|---|
| `scripts/compare_artifacts.py` | local only (gitignored) | Fingerprint (MD5 + size) local artifacts and compare vs the deployed Azure Squashfs. Three modes: `--fingerprint-local`, `--fingerprint-zip`, `--compare`. Run from repo root with `python scripts/compare_artifacts.py --fingerprint-local`. Requires `squashfs-tools` (`brew install squashfs`) to inspect the deployed image. |
| `artifacts_local.json` | local only (gitignored) | Last fingerprint of local artifacts (generated 2026-03-14) |
| `artifacts_deployed.json` | local only (gitignored) | Last fingerprint of deployed artifacts (generated 2026-03-14; all 13 files matched local) |

---

## Where we stopped

- Last action: fixed country/OS/device encoding bug, fixed `extend()` crash, fixed `ROOT` path, redeployed, verified live
- Files committed: `deployment/azure_functions/HttpReco/__init__.py`, `src/training/build_popularity_lists.py`, `CONTEXT.md`, `.gitignore`

---

## Immediate next steps

- Open `_v2.pptx` in PowerPoint to visually verify slide 12 layout; promote to canonical deck if good
- Fix `src/models/reranking.py::_build_features` to match deployed algorithm-rank logic (TDD)
- Fix Streamlit context-dropdown labels to use actual parquet codes for OS and device
- Review remaining slides for stale content

## After immediate next steps

- Introduce `docs/dev-notes.md` and `docs/DESIGN.md` as canonical targets
- Revisit evaluation metrics notebook consolidation

---

## Last test run

- Timestamp: 2026-03-13 21:53:59 CET
- Command: `uv run pytest tests/ -v`
- Status: PASS — 7 passed, 1 warning

## New/changed test files

- None in this session (docs-only steps — TDD exception applies)

---

## Session end checkpoint

---- 2026-03-14 CET
- branch: `main`
- working tree: clean (all changes committed and pushed)
- remote: `https://github.com/cool-machine/hybrid-recommendation-system.git`
- Azure: live and verified — `func azure functionapp publish` completed successfully
