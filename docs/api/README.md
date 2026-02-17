# API Documentation

Current API surface for the deployed recommender backend.

## Base URL

- Production: `https://ocp9funcapp-recsys.azurewebsites.net/api`
- Local (Functions host): `http://localhost:7071/api`

## Supported Endpoint

### `POST /reco`

Generate recommendations for one user.

#### Request body

```json
{
  "user_id": 1001,
  "k": 10,
  "env": {
    "device": 1,
    "os": 17,
    "country": "DE"
  }
}
```

- `user_id` (required): integer user id.
- `k` (optional): recommendation count, clamped to `1..100` (default `10`).
- `env` (optional): context overrides used mainly for cold-start behavior.

#### Success response

```json
{
  "recommendations": [58793, 59156, 58020, 57771, 30605],
  "ground_truth": 26859,
  "user_profile": {
    "stored": {"device": 1, "os": 17, "country": "DE"},
    "used": {"device": 1, "os": 17, "country": "DE"},
    "overrides_applied": false
  }
}
```

#### Error response

```json
{
  "error": "user_id out of range"
}
```

Common error cases:
- Invalid JSON payload -> `400`
- Negative or out-of-range `user_id` -> `400`

## Important Note

- There is no public `GET /health` endpoint on the current deployed API.

## Smoke Test

```bash
curl -X POST "https://ocp9funcapp-recsys.azurewebsites.net/api/reco" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1001, "k": 5, "env": {"device": 1, "os": 3, "country": "US"}}'
```
