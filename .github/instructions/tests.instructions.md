---
applyTo: "tests/**/*.py"
---

# Testing Instructions

## Test Organization
- `tests/unit/` - Unit tests (mocked dependencies, fast execution)
- `tests/integration/` - Integration tests (real database, external services mocked)
- `tests/conftest.py` - Shared fixtures

## Pytest Configuration
Tests run with `pytest-asyncio` in auto mode. All async tests work automatically:
```python
async def test_get_track_returns_track():
    # No decorator needed - asyncio_mode=auto in pyproject.toml
    result = await service.get_track("track-123")
    assert result is not None
```

## Test Markers
Use markers defined in `pyproject.toml`:
```python
import pytest

@pytest.mark.slow
async def test_full_sync():
    ...

@pytest.mark.integration
async def test_database_operations():
    ...

@pytest.mark.unit
def test_parse_duration():
    ...
```

Run specific tests:
- Unit only: `pytest -m unit`
- Skip slow: `pytest -m "not slow"`

## Fixtures
Use `factory_boy` for test data factories. Use `pytest-mock` for mocking.

### HTTP Mocking
Use `pytest-httpx` for HTTP client tests:
```python
async def test_spotify_api_call(httpx_mock):
    httpx_mock.add_response(
        url="https://api.spotify.com/v1/tracks/123",
        json={"id": "123", "name": "Test Track"}
    )
    result = await spotify_client.get_track("123")
    assert result["name"] == "Test Track"
```

### Database Testing
For integration tests, use in-memory SQLite:
```python
from soulspot.infrastructure.persistence.models import Base

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session
```

## Test Naming
Use descriptive names that explain the scenario:
```python
def test_parse_duration_returns_seconds_for_valid_input():
    ...

async def test_get_track_raises_not_found_for_missing_track():
    ...
```

## Assertions
Use plain `assert` statements (pytest rewrites them for helpful output).
For complex assertions, use `pytest.approx()` for floats.

## Coverage Target
- Minimum: 80% overall
- Service layer: 100%
- Run with: `pytest --cov=src/soulspot --cov-report=term-missing`
