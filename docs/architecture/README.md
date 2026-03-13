# System Architecture

> Canonical architecture reference. For algorithm details and performance metrics see [`ALGORITHMS.md`](../../ALGORITHMS.md). For the session handoff state see [`CONTEXT.md`](../../CONTEXT.md). For how every artifact was computed and where it lives in Azure see [`docs/artifacts.md`](../artifacts.md).

---

## High-Level Architecture

```
┌─────────────────────┐       POST /api/reco        ┌────────────────────────────────┐
│  Streamlit Cloud UI │  ─────────────────────────►  │  Azure Functions               │
│  deployment/        │                              │  ocp9funcapp-recsys            │
│  streamlit/app.py   │  ◄─────────────────────────  │  (Python 3.10, Consumption)    │
└─────────────────────┘      JSON response           └──────────────┬─────────────────┘
                                                                     │ memory-mapped at cold start
                                                                     ▼
                                                      ┌─────────────────────────────┐
                                                      │  Artifacts (433 MB bundle)  │
                                                      │  .npy arrays + .pkl + .txt  │
                                                      │  + .parquet                 │
                                                      └─────────────────────────────┘
```

---

## Azure Resources (verified 2026-03-13)

| Resource | Name | Detail |
|---|---|---|
| Resource group | `ocp9` | Central US |
| Function App | `ocp9funcapp-recsys` | **Running** · Python 3.10 · Consumption plan |
| Endpoint | `https://ocp9funcapp-recsys.azurewebsites.net/api/reco` | Anonymous auth, single POST route |
| Storage account | `ocp95449056669` | Standard LRS · StorageV2 |
| Last deploy zip | `scm-latest-ocp9funcapp-recsys.zip` | 433 MB · deployed 2025-08-22 |
| AzureML workspace | `ocp9` | Used for training only; not involved in serving |

---

## Deployed Artifact Manifest

All files are bundled inside the deploy zip and memory-mapped at Function App cold start.

| File | Shape / Type | What it encodes |
|---|---|---|
| `last_click.npy` | (65 536,) int32 | Last clicked article per user; **−1 = cold user** |
| `cf_i2i_top300.npy` | (65 536, 300) int32 | Per article: 300 most similar articles (I2I CF) |
| `als_top100.npy` | (65 536, 100) int32 | Per user: ALS top-100 personalized candidates |
| `tt_top200.npy` | (65 536, 200) int32 | Per user: Two-Tower cosine-similarity top-200 candidates |
| `pop_list.npy` | (65 536,) int32 | Articles ranked by global click frequency |
| `final_twotower_user_vec.npy` | (65 536, 250) float32 | Two-Tower user embedding vectors |
| `final_twotower_item_vec.npy` | (65 536, 250) float32 | Two-Tower item embedding vectors |
| `reranker.txt` | LightGBM Booster | 6-feature gradient-boosted ranker |
| `top_lists.pkl` | dict · 5 keys | Precomputed contextual popularity tables |
| `valid_clicks.parquet` | DataFrame | Ground-truth next click + stored user profiles |

### top_lists.pkl structure

```python
{
  "global_top":  ndarray(65536,),             # all articles, global rank
  "by_os":       {os_id: ndarray},            # 6 OS groups
  "by_dev":      {dev_id: ndarray},           # 3 device groups
  "by_os_reg":   {(os_id, country): ndarray}, # 8 (OS, country) combos
  "by_dev_reg":  {(dev_id, country): ndarray} # 6 (dev, country) combos
}
```

---

## Algorithm Call Sequences

