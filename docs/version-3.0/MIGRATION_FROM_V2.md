# Migration from Version 2.x to Version 3.0

**Document Status**: Architecture Specification  
**Last Updated**: 2025-11-22  
**Target Audience**: Developers implementing Version 3.0

---

## Overview

This document provides guidelines for migrating existing code from the main branch (Version 2.x) to Version 3.0 modular architecture while maintaining quality standards and avoiding technical debt.

**Key Principle**: We leverage existing implementations where they align with Version 3.0 architecture, but we **rigorously validate and refactor** to meet new standards. We do NOT blindly copy code.

---

## 1. Code Reuse Strategy

### 1.1 What to Reuse

**✅ CAN be reused (with validation):**

1. **Business Logic**
   - Track quality scoring algorithms
   - File format detection logic
   - Metadata parsing functions
   - Search query processing
   - Download state management logic

2. **Domain Knowledge**
   - MusicBrainz API integration patterns
   - Spotify API request/response handling
   - slskd client communication logic
   - Audio file quality assessment

3. **Tested Functions**
   - Utility functions with good test coverage
   - Data validation functions
   - Conversion functions (format, units, etc.)

4. **Configuration Parsing**
   - Environment variable handling (adapted to new onboarding)
   - Service URL validation
   - Credential format validation

**❌ MUST NOT be reused directly:**

1. **Database Access Code**
   - Direct SQLAlchemy calls → Must use Database Module
   - ORM models → Must be adapted to Database Module entities
   - Migration scripts → New schema for modular architecture

2. **Monolithic Architecture Code**
   - Cross-layer imports → Must respect module boundaries
   - Tightly coupled components → Must be decoupled
   - God objects → Must be split into focused modules

3. **Dead Code**
   - Unused functions or classes
   - Commented-out code blocks
   - Deprecated features
   - Placeholder implementations

4. **Non-Standard Code**
   - Code without docstrings
   - Magic numbers without explanation
   - Complex algorithms without documentation
   - Code violating new architecture principles

---

## 2. Code Quality Checklist

### 2.1 Before Migrating Any Code

**Every piece of code from Version 2.x MUST pass this checklist:**

```markdown
## Code Migration Quality Checklist

### Architecture Compliance
- [ ] Fits within a single module's responsibility
- [ ] Respects module boundaries (no cross-module DB access)
- [ ] Uses Database Module for all data access
- [ ] Does not violate dependency rules (no upward dependencies)
- [ ] Follows event-driven communication patterns

### Code Quality
- [ ] Has comprehensive docstring (Google-style)
- [ ] Has "future-self" comments for tricky parts
- [ ] No magic numbers (all constants explained)
- [ ] No dead code or commented blocks
- [ ] No placeholder TODOs without issues
- [ ] Follows current naming conventions
- [ ] Type hints on all function signatures

### Testing
- [ ] Has unit tests with >80% coverage
- [ ] Tests are up-to-date and passing
- [ ] Integration tests if applicable
- [ ] No test skips without documented reasons

### Documentation
- [ ] Function purpose is clear from docstring
- [ ] Complex algorithms explained
- [ ] Edge cases documented
- [ ] Examples provided for public APIs

### Security
- [ ] No hardcoded credentials or secrets
- [ ] No SQL injection vulnerabilities
- [ ] No path traversal vulnerabilities
- [ ] Input validation present
- [ ] Error messages don't leak sensitive info
```

---

## 3. Migration Process

### 3.1 Step-by-Step Migration

**For each component from Version 2.x:**

#### Step 1: Identify & Assess

```bash
# 1. Find the code in main branch
git checkout main
find src/soulspot -name "*.py" | grep <component_name>

# 2. Review the code
# - Understand its purpose
# - Check dependencies
# - Review tests
# - Check for issues/bugs
```

**Assessment Questions:**
- What does this code do?
- Why does it exist?
- What are its dependencies?
- Does it have tests?
- Are there known bugs or limitations?
- Does it fit Version 3.0 architecture?

#### Step 2: Plan Adaptation

