# Tests Directory

Comprehensive test suite for the recommendation system.

## Structure

```
tests/
├── fixtures/          # Test data and mock objects
├── conftest.py       # Pytest configuration and fixtures
└── README.md         # Test scope and archive notes
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
- Active tests:
  - `tests/unit/test_config.py`
  - `tests/unit/test_model_registry.py`
  - `tests/unit/test_contextual_popularity.py`
- Legacy unit tests remain archived in `removed/old_files/tests_legacy/unit/`

### Integration Tests
- Legacy integration tests were archived to `removed/old_files/tests_legacy/integration/`
- Active test scaffolding currently focuses on reusable fixtures/config setup

### Fixtures
- `sample_data.py` - Test datasets
- `mock_models.py` - Mock model objects
- `test_config.py` - Test configurations

## Test Data

Tests use sample data from `data/sample/` and test-specific fixtures from `tests/fixtures/`.

## Guidelines

1. **Isolate tests** - Each test should be independent
2. **Use fixtures** - Reuse test data and setup
3. **Mock external calls** - Don't hit real APIs in tests
4. **Test edge cases** - Include error conditions
5. **Keep tests fast** - Unit tests should run in seconds