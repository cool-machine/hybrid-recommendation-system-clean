# Tests Directory

Comprehensive test suite for the recommendation system.

## Structure

```
tests/
├── unit/              # Unit tests
│   ├── test_config.py
│   ├── test_model_registry.py
│   └── test_contextual_popularity.py
├── integration/       # Integration tests (placeholder)
├── fixtures/          # Test data and mock objects
├── conftest.py        # Pytest configuration and shared fixtures
└── README.md          # This file
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

## Test Categories

### Unit Tests
- `tests/unit/test_config.py` — Config dataclass creation and validation
- `tests/unit/test_model_registry.py` — ModelRegistry registration and lookup
- `tests/unit/test_contextual_popularity.py` — Cold-start popularity logic

### Integration Tests
- `tests/integration/` is scaffolded for future integration tests

### Fixtures
- `fixtures/sample_data.py` — Test datasets
- `fixtures/mock_models.py` — Mock model objects
- `fixtures/test_config.py` — Test configurations

## Test Data

Tests use sample data from `data/sample/` and test-specific fixtures from `tests/fixtures/`.

## Guidelines

1. **Isolate tests** - Each test should be independent
2. **Use fixtures** - Reuse test data and setup
3. **Mock external calls** - Don't hit real APIs in tests
4. **Test edge cases** - Include error conditions
5. **Keep tests fast** - Unit tests should run in seconds