```markdown
## Adaptation Plan for <component>

**Current Location**: src/soulspot/infrastructure/integrations/spotify_client.py
**Target Module**: modules/spotify/submodules/auth/
**Target Location**: modules/spotify/submodules/auth/backend/infrastructure/spotify_client.py

**Required Changes**:
1. Remove direct SQLAlchemy imports
2. Replace database calls with Database Module API
3. Add comprehensive docstrings
4. Extract magic numbers to constants
5. Add "future-self" comments for OAuth flow
6. Update tests to use Database Module mocks

**Risk Assessment**: Medium
- OAuth flow is complex but well-tested
- Credential storage needs Database Module integration
- Token refresh logic needs event publishing

**Estimated Effort**: 4 hours
```

#### Step 3: Extract & Refactor

```python
# ❌ OLD VERSION 2.x CODE (Direct DB Access)
class SpotifyClient:
    def save_token(self, token: dict) -> None:
        """Save OAuth token."""
        # Direct SQLAlchemy - BAD!
        session = Session()
        config = session.query(Config).filter_by(
            key="spotify_token"
        ).first()
        if config:
            config.value = json.dumps(token)
        else:
            config = Config(key="spotify_token", value=json.dumps(token))
            session.add(config)
        session.commit()

# ✅ NEW VERSION 3.0 CODE (Database Module)
class SpotifyClient:
    def __init__(self, db_service: DatabaseService):
        """
        Initialize Spotify API client.
        
        Hey future me – This client handles OAuth token management
        and API requests. Tokens are stored via Database Module
        (not directly in DB) and refreshed automatically when expired.
        
        Args:
            db_service: Database Module service for token storage
        """
        self.db_service = db_service
        
    async def save_token(self, token: dict) -> None:
        """
        Save OAuth token securely.
        
        Token is encrypted before storage (Database Module handles this).
        Publishes 'spotify.token.updated' event for subscribers.
        
        Args:
            token: OAuth token dict with access_token, refresh_token, expires_at
            
        Examples:
            >>> token = {"access_token": "abc", "refresh_token": "xyz", "expires_at": 1234567890}
            >>> await client.save_token(token)
        """
        # Use Database Module - GOOD!
        await self.db_service.save(
            entity_type="spotify_token",
            entity_data=token
        )
        # Database Module publishes database.spotify_token.created event automatically
```

#### Step 4: Add Documentation

```python
"""
Spotify API Client - OAuth 2.0 Authentication

This module handles OAuth 2.0 authentication flow with Spotify API.

**Why This Exists:**
We need to authenticate users with Spotify to access their playlists,
search tracks, and retrieve album information. Spotify requires OAuth 2.0
for all API access.

**Key Components:**
- SpotifyClient: Main API client with automatic token refresh
- TokenStorage: Secure token storage via Database Module
- OAuthFlow: Authorization code flow implementation

**OAuth Flow:**
1. User clicks "Connect Spotify" in onboarding
2. Browser redirects to Spotify authorization URL
3. User grants permissions
4. Spotify redirects back with authorization code
5. We exchange code for access token + refresh token
6. Tokens stored encrypted via Database Module
7. Access token refreshed automatically when expired

**Token Refresh:**
Access tokens expire after 1 hour. We refresh automatically:
- Check expiration before each API call
- If expired, use refresh_token to get new access_token
- Update stored tokens via Database Module
- Retry original API call with new token

**Error Handling:**
- Invalid credentials → Clear error with link to Spotify dashboard
- Token expired → Automatic refresh (transparent to caller)
- Rate limit → Exponential backoff with retry
- Network error → Structured error with troubleshooting steps

**Security:**
- Tokens encrypted via Database Module (Fernet)
- Client secret never logged or exposed in errors
- State parameter prevents CSRF attacks
- PKCE used for additional security

**Related Documentation:**
- OAuth flow diagram: docs/oauth-flow.md
- Token management: docs/token-management.md
- Error codes: docs/error-codes.md
"""
```

#### Step 5: Test Thoroughly

