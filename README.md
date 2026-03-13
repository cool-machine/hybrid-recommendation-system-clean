# Hybrid Recommendation System

**OpenClassrooms — Projet 9 : Réalisez une application de recommandation de contenu**

**Live demo**: [ai-recommender.streamlit.app](https://ai-recommender.streamlit.app) | **API**: `https://ocp9funcapp-recsys.azurewebsites.net/api/reco`

---

## What This Is

A production-deployed content recommendation system built for *My Content*, a start-up encouraging reading by surfacing relevant articles. Given a user ID, the system returns personalised article recommendations via a serverless Azure Functions API backed by a multi-algorithm ensemble.

The project covers the full ML lifecycle: data exploration, model research (three notebooks), a clean Python source package, deployment on Azure, and a Streamlit demo interface.

---

## Architecture

### Algorithms

| Algorithm | Role | Candidates |
|-----------|------|-----------|
| Item-to-Item Collaborative Filtering | Last-click similarity | up to 300 |
| ALS Matrix Factorization | Latent user preferences | up to 100 |
| Contextual Popularity | Cold-start (no history) | fills to k |
| Two-Tower Neural Embeddings | Deep user-item similarity | up to 200 |
| LightGBM Reranker | Final scoring (6 features) | top-k output |

### Request flow

```
POST /api/reco  ->  cold/warm detection
                     |
          +----------+-----------+
          v                      v
  Cold user                  Warm user
  Contextual popularity      CF + ALS + Two-Tower + Popularity
  blend (device/OS/country)  -> LightGBM reranker
          |                      |
          +----------+-----------+
                     v
            JSON: top-k article IDs
                + ground_truth
                + user_profile
```

---

## API

```bash
curl -X POST "https://ocp9funcapp-recsys.azurewebsites.net/api/reco" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1001, "k": 5}'
```

```json
{
  "recommendations": [58793, 59156, 58020, 57771, 30605],
  "ground_truth": 26859,
  "user_profile": {
    "stored": {"device": 1, "os": 17, "country": "DE"},
    "used":   {"device": 1, "os": 17, "country": "DE"},
    "overrides_applied": false
  }
}
```

Full API reference: [`docs/api/README.md`](docs/api/README.md)

---

## Repository Structure

```
.
├── livrables/                   # OpenClassrooms submission zips (3 livrables)
│
├── src/
│   ├── models/                  # CF, Popularity, Reranker classes
│   ├── training/                # Data preparation utilities
│   ├── service.py               # Business logic orchestration
│   ├── api.py                   # Pydantic request/response models
│   └── config.py                # Configuration management
│
├── deployment/
│   ├── azure_functions/         # Production Azure Functions backend
│   └── streamlit/               # Streamlit web interface
│
├── notebooks/
│   ├── collaborative-filtering.ipynb
│   ├── matrix-factorization-als.ipynb
│   └── hybrid-ensemble-recommendation.ipynb
│
├── tests/
│   ├── unit/                    # pytest unit tests
│   └── fixtures/                # Mock models and sample data
│
├── data/sample/                 # Small CSVs for local testing
├── docs/                        # API reference, architecture, guides
├── streamlit_app.py             # Streamlit Cloud entry point
└── requirements.txt
```

---

## Quick Start

```bash
git clone https://github.com/cool-machine/hybrid-recommendation-system.git
cd hybrid-recommendation-system
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/
```

To run the Streamlit interface locally:

```bash
export RECO_API_URL="https://ocp9funcapp-recsys.azurewebsites.net/api/reco"
streamlit run deployment/streamlit/app.py
```

---

## Deployment

See [`deployment/DEPLOYMENT.md`](deployment/DEPLOYMENT.md) for step-by-step instructions.

**Note on model artifacts**: The trained model files (~406 MB total: `.npy` arrays, LightGBM model, popularity tables) are excluded from Git due to size. They are deployed directly into the Azure Functions runtime environment.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`docs/api/README.md`](docs/api/README.md) | API endpoint reference |
| [`docs/architecture/README.md`](docs/architecture/README.md) | System architecture and design |
| [`docs/guides/getting-started.md`](docs/guides/getting-started.md) | Quick integration guide |
| [`deployment/DEPLOYMENT.md`](deployment/DEPLOYMENT.md) | Deployment instructions |
| [`livrables/README.md`](livrables/README.md) | Submission package index |

---

## Tech Stack

**Backend**: Python 3.10+, Azure Functions v2
**ML**: NumPy, SciPy, LightGBM, implicit (ALS)
**Frontend**: Streamlit
**Testing**: pytest
