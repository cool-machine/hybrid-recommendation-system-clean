# Artifact Reference

> Every file deployed to Azure Functions — what type it is, how it was computed, where it lives in Azure, and exactly what role it plays during a live request.

---

## Artifact types — three categories

Understanding the difference between these types answers the core question: **is a model running at inference time, or are we just doing a table lookup?**

| Type | Description | Examples |
|---|---|---|
| **Pre-computed lookup table** | Pure array indexing at request time. No algorithm runs. The "computation" happened entirely offline. | `last_click.npy`, `cf_i2i_top300.npy`, `als_top100.npy`, `tt_top200.npy`, `pop_list.npy`, `top_lists.pkl` |
| **Pre-computed embedding vectors** | Arrays loaded at cold start; used as inputs to an **on-the-fly cosine similarity** computation during each request | `final_twotower_user_vec.npy`, `final_twotower_item_vec.npy` |
| **Live ML model** | A trained model that **receives input features and outputs predictions at request time**. This is the only artifact that runs real inference during a request. | `reranker.txt` (LightGBM Booster) |
| **Raw data / ground truth** | Not a model. Loaded at cold start to populate user profiles and display ground-truth clicks in the demo UI. | `valid_clicks.parquet` |

---

## Azure storage location

All artifacts are bundled together inside a single deploy zip. There is no separate blob storage lookup at inference time — everything is loaded from the local file system of the running Azure Functions instance.

| Resource | Value |
|---|---|
| Storage account | `ocp95449056669` (Standard LRS, StorageV2) |
| Container | `scm-releases` |
| Blob name | `scm-latest-ocp9funcapp-recsys.zip` |
| Zip size | 433 MB |
| Deployed | 2025-08-22 |
| Path inside zip | `external_runtime_assets/azure/artifacts/` |
| Local mirror (dev) | `secondary_assets/external_runtime_assets/azure/artifacts/` |

When the Azure Functions runtime starts (cold start), it extracts the zip and the function code finds artifacts at:

```python
ROOT / "external_runtime_assets" / "azure" / "artifacts"
```

where `ROOT` is the grandparent of the function's `__init__.py`.

---

## Per-artifact reference

---

### `last_click.npy`

| Field | Value |
|---|---|
| **Type** | Pre-computed lookup table |
| **Shape** | (65 536,) int32 |
| **Meaning** | `last_click[user_id]` = article ID of the most recently clicked article for that user in the training set. Value `−1` means the user never clicked anything → **cold user**. |
| **Source data** | `train_clicks.parquet` |
| **How computed** | Group training interactions by `user_id`, take the row with the **maximum `click_timestamp`**, store its `click_article_id`. |
| **Key code** | `idx = train_df.groupby("user_id").click_timestamp.idxmax()` → `last_click[train_df.user_id[idx]] = train_df.click_article_id[idx]` |
| **Notebook** | `notebooks/hybrid-ensemble-recommendation.ipynb` · cell 56 |
| **Role at inference** | Looked up once to decide cold vs warm path, and to find the seed article for I2I CF candidates. No computation. |

---

### `cf_i2i_top300.npy`

| Field | Value |
|---|---|
| **Type** | Pre-computed lookup table |
| **Shape** | (65 536, 300) int32 |
| **Meaning** | `cf_i2i_top300[article_id]` = the 300 articles most co-clicked with that article, ranked by cosine similarity of their co-occurrence vectors. |
| **Source data** | `train_clicks.parquet` |
| **How computed** | 1. Build a **user × item incidence matrix** (CSR) from all training clicks. 2. L2-normalise each item's column vector (item = a column = "which users clicked it"). 3. Compute the full **item × item cosine similarity matrix** (`item_matrix @ item_matrix.T`). 4. For each of the 65 536 articles, keep the top-300 most similar neighbours, **excluding the article itself**. |
| **Key code** | `norm = ui.T.copy()` → L2-normalise → `sim = (norm @ norm.T)` → `top300 = argpartition(-sim, 301)[:, 1:301]` |
| **Notebook** | `notebooks/hybrid-ensemble-recommendation.ipynb` · cell 56 |
| **Role at inference** | For a warm user: `cf_i2i_top300[last_click[user_id]]` → direct array lookup → first 300 candidates. No algorithm runs. |

---

### `als_top100.npy`