```python
# tests/spotify/auth/test_spotify_client.py

"""
Tests for Spotify OAuth client.

Hey future me – These tests cover the happy path and error scenarios.
Mock the Database Module to avoid actual DB calls during tests.
"""

import pytest
from unittest.mock import AsyncMock
from modules.spotify.submodules.auth.backend.infrastructure.spotify_client import SpotifyClient

@pytest.fixture
def mock_db_service():
    """Mock Database Module for testing."""
    db = AsyncMock()
    return db

@pytest.fixture
def spotify_client(mock_db_service):
    """Spotify client with mocked dependencies."""
    return SpotifyClient(db_service=mock_db_service)

class TestTokenManagement:
    """Test OAuth token storage and refresh."""
    
    async def test_save_token_calls_database_module(
        self, 
        spotify_client, 
        mock_db_service
    ):
        """
        Verify token is saved via Database Module.
        
        Hey future me – This ensures we're not bypassing Database Module.
        Direct DB access would break caching and event publishing.
        """
        token = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_at": 1234567890
        }
        
        await spotify_client.save_token(token)
        
        # Verify Database Module was called correctly
        mock_db_service.save.assert_called_once_with(
            entity_type="spotify_token",
            entity_data=token
        )
    
    async def test_token_refresh_on_expiry(self, spotify_client):
        """
        Verify automatic token refresh when expired.
        
        This is critical – expired tokens would break all Spotify features.
        We refresh transparently without user intervention.
        """
        # Setup: Expired token
        expired_token = {
            "access_token": "old_token",
            "refresh_token": "refresh",
            "expires_at": 1000000000  # In the past
        }
        
        # Mock Spotify API refresh response
        new_token = {
            "access_token": "new_token",
            "refresh_token": "refresh",
            "expires_at": 9999999999  # Future
        }
        
        # TODO: Complete test implementation
        # This needs httpx mock for Spotify API calls
```

#### Step 6: Validate Against Checklist

```markdown
## Validation for spotify_client.py

### Architecture Compliance
- [x] Fits within Spotify auth submodule
- [x] Uses Database Module for all data access
- [x] No cross-module dependencies
- [x] Follows event-driven pattern (DB Module publishes events)
- [x] Respects module boundaries

### Code Quality
- [x] Comprehensive docstring with "Why This Exists"
- [x] "Future-self" comments for OAuth flow complexity
- [x] No magic numbers (token expiry as constant)
- [x] No dead code
- [x] No TODOs without issues
- [x] Type hints on all functions

### Testing
- [x] Unit tests with mocked Database Module
- [x] Tests for token refresh logic
- [x] Tests for error scenarios
- [x] >80% coverage

### Documentation
- [x] OAuth flow explained in module docstring
- [x] Token refresh algorithm documented
- [x] Error handling documented
- [x] Examples in docstrings

### Security
- [x] No hardcoded credentials
- [x] Tokens encrypted (via Database Module)
- [x] Error messages don't leak secrets
- [x] Input validation on all public methods
```

---

## 4. Common Migration Patterns

### 4.1 Database Access Migration

**Pattern: Replace Direct SQLAlchemy with Database Module**

```python
# ❌ OLD: Direct SQLAlchemy
from sqlalchemy.orm import Session
from soulspot.models import Track

def get_track(track_id: str) -> Track | None:
    session = Session()
    return session.query(Track).filter_by(id=track_id).first()

# ✅ NEW: Database Module
async def get_track(track_id: str) -> dict | None:
    """
    Get track by ID.
    
    Args:
        track_id: Unique track identifier
        
    Returns:
        Track data dict or None if not found
        
    Examples:
        >>> track = await get_track("spotify:track:123")
        >>> print(track["title"])
        "Let It Be"
    """
    return await db_service.get("track", track_id)
```

### 4.2 Configuration Migration

**Pattern: Replace .env with Onboarding + Database Module**

