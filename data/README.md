# Data Directory

This directory contains sample and test datasets for the recommendation system.

## Structure

```
data/
└── sample/           # Small sample datasets for testing and demos
```

## Sample Data

- `sample_users.csv` - Sample user profiles for testing
- `sample_interactions.csv` - Sample user-item interactions
- `sample_articles.csv` - Sample article metadata

## Usage

```python
import pandas as pd

# Load sample data
users = pd.read_csv('data/sample/sample_users.csv')
interactions = pd.read_csv('data/sample/sample_interactions.csv')
articles = pd.read_csv('data/sample/sample_articles.csv')
```

## Data Format

### Users
- `user_id`: Unique user identifier (int)
- `device`: Device type (0=mobile, 1=desktop, 2=tablet)
- `os`: Operating system (0-17)
- `country`: ISO country code (str)

### Interactions
- `user_id`: User identifier
- `article_id`: Article identifier  
- `timestamp`: Unix timestamp
- `click_type`: Type of interaction

### Articles
- `article_id`: Unique article identifier
- `category_id`: Article category
- `created_at`: Creation timestamp
- `word_count`: Article length