| Field | Value |
|---|---|
| **Type** | Pre-computed lookup table |
| **Shape** | (65 536, 100) int32 |
| **Meaning** | `als_top100[user_id]` = the 100 articles ranked highest by the ALS model's inner-product score for that user. |
| **Source data** | `train_clicks.parquet` |
| **How computed** | 1. Build user × item CSR matrix. 2. Train **ALS** (`implicit` library) with confidence weighting `C = 1 + 40 × R` (alpha=40), `factors=64`, `iterations=20`, `regularization=1e-4`. 3. After training, compute the full **score matrix** = `user_factors @ item_factors.T` (65 536 × 65 536). 4. For each user, keep the **top-100 highest-scoring items** via `argpartition`. |
| **Key code** | `als.fit((40 * ui.T).tocsr())` → `als_scores = als.item_factors @ als.user_factors.T` → `als_top100 = argpartition(-als_scores, 100, axis=1)[:, :100]` |
| **Notebook** | `notebooks/hybrid-ensemble-recommendation.ipynb` · cell 56 |
| **Role at inference** | `als_top100[user_id]` → direct array lookup → next up to 100 candidates added to pool. No algorithm runs. |

---

### `tt_top200.npy`

| Field | Value |
|---|---|
| **Type** | Pre-computed lookup table |
| **Shape** | (65 536, 200) int32 |
| **Meaning** | `tt_top200[user_id]` = the 200 articles with highest cosine similarity to that user's Two-Tower embedding vector. |
| **Source data** | `train_clicks.parquet` + `articles_embeddings.pickle` (pre-trained article embeddings) |
| **How computed** | 1. Train the Two-Tower neural network (see `final_twotower_*_vec.npy` below). 2. Extract final user and item embedding vectors for all users and items. 3. Compute the full **score matrix** = `user_vec @ item_vec.T`. 4. For each user, keep the **top-200 highest-scoring items** via `argpartition`. |
| **Key code** | `tt_scores = tt_user_vec @ tt_item_vec.T` → `tt_top200 = argpartition(-tt_scores, 200, axis=1)[:, :200]` |
| **Notebook** | `notebooks/hybrid-ensemble-recommendation.ipynb` · cell 56 |
| **Role at inference** | `tt_top200[user_id]` → direct array lookup → next up to 200 candidates. No algorithm runs. |

---

### `pop_list.npy`

