# Documentation

Active documentation for the hybrid recommendation system.

## Navigation

| Document | What it covers |
|---|---|
| [`CONTEXT.md`](../CONTEXT.md) | **Session handoff** — system summary, AWS deployment state, Azure rollback, full data flow, known issues, next steps |
| [`ALGORITHMS.md`](../ALGORITHMS.md) | **Algorithm story** — every algorithm tried, metrics, verdicts, production call sequences with LOOKUP/LIVE annotations |
| [`docs/artifacts.md`](artifacts.md) | **Artifact reference** — for every deployed file: type, derivation, AWS storage and inference role |
| [`docs/architecture/README.md`](architecture/README.md) | **Architecture** — AWS resources, call sequences, Azure rollback and known issues |
| [`docs/api/README.md`](api/README.md) | **API reference** — endpoint, request/response schema, smoke tests |
| [`docs/guides/getting-started.md`](guides/getting-started.md) | **Quick start** — curl examples, local Streamlit setup |
| [`deployment/DEPLOYMENT.md`](../deployment/DEPLOYMENT.md) | **Deployment** — CloudFormation/GitHub deployment, Streamlit and temporary Azure rollback |

## Quick links

- Live endpoint: `POST https://j6b3z6xge2l2pkyatv46jc6hem0gswse.lambda-url.us-east-1.on.aws/api/reco`
- Tests: `uv run pytest tests/ -v`

## Scope

This docs folder documents the currently deployed system only. Stale or experimental content belongs in `secondary_assets/`, not here.
