# Getting Started

Quick guide to call the recommender API and run the Streamlit demo.

## 1) Call the API

```bash
curl -X POST "https://ocp9funcapp-recsys.azurewebsites.net/api/reco" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1001, "k": 5}'
```

You should receive a JSON response containing:
- `recommendations`
- `ground_truth` (when available)
- `user_profile` with stored/used context info

## 2) Try context overrides

```bash
curl -X POST "https://ocp9funcapp-recsys.azurewebsites.net/api/reco" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1001,
    "k": 5,
    "env": {"device": 0, "os": 1, "country": "US"}
  }'
```

## 3) Run Streamlit locally

From repository root:

```bash
streamlit run deployment/streamlit/app.py --server.port 8501
```

Set backend URL before launch:

```bash
export RECO_API_URL="https://ocp9funcapp-recsys.azurewebsites.net/api/reco"
```

## Notes

- There is no public `GET /health` endpoint for this deployment.
- First API call may be slower due to Azure Functions cold start.
- For cold users, context has stronger influence than for warm users.

## Related docs

- API reference: `docs/api/README.md`
- Architecture: `docs/architecture/README.md`
- Deployment details: `deployment/DEPLOYMENT.md`
