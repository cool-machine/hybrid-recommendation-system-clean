# Deployment Guide

## Current deployment paths

- Backend API: Azure Functions app `ocp9funcapp-recsys`
- Frontend UI: Streamlit Cloud app linked to this repository

## Azure Functions deployment (manual publish)

```bash
cd deployment/azure_functions
func azure functionapp publish ocp9funcapp-recsys --python
```

## API smoke test

```bash
curl -X POST "https://ocp9funcapp-recsys.azurewebsites.net/api/reco" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 12345, "k": 5, "env": {"device": 1, "os": 3, "country": "US"}}'
```

## Streamlit entrypoint

- Cloud wrapper entrypoint: `streamlit_app.py`
- Canonical app executed by wrapper: `deployment/streamlit/app.py`

## Notes

- Large model artifacts are excluded from Git and must be present in the deployed runtime/storage environment.
- Preferred local runtime location is `external_runtime_assets/azure/artifacts/`.
