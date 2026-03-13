# API Documentation

> For architecture details see [`docs/architecture/README.md`](../architecture/README.md). For the handoff state see [`CONTEXT.md`](../../CONTEXT.md).

---

## Base URL

| Environment | URL |
|---|---|
| Production | `https://ocp9funcapp-recsys.azurewebsites.net/api` |
| Local (Azure Functions Core Tools) | `http://localhost:7071/api` |

No authentication required (anonymous auth level).

---

## Endpoint

### `POST /reco`

Generate top-k article recommendations for one user.

#### Request body

```json
{
  "user_id": 1001,
  "k": 10,
  "env": {
    "device": 1,
    "os": 17,
    "country": "US"
  }
}
```

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `user_id` | int | yes | — | Must be in range [0, 65535] |
| `k` | int | no | 10 | Clamped to [1, 100] |
| `env` | object | no | {} | Context overrides; see below |

#### `env` override fields

| Field | Type | Notes |
|---|---|---|
| `device` | int | Device group (0 = mobile, 1 = tablet, 2 = desktop) |
| `os` | int | OS group id (integer code) |
| `country` | string | **ISO 3166-1 alpha-2** e.g. `"US"`, `"FR"` ⚠️ see note below |

> **Country encoding note:** Stored user profiles currently have `country` as a numeric string (`"1"`) due to an upstream data preprocessing issue. Passing an ISO country code via the `env` override will activate the contextual `by_os_reg` / `by_dev_reg` popularity tables correctly; without the override the cold path silently falls back to `global_top`. See [Known Issues in architecture docs](../architecture/README.md#known-issues).

#### Success response (HTTP 200)

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

| Field | Type | Notes |
|---|---|---|
| `recommendations` | int[] | Article IDs, length = k, ordered by predicted relevance |
| `ground_truth` | int \| null | Held-out next click from validation set; null if user not in ground truth |
| `user_profile.stored` | object | Profile loaded from `valid_clicks.parquet` |
| `user_profile.used` | object | Effective context after env overrides applied |
| `user_profile.overrides_applied` | bool | True if non-empty `env` was provided in the request |

#### Error response (HTTP 400)

```json
{ "error": "user_id out of range" }
```

| Cause | Error message |
|---|---|
| Invalid JSON | `"Invalid JSON"` |
| `user_id < 0` or `user_id >= 65536` | `"user_id out of range"` |

---

## Routing logic

The function routes each request to one of two paths based on the user's click history:

- **Cold user** (`last_click[user_id] == -1`): contextual popularity blend from precomputed tables
- **Warm user** (has history): CF + ALS + Two-Tower + Popularity candidate pool → LightGBM reranker

See [`docs/architecture/README.md`](../architecture/README.md) for the full pipeline.

---

## Smoke tests (verified 2026-03-13)

```bash
# Basic warm-user request
curl -X POST "https://ocp9funcapp-recsys.azurewebsites.net/api/reco" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "k": 5}'

# With context override (activates contextual cold-start tables)
curl -X POST "https://ocp9funcapp-recsys.azurewebsites.net/api/reco" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 5, "k": 5, "env": {"device": 0, "os": 0, "country": "US"}}'

# Out-of-range user → 400
curl -X POST "https://ocp9funcapp-recsys.azurewebsites.net/api/reco" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 99999, "k": 5}'
```

---

## Notes

- **No `GET /health` endpoint.** Cold-start monitoring requires a real `POST /api/reco` call.
- **First call per instance is slower** (~5–10 s) due to Azure Functions cold start loading ~433 MB of artifacts.
- Warm requests are sub-second.
- The `ground_truth` field is for demo/evaluation display in the Streamlit UI; it is always null in a real production deployment where the true next click is unknown.
