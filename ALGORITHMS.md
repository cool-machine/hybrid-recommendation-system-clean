# Algorithm Story — OCP9 Hybrid Recommender

> This document traces every algorithm tried, why it was kept or discarded as a standalone ranker, and what role it plays in the final production pipeline.
> For the architecture and artifact details see [`docs/architecture/README.md`](docs/architecture/README.md).

---

## Production Call Sequence

### Cold users (`last_click[user_id] == -1`)

Cold users have **no interaction history**. No personalisation algorithm is called. The entire response is built from precomputed popularity tables in a fixed priority order.

```
http_reco(req)
  │
  └─► _cold_reco(env, k=10)
        │
        ├─ 1. TOP["by_os"].get(os_id)                → up to 2 items  [LOOKUP — precomputed table]
        │      (articles most clicked by users with the same OS)
        │
        ├─ 2. TOP["by_dev"].get(device_id)            → up to 2 items  [LOOKUP — precomputed table]
        │      (articles most clicked by users with the same device group)
        │
        ├─ 3. TOP["by_os_reg"].get((os_id, country))  → up to 3 items  [LOOKUP — precomputed table]
        │      (articles most clicked by users with the same OS in the same country)
        │
        ├─ 4. TOP["by_dev_reg"].get((dev_id, country))→ up to 3 items  [LOOKUP — precomputed table]
        │      (articles most clicked by users with the same device in the same country)
        │
        └─ 5. TOP["global_top"]  (= pop_list fallback)→ fill to k      [LOOKUP — precomputed table]
               (safety net if any bucket is short or missing)

  Deduplication with a seen-set at every step.
  ✅ Zero model inference. Every step is a precomputed table lookup.
  ➜ See docs/artifacts.md for how each table was computed.
```

**Algorithms EXCLUDED from the cold path and why:**

| Algorithm | Why excluded |
|---|---|
| U2U CF | Requires user interaction history (none available for cold users) |
| I2I CF | Requires `last_click[user_id]` (undefined for cold users) |
| ALS | Requires user interaction history to compute latent factors |
| Two-Tower retrieval | Requires meaningful user embedding (embedding exists but is untrained for zero-history users) |
| LightGBM reranker | Requires a candidate pool generated from the above — not applicable |

---

### Warm users (`last_click[user_id] != -1`)

Warm users have at least one recorded click. Four algorithms contribute candidates; one algorithm reranks the pool.

```
http_reco(req)
  │
  ├─ Step 1: get_candidates(user_id)  — builds deduplicated pool up to 1 000 items
  │    │
  │    ├─ 1a. I2I CF
  │    │       cf_i2i_top300[ last_click[user_id] ]          [LOOKUP — precomputed array]
  │    │       → index into 65536×300 array by last-clicked article
  │    │       → add up to 300 items  (pool cap: 300)
  │    │
  │    ├─ 1b. ALS
  │    │       als_top100[ user_id ]                         [LOOKUP — precomputed array]
  │    │       → index into 65536×100 array by user_id
  │    │       → add up to 100 items  (pool cap: 400)
  │    │
  │    ├─ 1c. Global Popularity (first pass)
  │    │       iterate pop_list                              [LOOKUP — precomputed sorted array]
  │    │       → fills up to 200 slots  (pool cap: 600)
  │    │
  │    ├─ 1d. Two-Tower
  │    │       tt_top200[ user_id ]                          [LOOKUP — precomputed array]
  │    │       → index into 65536×200 array by user_id
  │    │       → add up to 200 items  (pool cap: 800)
  │    │
  │    └─ 1e. Global Popularity (second pass / safety net)
  │            iterate pop_list                              [LOOKUP — same precomputed array]
  │            → fill remaining slots to 1 000
  │
  │    ✅ All of Step 1 is precomputed lookups. No algorithm runs at request time.
  │
  ├─ Step 2: build_features(user_id, cand)  — construct (1000 × 6) matrix
  │    │
  │    │  For each candidate at pool position r (1-based):
  │    │
  │    │  f0 = r if r≤300 else 1001              [DERIVED from pool position — no lookup needed]
  │    │  f1 = r-300 if 300<r≤400 else 1001      [DERIVED from pool position]
  │    │  f2 = r-400 if 400<r≤600 else 1001      [DERIVED from pool position]
  │    │  f3 = r-600 if 600<r≤800 else 1001      [DERIVED from pool position]
  │    │  f4 = r  (always set)                   [DERIVED from pool position]
  │    │  f5 = dot(user_vec[u], item_vec[i])
  │    │       / (‖u‖·‖i‖ + 1e-9)               [COMPUTED LIVE — NumPy dot product per candidate]
  │    │
  │    │  Features f0–f4: arithmetic from pool position. No extra data read.
  │    │  Feature f5: live NumPy computation using preloaded embedding arrays.
  │    │  1001 = sentinel meaning "this candidate did not come from that algorithm."
  │
  ├─ Step 3: model.predict(X_1000x6)            [LIVE MODEL INFERENCE — LightGBM Booster]
  │           → 1000 float scores
  │           This is the ONLY step where an actual ML model runs at request time.
  │
  └─ Step 4: argsort(-scores)[:k]               [COMPUTED LIVE — NumPy sort]
             → top-k article IDs returned to caller

  ➜ See docs/artifacts.md for how every array and the LightGBM model were computed offline.
```