> Full rationale and metrics for each algorithm: see [`ALGORITHMS.md`](../../ALGORITHMS.md#production-call-sequence).

### Cold users — no inference, pure table lookup

```
_cold_reco(env, k=10)
  1. TOP["by_os"][os_id]                → up to 2 items  [LOOKUP]
  2. TOP["by_dev"][device_id]           → up to 2 items  [LOOKUP]
  3. TOP["by_os_reg"][(os_id, country)] → up to 3 items  [LOOKUP]
  4. TOP["by_dev_reg"][(dev, country)]  → up to 3 items  [LOOKUP]
  5. TOP["global_top"]  (fallback)      → fill to k      [LOOKUP]

  ✅ Zero model inference. Every step is a precomputed table lookup.
```

Algorithms **excluded** from the cold path:

| Algorithm | Reason |
|---|---|
| U2U CF | Needs user interaction history — unavailable for cold users |
| I2I CF | Needs `last_click[user_id]` — undefined for cold users |
| ALS | Needs latent user factors from interaction history |
| Two-Tower retrieval | Needs trained user embedding; zero-history users have meaningless vectors |
| LightGBM | Needs a candidate pool from the above — not applicable |

---

### Warm users — 4-source candidate assembly → LightGBM rerank

```
Step 1 — get_candidates(user_id)   [pool built in order, deduplicated]
  1a. I2I CF     cf_i2i_top300[ last_click[u] ]   → up to 300 items  (pool → 300)
  1b. ALS        als_top100[ u ]                  → up to 100 items  (pool → 400)
  1c. Popularity pop_list (global rank)            → fill to 600      (pool → 600)
  1d. Two-Tower  tt_top200[ u ]                   → up to 200 items  (pool → 800)
  1e. Popularity pop_list (second pass)            → fill to 1 000    (pool → 1000)

Step 2 — build_features(user_id, candidates)   [(1000 × 6) matrix]
  f0 = CF rank         : r       if r ≤ 300        else 1001
  f1 = ALS rank        : r-300   if 300 < r ≤ 400  else 1001
  f2 = Pop rank        : r-400   if 400 < r ≤ 600  else 1001
  f3 = Two-Tower rank  : r-600   if 600 < r ≤ 800  else 1001
  f4 = Global rank     : r  (always set)
  f5 = Cosine sim      : dot(user_vec[u], item_vec[i]) / (‖u‖·‖i‖ + 1e-9)

Step 3 — model.predict(X)       LightGBM Booster scores all 1 000 candidates

Step 4 — argsort(-scores)[:k]   Return top-k article IDs
```

Algorithms **excluded** from the warm path:

| Algorithm | Reason |
|---|---|
| U2U CF | recall@10 = 0.59%, mean rank 22 985 — worst retriever; too noisy with sparse data. Never used in production. |
| Two-Tower as ranker | recall@100 = 3.13% standalone — too weak. Used only as candidate generator (step 1d) and cosine-similarity feature (f5). |
| Contextual popularity blend | The `by_os` / `by_dev` / `by_os_reg` / `by_dev_reg` tables are for cold users only. Warm users get raw `pop_list` as a filler (steps 1c, 1e), not the contextual blend. |

---

## Request Routing

Every request to `POST /api/reco` is routed to one of two fully separate paths.

```
POST /api/reco  { user_id, k, env }
      │
      ├─ Parse JSON  +  validate user_id ∈ [0, 65535]
      ├─ Load stored profile: valid_clicks.parquet → user_profiles[user_id]
      ├─ Apply env overrides (device / os / country) if present in request body
      └─ Route: last_click[user_id] == -1 ?
                    │ Yes                     │ No
                    ▼                         ▼
              COLD PATH                  WARM PATH
        (contextual popularity)    (ensemble + LightGBM)
```

---

## Cold Path — Contextual Popularity Blend

No interaction history → context (device, OS, country) is the only signal. Pure precomputed table lookup; no model inference.

```
Allocation for k = 10:
  by_os[os]               → 2 items   (⌊k × 2/10⌋)
  by_dev[device]          → 2 items   (⌊k × 2/10⌋)
  by_os_reg[(os,country)] → 3 items   (⌊k × 3/10⌋)
  by_dev_reg[(dev,ctry)]  → 3 items   (remainder)
  global_top              → fill to k (safety net if any bucket is short/missing)

All candidates deduplicated with a seen-set.
```

**Performance:** recall@10 = 17.21% (contextual) / 12.11% (global fallback)

---

## Warm Path — Candidate Assembly + LightGBM

### Step 1 — Candidate pool (up to 1 000 items, deduplicated)

```
last_click[user_id] = article i                                  [LOOKUP]
  ├─ cf_i2i_top300[i]   → up to 300 candidates                   [LOOKUP — precomputed array]
  ├─ als_top100[user]   → +100 candidates                        [LOOKUP — precomputed array]
  ├─ pop_list           → fill to 600                            [LOOKUP — precomputed sorted list]
  ├─ tt_top200[user]    → +200 candidates                        [LOOKUP — precomputed array]
  └─ pop_list (cont.)   → fill to 1 000                          [LOOKUP — precomputed sorted list]
```

Cumulative caps: CF@300 → ALS@400 → Pop@600 → TT@800 → Pop@1000.
✅ All lookups. No algorithm runs. Every array was computed offline and bundled in the deploy zip.

### Step 2 — 6-feature matrix (1 000 × 6)

| # | Feature | How produced at request time | Default (item not from that source) |
|---|---|---|---|
| 0 | CF rank | Arithmetic from pool position (r if r≤300) | 1001 |
| 1 | ALS rank | Arithmetic from pool position (r-300 if 300<r≤400) | 1001 |
| 2 | Popularity rank | Arithmetic from pool position (r-400 if 400<r≤600) | 1001 |
| 3 | Two-Tower rank | Arithmetic from pool position (r-600 if 600<r≤800) | 1001 |
| 4 | Global rank | Pool position r — always set | — |
| 5 | Cosine similarity | **COMPUTED LIVE:** `dot(user_vec[u], item_vec[i]) / (‖u‖·‖i‖ + ε)` | — |

Features f0–f4 require no data read — they are derived from the candidate's position in the pool.
Feature f5 is a real NumPy computation on the preloaded embedding arrays, run for every candidate.

### Step 3 — LightGBM rerank

```python
scores   = model.predict(X_1000x6)    # LIVE MODEL INFERENCE — only real ML prediction in the system
topk_ids = [cand[i] for i in argsort(-scores)[:k]]
```

`reranker.txt` is the **only artifact that runs ML inference at request time**. All other artifacts are precomputed lookup tables or embedding arrays.

➜ For how every artifact was trained and where it is stored: see [`docs/artifacts.md`](../artifacts.md).

**Performance:** hit_rate@10 = 18.58% (warm users); recall@10 ensemble = 22.99% (warm users)

---

## Response Format

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

- `recommendations`: list of article IDs (length = k)
- `ground_truth`: held-out next click from validation set (null if user not in ground truth)
- `user_profile.stored`: profile loaded from `valid_clicks.parquet`
- `user_profile.used`: effective context after env overrides
- `user_profile.overrides_applied`: true if caller sent non-empty `env`

---

## Live Test Results (2026-03-13)

```bash
# Warm user
curl -X POST https://ocp9funcapp-recsys.azurewebsites.net/api/reco \
  -H "Content-Type: application/json" -d '{"user_id":1,"k":5}'
# → {"recommendations":[30077,30650,26551,31411,30545],"ground_truth":36162,...}

# Near-cold user (global pop articles visible: #29902, #9999)
curl -X POST https://ocp9funcapp-recsys.azurewebsites.net/api/reco \
  -H "Content-Type: application/json" -d '{"user_id":0,"k":5}'
# → {"recommendations":[5747,3436,29902,9999,8574],"ground_truth":26859,...}

# Env override — overrides_applied: true, different recommendations returned
curl -X POST https://ocp9funcapp-recsys.azurewebsites.net/api/reco \
  -H "Content-Type: application/json" \
  -d '{"user_id":5,"k":5,"env":{"os":0,"device":0,"country":"US"}}'
# → {"recommendations":[3160,27647,27947,11385,30119],...,"overrides_applied":true}
```

---

## Known Issues

### 1. Country stored as numeric code, not ISO string (Medium)

`valid_clicks.parquet` stores country as a numeric code (e.g. `"1"`) rather than an ISO-3166 string (`"US"`, `"FR"`). This causes `by_os_reg` and `by_dev_reg` lookups in `top_lists.pkl` to miss (keys are `(os_id, 'US')` etc.), silently falling back to `global_top` for virtually all cold users. Cold-start contextual quality is therefore degraded.

**Fix needed in:** the data preprocessing step that builds `valid_clicks.parquet`, or a lookup table in `__init__.py` that maps numeric country codes → ISO strings.

### 2. `src/models/reranking.py::_build_features` diverged from production (Medium)

The clean OOP reranker always sets algorithm ranks 0–3 to 1001 (the sentinel). The deployed function (`HttpReco/__init__.py::build_features`) correctly infers ranks from candidate pool position ranges. The `src/` version needs to be brought into sync, or explicitly documented as a simplified version.

### 3. No health endpoint (Low)

No `GET /health` or `GET /status` route. Cold-start monitoring requires a real `POST /api/reco` call.

---

## Algorithm Summary

| Algorithm | recall@10 | Role |
|---|---|---|
| U2U CF | 0.59% | Baseline only — not deployed |
| **I2I CF** | 1.55% | 300 candidates · highest priority |
| **ALS** | 1.98% | 100 candidates · diversity |
| Two-Tower | — | 200 candidates + cosine similarity feature |
| Popularity (global) | 12.11% | Cold start backbone + pool filler |
| Popularity (contextual) | 17.21% | Cold start with context |
| LightGBM reranker | 18.58%* | Final warm-user ranker |
| **Hybrid ensemble** | **22.99%**† | **Production** |

Full algorithm details, hyperparameter search results, and design rationale: see [`ALGORITHMS.md`](../../ALGORITHMS.md).

---

## Code Locations

| Concern | Production path | Clean OOP path |
|---|---|---|
| Artifact loading | `deployment/azure_functions/HttpReco/__init__.py` lines 23–77 | `src/service.py::_load_auxiliary_data` |
| Cold routing | `__init__.py::http_reco` | `src/service.py::_is_cold_user` |
| Cold-start logic | `__init__.py::_cold_reco` | `src/models/popularity.py::ContextualPopularity` |
| Candidate assembly | `__init__.py::get_candidates` | `src/service.py::_generate_candidate_pool` |
| Feature engineering | `__init__.py::build_features` | `src/models/reranking.py::_build_features` ⚠️ (diverged) |
| LightGBM inference | `__init__.py::http_reco` warm branch | `src/models/reranking.py::rerank` |

---

## Technology Stack

| Layer | Technology |
|---|---|
| API | Azure Functions v2 · Python decorator model · anonymous auth |
| ML inference | NumPy · LightGBM · (all artifacts precomputed offline) |
| Data loading | pandas · pyarrow (parquet) |
| Frontend | Streamlit (Streamlit Cloud) |
| Testing | pytest · unittest.mock |
| Local dev | Azure Functions Core Tools |
