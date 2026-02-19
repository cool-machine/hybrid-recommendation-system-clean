# Hybrid Recommendation System

**Live Demo**: [Streamlit App](https://ai-recommender.streamlit.app) | **API**: `https://ocp9funcapp-recsys.azurewebsites.net/api/reco`

## Overview

Production-grade recommendation system deployed on Azure, featuring a multi-algorithm ensemble with 65K real user profiles and 406MB of trained ML models.

## Architecture

### Core Algorithms
1. **Collaborative Filtering**: Item-to-item similarity using implicit feedback
2. **ALS Matrix Factorization**: Latent factor model for user preferences  
3. **Two-Tower Neural Network**: Deep learning embeddings
4. **LightGBM Reranker**: Final ranking with 6 engineered features
5. **Contextual Popularity**: Cold-start with device/OS/region awareness

### System Design
```python
# Multi-stage candidate generation
cf_candidates = collaborative_filtering(user_last_click)     # 300 items
als_candidates = matrix_factorization(user_id)              # 100 items  
popularity_candidates = global_popularity()                 # 200 items
neural_candidates = two_tower_network(user_id)              # 200 items

# Final reranking with LightGBM
final_recommendations = lightgbm_reranker.predict(
    all_candidates, user_features
)[:k]
```

## Technical Highlights

### Performance & Scale
- **Live Production API**: Azure Functions with auto-scaling
- **Response Time**: Sub-second latency on consumption plan
- **Model Size**: 406MB optimized artifacts with lazy loading
- **User Base**: 65,535 users with real profile data

### Code Quality
- **~1,500 lines** of production Python code
- **Full type annotations** with modern Python 3.10+ features
- **Comprehensive error handling** and logging
- **Clean architecture** with separation of concerns

### Data Engineering
- **Real User Profiles**: Device/OS/country extracted from interaction logs
- **Context Awareness**: Different algorithms for cold vs warm users
- **Hybrid Approach**: Stored profiles with manual override capability

## API Usage

### Request
```json
POST /api/reco
{
    "user_id": 12345,
    "k": 10,
    "env": {"device": 1, "os": 2, "country": "US"}
}
```

### Response
```json
{
    "recommendations": [58793, 59156, 58020],
    "ground_truth": 26859,
    "user_profile": {
        "stored": {"device": 1, "os": 17, "country": "DE"},
        "used": {"device": 1, "os": 2, "country": "US"},
        "overrides_applied": true
    }
}
```

## Development

### Quick Start
```bash
git clone [repository]
cd recommender
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/
```

### Repository cleanup note

Non-essential presentation and submission artifacts are kept in `secondary_assets/` (gitignored).
Runtime files that should stay out of GitHub (model artifacts, local Streamlit secrets/config) are stored in `external_runtime_assets/` (gitignored).

### Project Structure
```
src/
├── models/          # ML algorithm implementations
├── training/        # Data preparation utilities
├── service.py       # Business logic orchestration
├── api.py           # Azure Functions API with Pydantic validation
└── config.py        # Configuration management

deployment/
├── azure_functions/ # Production Azure Functions backend
└── streamlit/       # Web interface demo

notebooks/           # Research notebooks (CF, ALS, ensemble)
data/sample/         # Small sample datasets for testing
tests/
├── unit/            # Unit tests
├── fixtures/        # Test data and mocks
└── conftest.py      # Shared pytest fixtures/config
```

## Technical Stack

**Backend**: Python 3.10, Azure Functions, Pydantic
**ML**: NumPy, SciPy, LightGBM, implicit
**Infrastructure**: Azure Functions, Azure Blob Storage
**Frontend**: Streamlit with responsive UI
**Testing**: pytest, unittest.mock

## Key Features

1. **Multi-Algorithm Ensemble**: Combines 4 different ML approaches
2. **Context-Aware Cold Start**: Adapts to user device/location/OS
3. **Production Deployment**: Live Azure Functions with monitoring
4. **Real-Time API**: RESTful endpoints with proper validation
5. **Operational Validation**: runtime smoke checks and fixture-driven verification

---

*This system demonstrates full-stack ML engineering from research to production deployment.*