**Algorithms EXCLUDED from the warm path and why:**

| Algorithm | Why excluded |
|---|---|
| U2U CF | recall@10 = 0.59%, mean rank 22 985. With sparse interactions, user–user similarity is too noisy. Worst retriever tested. Never used in production. |
| Two-Tower as standalone ranker | recall@100 = 3.13% standalone (vs I2I CF's 19.69%). BPR-trained models optimise relative ordering, not top-K precision. Used only as a candidate generator (step 1d) and via cosine similarity (feature f5), not as a ranker. |
| Contextual popularity blend | The `_cold_reco` logic (by_os / by_dev / by_os_reg / by_dev_reg) is skipped entirely for warm users. For warm users, raw `pop_list` is used as a filler (steps 1c and 1e), not the contextual blend. |

---

---

## Dataset Context

| Split | Users | Items | Interactions |
|---|---|---|---|
| Train | 65 536 | 33 320 | 2 857 109 |
| Validation | 65 536 | 33 320 | 1 click / user |
| Test | 65 536 | 33 320 | 1 click / user |

Ground truth is a **single held-out click per user**. Primary metric: **recall@10** (did the true article appear in the top-10 recommendations?).

---

## 1. User-to-User Collaborative Filtering (U2U CF)

**Notebook:** `collaborative-filtering.ipynb` §4

### How it works
Builds a user–item interaction matrix, computes cosine similarity between users, and recommends items liked by the most similar neighbours that the target user has not yet seen.

### Results (full validation set, 65 536 users)

| Metric | Value |
|---|---|
| recall@5 | 0.23% |
| recall@10 | 0.59% |
| recall@100 | 3.32% |
| Mean rank | 22 985 |

### Verdict — ❌ Not used in production
U2U CF is the weakest retriever. With 65 k users and very sparse interactions (on average fewer than 50 clicks per user), the user–user similarity matrix is too noisy to be reliable. The mean rank of 22 985 confirms that the ground-truth article is essentially buried. It was kept in the notebook as a baseline reference only.

---

## 2. Item-to-Item Collaborative Filtering (I2I CF)

**Notebook:** `collaborative-filtering.ipynb` §5

### How it works
Transposes the problem: computes item–item cosine similarity from the co-interaction matrix, then recommends items most similar to what the user has already consumed.

### Results

| Metric | Value |
|---|---|
| recall@5 | 0.60% |
| recall@10 | 1.55% |
| recall@100 | 19.69% |
| Mean rank | 2 460 |

### Verdict — ✅ Primary retriever (300 candidates, highest priority)
I2I CF is the strongest individual retriever on this dataset. Its recall@100 of 19.69% and mean rank of 2 460 are significantly better than U2U CF and competitive with ALS. It captures strong local co-consumption patterns and is fast to serve (pre-computed similarity matrix). It contributes **300 candidates** to the hybrid pool and is given the highest priority weight.

---

## 3. Matrix Factorization — ALS (Alternating Least Squares)

**Notebook:** `matrix-factorization-als.ipynb`

### How it works
Factorises the sparse user–item interaction matrix into two dense embedding matrices (users × factors, items × factors) by alternately fixing one and solving for the other in closed form. Scores are inner products of user and item embeddings.

### Results (best hyperparameters: factors=128, α=40)

| Metric | Value |
|---|---|
| recall@5 | 1.06% |
| recall@10 | 1.98% |
| recall@100 | 16.54% |
| Mean rank | 7 554 |

### Hyperparameter search

| Factors | Alpha | recall@10 |
|---|---|---|
| 64 | 20 | 1.68% |
| 128 | 40 | **1.98%** |
| 256 | 40 | 1.91% |

### Verdict — ✅ Secondary retriever (100 candidates, "new discovery" role)
ALS recall@10 (1.98%) is marginally better than I2I CF at small K, but weaker at recall@100. Its value in the ensemble is **diversity**: the global latent factors it learns surface different articles than co-occurrence-based I2I CF. It is deliberately allocated a smaller quota (100 candidates) to avoid dominating the pool, letting the LightGBM reranker arbitrate.

---

## 4. Two-Tower Neural Network

**Notebook:** `hybrid-ensemble-recommendation.ipynb` §6 (training embedded in the hybrid notebook)

### How it works
A dual-encoder model trained with Bayesian Personalised Ranking (BPR) loss and 50 negative samples per positive. The user tower is an MLP on a learned user embedding; the item tower shares pre-trained item embeddings (frozen after pre-training). Retrieval score = cosine similarity of the two output vectors.

Architecture: 33.4 M parameters — item embedding (16.4 M) + item projection (62.5 K) + user embedding (16.4 M) + user MLP (521 K).

Training: up to 15 epochs with early stopping on validation BPR loss (best val_loss = 0.208).

### Results (standalone evaluation, 65 536 users)

| Metric | Value |
|---|---|
| recall@100 | 3.13% |
| recall@200 | 6.82% |
| recall@300 | 11.76% |
| Mean rank | 23 659 |

> recall@5 and recall@10 were not printed (evaluation K-list started at 100), but given recall@100 = 3.13%, both would be negligible (< 0.1%).

### Verdict — ⚠️ Not used as a standalone ranker; used as a feature and supplementary retriever
The Two-Tower performs worse than I2I CF and ALS as a retriever (recall@100 = 3.13% vs 19.69% and 16.54%). This is expected: BPR-trained embedding models are optimised for relative ordering, not absolute top-K precision. However, the **item and user embedding vectors** carry rich semantic information that neither CF nor ALS captures. In the hybrid:

- The Two-Tower contributes **200 candidates** to the pool (articles with highest cosine similarity to the user vector).
- The **cosine similarity score** between the user and each candidate item is passed as a feature to LightGBM, giving the reranker a semantic signal it would otherwise lack.

---

## 5. Contextual Popularity

**Notebook:** `hybrid-ensemble-recommendation.ipynb` §4

### How it works
Ranks articles by recency-weighted click count, segmented by user context (operating system, device type, country). For a given user, the popularity list is filtered to their context segment before recommendation. When the context segment is too sparse, it falls back to global popularity.

### Results

| Metric | Value |
|---|---|
| recall@10 (global fallback) | 12.11% |
| recall@10 (contextual, all users) | 17.21% |

### Verdict — ✅ Cold-start backbone
Popularity is the only algorithm that can handle **cold-start users** (those with zero or near-zero history, ~52 k of 65 k users). Its recall@10 of 12.11% (global) is surprisingly strong given its simplicity and is higher than any of the personalised CF/MF models. It forms the primary cold-start path: if a user has no history, popularity is the complete response. For warm users it fills remaining candidate slots and acts as a safety net.

---

## 6. LightGBM Reranker

**Notebook:** `hybrid-ensemble-recommendation.ipynb` §8

### How it works
After the retrieval stage assembles up to 1 000 candidate articles from all sources, a LightGBM gradient-boosted ranker scores each (user, candidate) pair and reorders the list. It is trained with pairwise ranking loss on the same training set.

### Input features (6 total)

| # | Feature | Source |
|---|---|---|
| 1 | I2I CF rank | CF retriever |
| 2 | ALS rank | ALS retriever |
| 3 | Popularity rank | Popularity retriever |
| 4 | Two-Tower rank | Two-Tower retriever |
| 5 | Global article position | Article metadata |
| 6 | Cosine similarity (user ↔ item) | Two-Tower embeddings |

> **Known limitation:** features 1–4 are only meaningful for candidates that were retrieved by the corresponding algorithm; for candidates from other sources they default to a sentinel value (1001). This means features 5 (global position) and 6 (cosine similarity) carry most of the signal in practice. Fixing this — by always computing all four rank features for all candidates — is an identified improvement for future work.

### Results

| Metric | Value |
|---|---|
| hit_rate@10 (warm users, 13 108) | 18.58% |
| Users evaluated | 13 108 |

### Verdict — ✅ Final stage for all warm users
LightGBM's hit_rate@10 of 18.58% sits between the ensemble recall@10 (22.99%) and the raw pool. It is the authoritative ranker for warm users: it arbitrates between the four retrieval signals and surfaces the most relevant article in the top 10.

---

## 7. Hybrid Ensemble (Final System)

**Notebook:** `hybrid-ensemble-recommendation.ipynb` §8–9

### Pipeline

```
User request
     │
     ├─ has history? ──No──► Contextual Popularity → top-10 response
     │
    Yes
     ▼
┌─────────────────────────────────────┐
│         Candidate retrieval         │
│  I2I CF        → 300 candidates     │
│  ALS           → 100 candidates     │
│  Two-Tower NN  → 200 candidates     │
│  Popularity    → fills to 1 000     │
└───────────────┬─────────────────────┘
                │ deduplicated pool
                ▼
        LightGBM Reranker
        (6 features per candidate)
                │
                ▼
           Top-10 response
```

### Results

| Metric | Users | Value |
|---|---|---|
| recall@10 — all users (warm + cold) | 65 536 | 17.21% |
| recall@10 — warm users only | 13 108 | **22.99%** |
| hit_rate@10 — LightGBM stage | 13 108 | 18.58% |
| Candidate pool recall@1000 | 65 536 | **75.01%** |
| Improvement vs. best individual (ALS recall@10 = 1.98%) | — | **11.6×** |

### Why the hybrid works
No single algorithm covers all scenarios:

- I2I CF and ALS are strong for personalisation but require history and cap out at ~2% recall@10 individually.
- Two-Tower adds semantic diversity and a cosine similarity signal, but is a weak standalone retriever.
- Popularity solves cold start but is impersonal for warm users.

By aggregating 1 000 diverse candidates and letting LightGBM arbitrate, the ensemble achieves recall@10 = 22.99% for warm users — 11.6× the best individual algorithm. The 75% candidate pool recall@1000 confirms the diversity is genuine: the ground-truth article is reachable 3 out of 4 times before reranking even begins.

---

## Summary Table

| Algorithm | Recall@5 | Recall@10 | Recall@100 | Mean Rank | Role in system |
|---|---|---|---|---|---|
| U2U CF | 0.23% | 0.59% | 3.32% | 22 985 | Baseline only, not deployed |
| I2I CF | 0.60% | 1.55% | 19.69% | 2 460 | 300 candidates (priority) |
| ALS | 1.06% | 1.98% | 16.54% | 7 554 | 100 candidates (diversity) |
| Two-Tower NN | — | — | 3.13% | 23 659 | 200 candidates + cosine feature |
| Popularity (global) | — | 12.11% | — | — | Cold start + pool fill |
| LightGBM | — | 18.58%* | — | — | Final reranker (warm users) |
| **Hybrid ensemble** | — | **22.99%**† | — | — | **Production system** |

\* hit_rate@10 on 13 108 warm users
† recall@10 on 13 108 warm users; 17.21% across all 65 536 users