```python
# ❌ OLD: Environment variables
import os
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# ✅ NEW: Database Module configuration
async def get_spotify_credentials() -> dict:
    """
    Get Spotify API credentials from secure storage.
    
    Credentials are stored encrypted via onboarding wizard.
    Retrieved from Database Module on demand.
    
    Returns:
        Dict with client_id and client_secret (decrypted)
        
    Raises:
        ConfigurationError: If credentials not configured
    """
    config = await db_service.get("config", "spotify_credentials")
    
    if not config:
        raise ConfigurationError(
            code="SPOTIFY_NOT_CONFIGURED",
            message="Spotify credentials not set",
            resolution="Run onboarding wizard: http://localhost:8765/onboarding",
            docs_url="https://docs.soulspot.app/setup/spotify"
        )
    
    return config  # Database Module decrypts automatically
```

### 4.3 Error Handling Migration

**Pattern: Structured Errors with Context**

```python
# ❌ OLD: Generic exceptions
def search_track(query: str):
    if not query:
        raise ValueError("Query cannot be empty")
    
    response = requests.get(f"{SPOTIFY_API}/search?q={query}")
    if response.status_code != 200:
        raise Exception(f"Spotify API error: {response.status_code}")

# ✅ NEW: Structured errors with actionable resolution
async def search_track(query: str) -> list[dict]:
    """
    Search for tracks on Spotify.
    
    Args:
        query: Search query (artist, title, album, etc.)
        
    Returns:
        List of track dicts with metadata
        
    Raises:
        ValidationError: If query is invalid
        SpotifyAPIError: If Spotify API call fails
        
    Examples:
        >>> tracks = await search_track("Beatles Let It Be")
        >>> print(tracks[0]["title"])
        "Let It Be"
    """
    # Validate input
    if not query or not query.strip():
        raise ValidationError(
            code="SPOTIFY_EMPTY_QUERY",
            message="Search query cannot be empty",
            resolution="Enter at least 1 character to search",
            context={"query": query},
            docs_url="https://docs.soulspot.app/spotify/search"
        )
    
    try:
        response = await httpx_client.get(
            f"{SPOTIFY_API}/search",
            params={"q": query, "type": "track"}
        )
        response.raise_for_status()
        
    except httpx.HTTPStatusError as e:
        raise SpotifyAPIError(
            code="SPOTIFY_API_ERROR",
            message=f"Spotify API returned {e.response.status_code}",
            resolution=(
                "1. Check Spotify API status: https://status.spotify.com\n"
                "2. Verify credentials in Settings → Spotify\n"
                "3. Check rate limits\n"
                "4. Review logs for details"
            ),
            context={
                "query": query,
                "status_code": e.response.status_code,
                "response": e.response.text[:200]
            },
            docs_url="https://docs.soulspot.app/troubleshooting/spotify-errors"
        )
    
    return response.json()["tracks"]["items"]
```

---

## 5. Anti-Patterns to Avoid

### 5.1 ❌ Blind Copy-Paste

**DON'T:**
```python
# Just copying old code without understanding or validation
# This brings forward all bugs and technical debt!
```

**DO:**
```python
# 1. Understand the code
# 2. Validate against quality checklist
# 3. Refactor to meet new standards
# 4. Add comprehensive documentation
# 5. Test thoroughly
```

### 5.2 ❌ Keeping Dead Code

**DON'T:**
```python
# Old code commented out "just in case"
# def old_broken_function():
#     # This never worked properly
#     pass

def new_function():
    pass
```

**DO:**
```python
# Remove old code completely
# Git history preserves it if needed
# Only keep what's actively used and tested

def new_function():
    """
    New implementation that actually works.
    
    Replaced old_broken_function which had issues with...
    See Git history (commit abc123) for old implementation.
    """
    pass
```

### 5.3 ❌ Partial Migration

**DON'T:**
```python
# Half using Database Module, half using direct SQLAlchemy
async def save_track(track: dict):
    # New way
    await db_service.save("track", track)
    
    # Old way mixed in - CONFUSING!
    session = Session()
    album = session.query(Album).first()  # Direct DB access
```

**DO:**
```python
# Consistent use of Database Module throughout
async def save_track(track: dict):
    """Save track via Database Module."""
    await db_service.save("track", track)
    
async def get_album(album_id: str):
    """Get album via Database Module."""
    return await db_service.get("album", album_id)
```

