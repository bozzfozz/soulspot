---
applyTo: "tests/**/*"
---

# Test Guidelines

## Test Framework
- Use `pytest` with `pytest-asyncio` for async tests.
- Tests are auto-detected under `tests/` directory.
- Run `make test` or `pytest tests/ -v`.

## Async Tests
- Use `async def test_...` for async functions.
- `asyncio_mode=auto` is configured in `pyproject.toml`.

## Test Organization
- `tests/unit/` — isolated unit tests (no external deps)
- `tests/integration/` — tests with real services/DB

## Mocking & Fixtures
- Use `pytest-mock` for mocking.
- Use `pytest-httpx` for HTTP client mocking.
- Use `factory-boy` for test data factories.

## Coverage
- Run `make test-cov` to generate coverage reports.
- Coverage reports go to `htmlcov/`.

## Best Practices
- One assertion per test when possible.
- Use descriptive test names: `test_should_<expected_behavior>_when_<condition>`.
- Mark slow tests with `@pytest.mark.slow`.
