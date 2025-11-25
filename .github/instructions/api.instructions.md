---
applyTo: "src/soulspot/api/**/*"
---

# FastAPI API Guidelines

## Route Definitions
- Place routes in `src/soulspot/api/routers/`.
- Use type hints for request/response models.
- Document endpoints with docstrings (auto-generates OpenAPI docs).

## Request/Response Models
- Use Pydantic models for request validation.
- Define models in `src/soulspot/api/schemas/` or alongside routers.
- Use `response_model` parameter for response validation.

## Dependency Injection
- Use FastAPI's `Depends()` for dependencies.
- Session dependencies provide `AsyncSession`.
- Config dependencies provide application settings.

## Error Handling
- Use `HTTPException` for client errors (4xx).
- Use structured error responses.
- Log server errors (5xx) appropriately.

## Authentication
- JWT tokens for API authentication.
- OAuth2 for Spotify integration.
- Use `python-jose` for token handling.

## Best Practices
- Keep routes thin — delegate to services.
- Use meaningful HTTP status codes.
- Validate inputs with Pydantic, not manual checks.