---

## 6. Implementation Priority

### 6.1 Phase 1: Core Infrastructure (Weeks 1-2)

**Migrate FIRST (foundation for everything):**

1. **Database Module** (new implementation, minimal migration)
2. **Event Bus** (can reuse message queue logic)
3. **Module Registry** (new implementation)
4. **Module Router** (new implementation)

### 6.2 Phase 2: Pilot Modules (Weeks 3-6)

**Migrate with HIGH scrutiny:**

1. **Soulseek Module**
   - Reuse: slskd client communication logic
   - Reuse: Search result parsing
   - Reuse: Download state machine (with refactor)
   - Refactor: All database access → Database Module
   - Add: Comprehensive error handling
   - Add: Module documentation

2. **Spotify Module**
   - Reuse: OAuth flow logic (with refactor)
   - Reuse: API request/response handling
   - Reuse: Playlist parsing
   - Refactor: All database access → Database Module
   - Refactor: Configuration → Onboarding + Database Module
   - Add: Submodule structure
   - Add: Comprehensive error handling

### 6.3 Phase 3: Supporting Modules (Weeks 7-10)

**Migrate with MEDIUM scrutiny:**

1. **Metadata Module**
   - Reuse: MusicBrainz API client
   - Reuse: CoverArtArchive integration
   - Refactor: Database access
   - Add: Event subscriptions

2. **Library Module**
   - Reuse: File organization logic
   - Reuse: Playlist export
   - Refactor: Database access
   - Add: Import/export features

### 6.4 Phase 4: Optional Modules (Weeks 11-12)

**Migrate selectively:**

1. **Notifications Module** (if exists in v2)
2. **Admin Module** (may not need)
3. **Analytics Module** (may not need)

---

## 7. Quality Gates

### 7.1 Before Merging Any Migrated Code

**Mandatory Checks:**

```bash
# 1. Code Quality
ruff check . --config pyproject.toml
mypy --config-file mypy.ini .

# 2. Security
bandit -r . -f json -o /tmp/bandit-report.json

# 3. Tests
pytest tests/ --cov --cov-report=html

# 4. Documentation
# Manual: Verify all functions have docstrings
# Manual: Verify CHANGELOG.md updated
# Manual: Verify module docs/ updated
```

**Acceptance Criteria:**

- [ ] All linters pass (ruff, mypy)
- [ ] No security issues (bandit)
- [ ] Test coverage ≥80%
- [ ] All tests pass
- [ ] Documentation complete
- [ ] Code review approved
- [ ] Migration checklist completed

---

## 8. Example: Full Migration

### 8.1 Migrating Spotify Track Search

**Original Code (Version 2.x):**

```python
# src/soulspot/integrations/spotify.py

import os
import requests
from sqlalchemy.orm import Session
from soulspot.models import Track

SPOTIFY_API = "https://api.spotify.com/v1"
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

def search_tracks(query):
    # Get token from DB
    session = Session()
    token_row = session.query(Config).filter_by(key="spotify_token").first()
    token = json.loads(token_row.value)["access_token"]
    
    # Call API
    response = requests.get(
        f"{SPOTIFY_API}/search",
        params={"q": query, "type": "track"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        raise Exception(f"Error: {response.status_code}")
    
    # Save results to DB
    for item in response.json()["tracks"]["items"]:
        track = Track(
            id=item["id"],
            title=item["name"],
            artist=item["artists"][0]["name"]
        )
        session.add(track)
    session.commit()
    
    return response.json()["tracks"]["items"]
```

**Migrated Code (Version 3.0):**

