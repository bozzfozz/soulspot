---
applyTo: "src/soulspot/**/*.py"
---

# Python Backend Instructions

## Architecture Pattern
This project follows **Clean/Onion Architecture** with distinct layers:
- `api/` - FastAPI routes, schemas, dependencies
- `application/` - Use cases and application services
- `domain/` - Entities, value objects, exceptions, ports (interfaces)
- `infrastructure/` - External integrations, persistence, security

**Rule**: Code flows inward - inner layers never import from outer layers.

## Coding Standards

### Type Hints
All functions **MUST** have complete type annotations. The project uses `mypy` with `strict = true`:
```python
def process_track(track_id: str, options: ProcessOptions | None = None) -> TrackResult:
    ...
```

### Async/Await
Database operations and HTTP clients use **async/await**. Use `httpx.AsyncClient` for HTTP and SQLAlchemy async session:
```python
async def get_track(self, track_id: str) -> Track | None:
    async with self._session() as session:
        result = await session.execute(select(TrackModel).where(TrackModel.id == track_id))
        return result.scalar_one_or_none()
```

### Settings Access
**Never** use `os.getenv()` directly. Use the Settings service:
```python
from soulspot.config import get_settings
settings = get_settings()
url = settings.spotify.client_id  # NOT os.getenv("SPOTIFY_CLIENT_ID")
```

### Error Handling
Use structured domain exceptions from `domain/exceptions/`:
```python
from soulspot.domain.exceptions import TrackNotFoundError
raise TrackNotFoundError(track_id=track_id)
```

### Future-Self Comments
Every new function needs a comment explaining the "why":
```python
# Hey future me - this function handles rate limiting from MusicBrainz.
# The API allows max 1 req/sec, so we use exponential backoff on 429s.
# Watch out: the circuit breaker resets after 60 seconds of success.
async def fetch_metadata(mbid: str) -> MusicBrainzData:
    ...
```

## Import Order
1. Standard library
2. Third-party packages
3. Local application imports

Use `ruff` for automatic sorting: `ruff check --fix`

## Testing
- Unit tests go in `tests/unit/`
- Integration tests go in `tests/integration/`
- Use `pytest-asyncio` for async tests
- Use `pytest-httpx` for HTTP client mocking
- Target coverage: 80%+ overall, 100% for service layer

## Key Files Reference
- Entry point: `src/soulspot/main.py`
- Settings: `src/soulspot/config/settings.py`
- Models: `src/soulspot/infrastructure/persistence/models.py`
- Repositories: `src/soulspot/infrastructure/persistence/repositories.py`
- Database session: `src/soulspot/infrastructure/persistence/database.py`