| Field | Value |
|---|---|
| **Type** | Pre-computed lookup table |
| **Shape** | (65 536,) int32 |
| **Meaning** | All article IDs sorted by **descending total click count** in the training set. `pop_list[0]` is the most-clicked article (#29902). |
| **Source data** | `train_clicks.parquet` |
| **How computed** | `np.argsort(np.bincount(train_df.click_article_id, minlength=n_items))[::-1]` — count clicks per article, sort descending. |
| **Notebook** | `notebooks/hybrid-ensemble-recommendation.ipynb` · cell 56 |
| **Role at inference** | Iterated in rank order to fill candidate pool slots (positions 401–600 and 801–1000). Also the fallback for `global_top` in cold-path if `top_lists.pkl` fails to load. Pure iteration, no computation. |

---

### `top_lists.pkl`

| Field | Value |
|---|---|
| **Type** | Pre-computed lookup table |
| **Shape** | Python dict · 5 keys |
| **Meaning** | Contextual popularity lists: for each combination of OS group, device group, and country, a ranked array of article IDs most clicked by users in that segment. |
| **Source data** | `train_clicks.parquet` (columns: `click_article_id`, `click_os`, `click_deviceGroup`, `click_country`) |
| **How computed** | For each context segment, filter training clicks to that segment, count click frequency per article, sort descending. Stored as a dict: |

```python
{
  "global_top":  ndarray(65536,),              # all articles, global rank order
  "by_os":       {os_id (int): ndarray},        # 6 OS groups
  "by_dev":      {dev_id (int): ndarray},       # 3 device groups
  "by_os_reg":   {(os_id, country_str): ndarray},  # 8 (OS, country) combos
  "by_dev_reg":  {(dev_id, country_str): ndarray}  # 6 (dev, country) combos
}
```

> ⚠️ **Known issue:** `click_country` was stored as a `uint8` numeric code (0–255) in `data-processing.ipynb`. The keys in `by_os_reg` and `by_dev_reg` expect ISO country strings (`'US'`, `'FR'`). Stored user profiles carry the numeric code (e.g. `"1"`), causing contextual lookups to **miss silently** and fall back to `global_top`. Fix: add a numeric→ISO mapping when building user profiles.

| **Notebook** | `notebooks/hybrid-ensemble-recommendation.ipynb` (contextual popularity segment) — exact cell not in downloaded v2 notebooks; likely built in the popularity notebook series or a standalone script before deployment. |
| **Role at inference** | Cold path only. `TOP["by_os"][os_id]` etc. → direct dict lookup → returns pre-ranked article array. No computation. |

---

### `final_twotower_user_vec.npy`

| Field | Value |
|---|---|
| **Type** | Pre-computed embedding vectors (used in live cosine computation) |
| **Shape** | (65 536, 250) float32 |
| **Meaning** | L2-normalised 250-dimensional embedding vector for every user, output of the trained Two-Tower user tower. |
| **Source data** | `train_clicks.parquet` |
| **How computed** | See Two-Tower training below. After training: `user_vec = model.user_vec(torch.arange(n_users)).detach().cpu().numpy()` → `np.save("final_twotower_user_vec.npy", user_vec)` |
| **Notebook** | `notebooks/hybrid-ensemble-recommendation.ipynb` · cell 54 |
| **Role at inference** | **Used in a live computation** at every warm-user request: `dot(user_vec[u], item_vec[i]) / (‖u‖ · ‖i‖ + ε)` is computed for all ~1000 candidates to produce feature f5 for LightGBM. This is a real NumPy matrix operation happening per-request. |

---

### `final_twotower_item_vec.npy`

| Field | Value |
|---|---|
| **Type** | Pre-computed embedding vectors (used in live cosine computation) |
| **Shape** | (65 536, 250) float32 |
| **Meaning** | L2-normalised 250-dimensional embedding vector for every article, output of the trained Two-Tower item tower. |
| **Source data** | `articles_embeddings.pickle` (pre-trained article content embeddings from the dataset) |
| **How computed** | See Two-Tower training below. After training: `item_vec = model.item_vec(torch.arange(n_items)).detach().cpu().numpy()` → `np.save("final_twotower_item_vec.npy", item_vec)` |
| **Notebook** | `notebooks/hybrid-ensemble-recommendation.ipynb` · cell 54 |
| **Role at inference** | Same as `user_vec` above — used per-request in the cosine similarity computation for LightGBM feature f5. |

#### Two-Tower training (how both embedding files were produced)

The Two-Tower is a **dual-encoder neural network** trained with **Bayesian Personalised Ranking (BPR) loss**:

- **User tower:** learnable user embedding (65 536 × 250) → 2-layer MLP → L2-normalise output
- **Item tower:** linear projection of pre-trained `articles_embeddings.pickle` vectors → L2-normalise output (item base embeddings are **frozen** after pre-training)
- **Loss:** BPR with **50 random negative samples** per positive click
- **Training:** up to 15 epochs, `EarlyStopping` on validation BPR loss (best `val_loss ≈ 0.208`), `ReduceLROnPlateau` scheduler
- **Framework:** PyTorch + PyTorch Lightning, `pl.seed_everything(42)`
- **Output:** 250-dim L2-normalised vectors for all 65 536 users and all 65 536 articles
- **Saved to:** `cached_artifacts/final_twotower_user_vec.npy` and `final_twotower_item_vec.npy`
- **Notebook:** `notebooks/hybrid-ensemble-recommendation.ipynb` · cell 54

---

### `reranker.txt` — THE ONLY LIVE ML MODEL

| Field | Value |
|---|---|
| **Type** | **Live ML model — runs inference at every warm-user request** |
| **Format** | LightGBM Booster (text format, loadable with `lgb.Booster(model_file=...)`) |
| **Meaning** | A gradient-boosted ranking model that scores each of the ~1000 candidates and reorders them. This is the **only artifact where a model is actually predicting at request time**. |
| **Source data** | All other lookup tables + `valid_clicks.parquet` (as labels) |
| **How computed** | 1. For every warm user (those with `last_click != -1`), build the same 1000-candidate pool that inference will use. 2. Construct the 6-feature matrix (same as inference). 3. Label each (user, candidate) pair: `label = 1` if candidate == ground-truth next click, else `0`. 4. Train LightGBM with `lambdarank` objective (pairwise ranking loss), optimising `ndcg@[10, 100]`. 5. 80/20 user split for train/validation; `early_stopping_round=50`. |
| **Hyperparameters** | `objective="lambdarank"`, `metric="ndcg"`, `ndcg_eval_at=[10,100]`, `learning_rate=0.05`, `num_leaves=255`, `min_data_in_leaf=20`, `feature_fraction=0.8`, `early_stopping_round=50` |
| **Key code** | `model = lgb.train(params, dtrain, valid_sets=[dval])` → `model.save_model("reranker.txt")` |
| **Notebook** | `notebooks/hybrid-ensemble-recommendation.ipynb` · cell 60 |
| **Role at inference** | `model.predict(X_1000x6)` → 1000 float scores → `argsort(-scores)[:k]` → top-k article IDs returned to caller. **Real model inference happens here.** |

---

### `valid_clicks.parquet`

| Field | Value |
|---|---|
| **Type** | Raw data file (not a model or derived artifact) |
| **Meaning** | The held-out validation click dataset from the original recommendation corpus. One row per user. Used at inference time for two purposes: (1) the `ground_truth` field in the response (for demo/evaluation display), and (2) stored user profiles (device, OS, country). |
| **Source data** | Original recommendation dataset |
| **How computed** | Not computed — this is the raw validation split of the dataset. It was the held-out set used during model evaluation. |
| **Columns used at inference** | `user_id`, `click_article_id` (ground truth), `click_deviceGroup`, `click_os`, `click_country` |
| **Role at inference** | Loaded at cold start. Provides `ground_truth` for display and populates `user_profiles` dict. No computation on it per request. |

> ⚠️ **Known issue:** `click_country` is stored as a numeric `uint8` code (from `data-processing.ipynb`'s dtype optimisation) — not as an ISO string. This is the root cause of the cold-path contextual lookup miss (see `top_lists.pkl` note above and [Known Issues](architecture/README.md#known-issues)).

---

## What computation actually happens at request time?

This table directly answers whether the system is doing "live inference" or "table lookup" at each step.

| Step | What runs | Type |
|---|---|---|
| Cold routing | `last_click[user_id] == -1` | Array index — **lookup** |
| Load user profile | `user_profiles.get(user_id)` | Dict lookup — **no computation** |
| **Cold path — slot 1–4** | `TOP["by_os"][os_id]` etc. | Dict + array index — **lookup** |
| **Cold path — fallback** | Iterate `pop_list` | Array iteration — **no computation** |
| **Warm — CF candidates** | `cf_i2i_top300[last_click[u]]` | Array index — **lookup** |
| **Warm — ALS candidates** | `als_top100[u]` | Array index — **lookup** |
| **Warm — Pop candidates** | Iterate `pop_list` | Array iteration — **no computation** |
| **Warm — TT candidates** | `tt_top200[u]` | Array index — **lookup** |
| **Warm — cosine similarity** | `dot(user_vec[u], item_vec[cand]) / (‖u‖·‖i‖)` per ~1000 candidates | **NumPy matrix operation — computed live** |
| **Warm — LightGBM scoring** | `model.predict(X_1000x6)` | **Model inference — computed live** |
| **Warm — top-k selection** | `argsort(-scores)[:k]` | **NumPy sort — computed live** |

**Summary:** For cold users, the entire response is precomputed table lookups — zero model inference. For warm users, the candidate lists are all precomputed lookups, but the **cosine similarity computation**, **LightGBM scoring**, and **final sort** all happen live at request time.

---

## Training dependency graph

```
Raw dataset
  │
  ├─ train_clicks.parquet ──────────────────────────────────┐
  │    │                                                     │
  │    ├─► last_click.npy          (max-timestamp groupby)  │
  │    │                                                     │
  │    ├─► cf_i2i_top300.npy       (item cosine sim matrix) │
  │    │                                                     │
  │    ├─► als_top100.npy          (ALS matrix factor.)     │
  │    │                                                     │
  │    └─► pop_list.npy            (click count argsort)    │
  │                                                          │
  ├─ articles_embeddings.pickle                              │
  │    │                                                     │
  │    └─► Two-Tower training (BPR, 50 neg, 15 ep.)         │
  │              │                                           │
  │              ├─► final_twotower_user_vec.npy             │
  │              ├─► final_twotower_item_vec.npy             │
  │              └─► tt_top200.npy   (user_vec@item_vec.T)  │
  │                                                          │
  └─ valid_clicks.parquet                                    │
       │  (as training labels for LightGBM)                  │
       └─────────────────────────────────────────────────────┤
                                                             │
                        ┌────────────────────────────────────┘
                        │  (all lookup tables + embeddings)
                        ▼
               LightGBM lambdarank training
               (1000-candidate pool per user,
                6 features per candidate,
                label = 1 if == ground truth)
                        │
                        └─► reranker.txt
```

---

## Notebook → artifact mapping

| Notebook | Cell | Artifacts produced |
|---|---|---|
| `notebooks/hybrid-ensemble-recommendation.ipynb` | 54 | `final_twotower_user_vec.npy`, `final_twotower_item_vec.npy` |
| `notebooks/hybrid-ensemble-recommendation.ipynb` | 56 | `last_click.npy`, `cf_i2i_top300.npy`, `als_top100.npy`, `tt_top200.npy`, `pop_list.npy` |
| `notebooks/hybrid-ensemble-recommendation.ipynb` | 60 | `reranker.txt` |
| Popularity notebook / manual | — | `top_lists.pkl` (exact build cell not in downloaded notebooks) |
| Raw dataset split | — | `valid_clicks.parquet` (provided, not generated) |