```python
# modules/spotify/submodules/search/backend/application/services/search_service.py

"""
Spotify Track Search Service

Handles track search via Spotify Web API with automatic token management,
caching, and event publishing.

**Architecture:**
- Uses Database Module for token retrieval and result caching
- Publishes 'spotify.search.completed' event for subscribers
- Integrates with Module Router for cross-module search

**Token Management:**
- Retrieves encrypted access token via Database Module
- Automatically refreshes expired tokens (transparent)
- Falls back to credential flow if refresh fails

**Caching Strategy:**
- Search results cached for 5 minutes (reduce API calls)
- Cache key: search_query hash + user_market
- Invalidated on: User preference changes, API errors

**Error Handling:**
- Empty query → ValidationError with user-friendly message
- Network error → Retry with exponential backoff (3 attempts)
- Token expired → Auto-refresh and retry original request
- Rate limit → Wait and retry with structured error

**Related Docs:**
- API documentation: docs/api.md
- Event schemas: docs/events.md
- Error codes: ../../ERROR_MESSAGING.md
"""

from typing import Protocol
from datetime import datetime, timedelta
import httpx

from core.database import DatabaseService
from core.events import EventBus
from core.errors import ValidationError, SpotifyAPIError

# Constants - Magic numbers explained
SEARCH_CACHE_TTL = 300  # 5 minutes in seconds (balance freshness vs API calls)
MAX_RESULTS = 50  # Spotify API max per page
RETRY_ATTEMPTS = 3  # Network retry attempts (balance latency vs reliability)
RETRY_BACKOFF = 2  # Exponential backoff multiplier

class SearchService:
    """
    Spotify track search service.
    
    Hey future me – This service handles all Spotify search operations.
    Key complexity is token management (automatic refresh) and caching
    (reduces API calls but must stay fresh). Error handling is critical
    because search is user-facing and errors must be actionable.
    
    Args:
        db_service: Database Module for token + caching
        event_bus: Event Bus for publishing search events
        http_client: HTTP client for Spotify API (injected for testing)
    """
    
    def __init__(
        self,
        db_service: DatabaseService,
        event_bus: EventBus,
        http_client: httpx.AsyncClient | None = None
    ):
        self.db = db_service
        self.events = event_bus
        self.http = http_client or httpx.AsyncClient(timeout=10.0)
        
    async def search_tracks(
        self,
        query: str,
        limit: int = 20
    ) -> list[dict]:
        """
        Search for tracks on Spotify.
        
        Results are cached for 5 minutes to reduce API calls. Token is
        automatically refreshed if expired (transparent to caller).
        
        Args:
            query: Search query (artist, title, album, keywords, etc.)
            limit: Max results to return (1-50, default 20)
            
        Returns:
            List of track dicts with:
                - id: Spotify track ID
                - title: Track name
                - artist: Primary artist name
                - album: Album name
                - duration_ms: Track length in milliseconds
                - spotify_url: External Spotify URL
                
        Raises:
            ValidationError: If query is empty or limit invalid
            SpotifyAPIError: If Spotify API call fails
            
        Examples:
            >>> results = await search_service.search_tracks("Beatles Let It Be")
            >>> print(results[0]["title"])
            "Let It Be - Remastered 2009"
            
            >>> # With custom limit
            >>> results = await search_service.search_tracks("Queen", limit=10)
            
        Notes:
            - Results cached for 5 minutes
            - Token auto-refreshed if expired
            - Retries 3 times on network error
            - Rate limiting handled automatically
        """
        # Validate input
        if not query or not query.strip():
            raise ValidationError(
                code="SPOTIFY_EMPTY_QUERY",
                message="Search query cannot be empty",
                resolution="Enter at least 1 character to search",
                context={"query": query},
                docs_url="https://docs.soulspot.app/spotify/search#errors"
            )
        
        if not (1 <= limit <= MAX_RESULTS):
            raise ValidationError(
                code="SPOTIFY_INVALID_LIMIT",
                message=f"Limit must be between 1 and {MAX_RESULTS}",
                resolution=f"Set limit to value between 1 and {MAX_RESULTS}",
                context={"limit": limit, "max": MAX_RESULTS},
                docs_url="https://docs.soulspot.app/spotify/search#limits"
            )
        
        # Check cache first (reduces API calls)
        cache_key = f"spotify:search:{hash(query)}:{limit}"
        cached = await self.db.get("search_cache", cache_key)
        
        if cached and not self._is_cache_expired(cached):
            return cached["results"]
        
        # Get access token via Database Module
        token = await self._get_access_token()
        
        # Call Spotify API with retry
        results = await self._call_spotify_search(query, limit, token)
        
        # Cache results
        await self.db.save(
            entity_type="search_cache",
            entity_data={
                "id": cache_key,
                "results": results,
                "cached_at": datetime.utcnow().isoformat(),
                "ttl": SEARCH_CACHE_TTL
            }
        )
        
        # Publish event (other modules can subscribe)
        await self.events.publish(
            "spotify.search.completed",
            {
                "query": query,
                "result_count": len(results),
                "cached": False
            }
        )
        
        return results
    
    async def _get_access_token(self) -> str:
        """
        Get valid access token from Database Module.
        
        Hey future me – Token is stored encrypted via Database Module.
        If expired, this automatically refreshes it (using refresh_token)
        and updates storage. Caller doesn't need to know about expiry.
        
        Returns:
            Valid access token (decrypted)
            
        Raises:
            ConfigurationError: If Spotify not configured
            SpotifyAPIError: If token refresh fails
        """
        token_data = await self.db.get("config", "spotify_token")
        
        if not token_data:
            raise ConfigurationError(
                code="SPOTIFY_NOT_CONFIGURED",
                message="Spotify credentials not configured",
                resolution=(
                    "1. Go to Settings → Spotify\n"
                    "2. Enter Client ID and Client Secret\n"
                    "3. Click 'Test Connection'\n"
                    "4. Save configuration"
                ),
                context={},
                docs_url="https://docs.soulspot.app/setup/spotify"
            )
        
        # Check if token expired
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        if datetime.utcnow() >= expires_at:
            # Auto-refresh token
            token_data = await self._refresh_token(token_data["refresh_token"])
            
            # Update stored token
            await self.db.update(
                entity_type="config",
                entity_id="spotify_token",
                updates=token_data
            )
        
        return token_data["access_token"]
    
    async def _call_spotify_search(
        self,
        query: str,
        limit: int,
        token: str
    ) -> list[dict]:
        """
        Call Spotify Web API search endpoint with retry.
        
        Hey future me – Network errors happen. We retry up to 3 times
        with exponential backoff. Rate limiting is handled by waiting
        the time Spotify tells us (Retry-After header).
        
        Args:
            query: Search query
            limit: Max results
            token: Valid access token
            
        Returns:
            List of track dicts
            
        Raises:
            SpotifyAPIError: If all retries fail or non-retryable error
        """
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = await self.http.get(
                    "https://api.spotify.com/v1/search",
                    params={"q": query, "type": "track", "limit": limit},
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                response.raise_for_status()
                
                # Parse and return results
                data = response.json()
                return [
                    {
                        "id": item["id"],
                        "title": item["name"],
                        "artist": item["artists"][0]["name"],
                        "album": item["album"]["name"],
                        "duration_ms": item["duration_ms"],
                        "spotify_url": item["external_urls"]["spotify"]
                    }
                    for item in data["tracks"]["items"]
                ]
                
            except httpx.HTTPStatusError as e:
                # Handle rate limiting (wait and retry)
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", 5))
                    
                    if attempt < RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(retry_after)
                        continue  # Retry
                
                # Non-retryable error or final attempt
                raise SpotifyAPIError(
                    code=f"SPOTIFY_API_{e.response.status_code}",
                    message=f"Spotify API returned {e.response.status_code}",
                    resolution=(
                        "1. Check Spotify API status: https://status.spotify.com\n"
                        "2. Verify credentials in Settings → Spotify\n"
                        "3. Wait a few minutes if rate limited\n"
                        "4. Review logs for details"
                    ),
                    context={
                        "query": query,
                        "status_code": e.response.status_code,
                        "attempt": attempt + 1,
                        "response_preview": e.response.text[:200]
                    },
                    docs_url="https://docs.soulspot.app/troubleshooting/spotify-errors"
                )
                
            except httpx.NetworkError as e:
                # Retry on network errors
                if attempt < RETRY_ATTEMPTS - 1:
                    wait_time = (RETRY_BACKOFF ** attempt)  # Exponential backoff
                    await asyncio.sleep(wait_time)
                    continue
                
                # All retries failed
                raise SpotifyAPIError(
                    code="SPOTIFY_NETWORK_ERROR",
                    message="Network error while contacting Spotify API",
                    resolution=(
                        "1. Check internet connection\n"
                        "2. Verify firewall settings\n"
                        "3. Try again in a few minutes\n"
                        "4. Check system logs for network issues"
                    ),
                    context={
                        "query": query,
                        "attempts": RETRY_ATTEMPTS,
                        "error": str(e)
                    },
                    docs_url="https://docs.soulspot.app/troubleshooting/network-errors"
                )
    
    def _is_cache_expired(self, cached: dict) -> bool:
        """
        Check if cached search result is expired.
        
        Args:
            cached: Cached entry with cached_at and ttl
            
        Returns:
            True if expired, False if still fresh
        """
        cached_at = datetime.fromisoformat(cached["cached_at"])
        ttl = cached.get("ttl", SEARCH_CACHE_TTL)
        
        return datetime.utcnow() > (cached_at + timedelta(seconds=ttl))
```

