---
applyTo: "**/*.py"
---

# Python Code Guidelines

## Type Hints (Strict Mode)
- All public functions MUST have explicit type hints for parameters and return values.
- `mypy` is configured with `strict = true` in `pyproject.toml`.
- Use `Optional[T]` or `T | None` for nullable types.

## Async Code
- This codebase uses async SQLAlchemy with `aiosqlite`.
- Prefer `async def` and `await` for database operations.
- Use `AsyncSession` from SQLAlchemy for DB transactions.

## Code Style
- `ruff` is the linter and formatter (config in `pyproject.toml`).
- Line length: 88 characters.
- Use double quotes for strings.
- Run `make format` before committing.

## Architecture Layers
```
API (routers) → Application (services) → Domain (models) → Infrastructure (repositories)
```
- Keep business logic in the `application/` layer (services).
- Keep DB access in `infrastructure/` (repositories).
- Domain models in `domain/` should be framework-agnostic.

## Documentation
- Add a brief comment before each function explaining its purpose.
- Include "why" explanations for non-obvious code.
