# Hybrid Recommendation System

Production-grade content recommendation application with a live Streamlit demo and scale-to-zero AWS Lambda API.

**Live demo**: [ai-recommender.streamlit.app](https://ai-recommender.streamlit.app) | **API**: `https://j6b3z6xge2l2pkyatv46jc6hem0gswse.lambda-url.us-east-1.on.aws/api/reco`

---

## What This Is

A production-deployed content recommendation system built for *My Content*, a start-up encouraging reading by surfacing relevant articles. Given a user ID, the system returns personalised article recommendations via a serverless AWS Lambda API backed by a multi-algorithm ensemble.

The project covers the full ML lifecycle: data exploration, model research (three notebooks), a clean Python source package, deployment on AWS, and a Streamlit demo interface.

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
curl -X POST "https://j6b3z6xge2l2pkyatv46jc6hem0gswse.lambda-url.us-east-1.on.aws/api/reco" \
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
├── src/
│   ├── models/                  # CF, Popularity, Reranker classes
│   ├── training/                # Data preparation utilities
│   ├── service.py               # Business logic orchestration
│   ├── api.py                   # Pydantic request/response models
│   └── config.py                # Configuration management
│
├── deployment/
│   ├── azure_functions/         # Temporary Azure rollback backend
│   └── streamlit/               # Streamlit web interface
├── aws_lambda/                  # AWS handler, container and CloudFormation stack
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
git clone https://github.com/cool-machine/hybrid-recommendation-system-clean.git
cd hybrid-recommendation-system-clean
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/
```

To run the Streamlit interface locally:

```bash
export OCP9_API_URL="https://j6b3z6xge2l2pkyatv46jc6hem0gswse.lambda-url.us-east-1.on.aws/api/reco"
streamlit run deployment/streamlit/app.py
```

---

## Deployment

See [`deployment/DEPLOYMENT.md`](deployment/DEPLOYMENT.md) for step-by-step instructions.

**Note on model artifacts**: The 13 verified runtime/training-evidence files (425.5 MB total) are excluded from Git. They are stored in the private stack-owned S3 bucket; the Lambda downloads and hash-verifies the ten serving files on cold start.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`docs/api/README.md`](docs/api/README.md) | API endpoint reference |
| [`docs/architecture/README.md`](docs/architecture/README.md) | System architecture and design |
| [`docs/guides/getting-started.md`](docs/guides/getting-started.md) | Quick integration guide |
| [`deployment/DEPLOYMENT.md`](deployment/DEPLOYMENT.md) | Deployment instructions |
| [`docs/README.md`](docs/README.md) | Documentation index |

---

## Tech Stack

**Backend**: Python 3.12, AWS Lambda container, S3, ECR, CloudFormation
**ML**: NumPy, SciPy, LightGBM, implicit (ALS)
**Frontend**: Streamlit
**Testing**: pytest