**Migration Summary:**

✅ **Improvements:**
- Database Module for all data access (no direct SQLAlchemy)
- Comprehensive docstrings with examples
- "Future-self" comments for complex parts
- Structured error handling with actionable messages
- Caching strategy to reduce API calls
- Automatic token refresh (transparent)
- Retry logic with exponential backoff
- Event publishing for module integration
- Constants explained (no magic numbers)
- Type hints on all functions
- Testable (dependency injection)

✅ **Quality Checklist:**
- [x] Architecture compliant
- [x] Comprehensive documentation
- [x] Structured error handling
- [x] No magic numbers
- [x] No dead code
- [x] Type hints
- [x] Testable design

---

## 9. Documentation Requirements

### 9.1 Migration Documentation in Module

**Every migrated module MUST document:**

```markdown
# modules/spotify/MIGRATION_NOTES.md

## Migration from Version 2.x

### What Was Reused

**OAuth Flow Logic** (75% reused)
- Source: src/soulspot/integrations/spotify.py:SpotifyAuth
- Reused: Authorization code exchange, PKCE implementation
- Refactored: Token storage (Database Module), error handling
- Reason: OAuth logic was well-tested and correct

**API Client** (50% reused)
- Source: src/soulspot/integrations/spotify.py:SpotifyClient
- Reused: Request/response parsing, retry logic
- Refactored: Configuration, error handling, documentation
- Reason: Core API logic was solid but needed better errors

### What Was Rewritten

**Database Access** (100% rewritten)
- Old: Direct SQLAlchemy queries
- New: Database Module API
- Reason: Version 3.0 architecture requirement

**Configuration** (100% rewritten)
- Old: Environment variables (.env)
- New: Onboarding wizard + Database Module
- Reason: Better UX, encrypted storage

### Known Issues Migrated

None - All known bugs from Version 2.x were fixed during migration.

### Testing Notes

- All old tests adapted to use Database Module mocks
- Added tests for new error handling
- Coverage increased from 65% to 85%
```

---

## 10. Summary

**Key Principles:**

1. ✅ **Review Before Reuse**: Understand code before migrating
2. ✅ **Quality Checklist**: Every migration passes checklist
3. ✅ **Refactor to Standards**: Meet Version 3.0 requirements
4. ✅ **Document Changes**: Explain what and why
5. ✅ **Test Thoroughly**: Maintain or improve coverage
6. ✅ **Remove Dead Code**: No baggage from Version 2.x
7. ✅ **Validate Continuously**: Lint, type-check, security scan

**DO:**
- Reuse proven business logic
- Refactor to new architecture
- Add comprehensive documentation
- Improve error handling
- Increase test coverage

**DON'T:**
- Blindly copy-paste
- Keep dead code
- Ignore quality checklist
- Skip documentation
- Bypass Database Module

---

**This document ensures Version 3.0 builds on Version 2.x strengths while eliminating technical debt and architectural limitations.**
