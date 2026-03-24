# Documentation

Active documentation for the hybrid recommendation system.

## Navigation

| Document | What it covers |
|---|---|
| [`CONTEXT.md`](../CONTEXT.md) | **Session handoff** — system summary, Azure deployment state, full data flow, known issues, next steps |
| [`ALGORITHMS.md`](../ALGORITHMS.md) | **Algorithm story** — every algorithm tried, metrics, verdicts, production call sequences with LOOKUP/LIVE annotations |
| [`docs/artifacts.md`](artifacts.md) | **Artifact reference** — for every deployed file: type (lookup table / live model / raw data), how it was computed, where it lives in Azure, role at inference time |
| [`docs/architecture/README.md`](architecture/README.md) | **Architecture** — Azure resources, call sequences, known issues |
| [`docs/api/README.md`](api/README.md) | **API reference** — endpoint, request/response schema, smoke tests |
| [`docs/guides/getting-started.md`](guides/getting-started.md) | **Quick start** — curl examples, local Streamlit setup |
| [`deployment/DEPLOYMENT.md`](../deployment/DEPLOYMENT.md) | **Deployment** — how to redeploy the Azure Function and Streamlit app |

## Quick links

- Live endpoint: `POST https://ocp9funcapp-recsys.azurewebsites.net/api/reco`
- Tests: `uv run pytest tests/ -v`

## Scope

This docs folder documents the currently deployed system only. Stale or experimental content belongs in `secondary_assets/`, not here.
