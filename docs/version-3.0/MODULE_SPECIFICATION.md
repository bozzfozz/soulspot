# SoulSpot Bridge - Module Specification Template (Version 3.0)

**Version:** 3.0.0  
**Status:** Planning Phase  
**Last Updated:** 2025-11-21

---

## 1. Introduction

This document defines the **standard structure and requirements** for all feature modules in SoulSpot Bridge Version 3.0. Every new module MUST follow this specification to ensure consistency, maintainability, and interoperability.

### 1.1 Purpose

- Provide a clear template for creating new modules
- Ensure consistency across all modules
- Define minimum requirements for module quality
- Standardize module interfaces and contracts

### 1.2 Scope

This specification applies to:
- All new feature modules
- Migrated modules from Version 2.x
- Core modules (with some exceptions noted)
- Third-party modules (future)

---

## 2. Module Metadata

Every module MUST define its metadata in `__init__.py`:

```python
# modules/{module_name}/__init__.py

"""
{Module Name} Module

{Brief description of module purpose and features}
"""

from .backend.api.routes import router
from .backend.config.settings import {ModuleName}Settings

__version__ = "1.0.0"
__author__ = "{Author Name}"
__description__ = "{Module description}"

class Module:
    """Standard module interface."""
    
    # Module identification
    name: str = "{module_name}"
    version: str = __version__
    description: str = __description__
    
    # Module components
    router: APIRouter = router
    settings: {ModuleName}Settings = {ModuleName}Settings()
    
    # Module capabilities
    provides_api: bool = True
    provides_ui: bool = True
    provides_events: bool = True
    
    # Module dependencies
    depends_on: list[str] = ["core"]  # List of required modules
    optional_deps: list[str] = []     # List of optional modules
    
    @staticmethod
    def health_check() -> dict:
        """
        Module health check.
        
        Returns:
            dict: Health status with details
        """
        return {
            "status": "healthy",
            "module": "{module_name}",
            "version": __version__,
        }
    
    @staticmethod
    def get_info() -> dict:
        """
        Get module information.
        
        Returns:
            dict: Module metadata and capabilities
        """
        return {
            "name": "{module_name}",
            "version": __version__,
            "description": __description__,
            "endpoints": router.routes,
            "events": {
                "publishes": ["event.name1", "event.name2"],
                "subscribes": ["event.name3", "event.name4"],
            },
            "dependencies": {
                "required": ["core"],
                "optional": [],
            },
        }

__all__ = ["Module"]
```

---

## 3. Directory Structure

### 3.1 Required Structure

```
modules/{module_name}/
├── README.md                   # ✅ REQUIRED - Module overview & getting started
├── CHANGELOG.md                # ✅ REQUIRED - Module version history
├── __init__.py                 # ✅ REQUIRED - Module interface & metadata
│
├── docs/                       # ✅ REQUIRED - Module documentation
│   ├── architecture.md         # Module architecture & design decisions
│   ├── api.md                  # API documentation
│   ├── events.md               # Event schemas & contracts
│   ├── configuration.md        # Configuration guide
│   └── development.md          # Development & contribution guide
│
├── frontend/                   # ✅ REQUIRED (if provides_ui)
│   ├── __init__.py
│   ├── pages/                  # Full page templates
│   ├── widgets/                # Reusable UI components
│   ├── partials/               # Template fragments
│   ├── styles/                 # CSS files
│   └── scripts/                # JavaScript files
│
├── backend/                    # ✅ REQUIRED
│   ├── __init__.py
│   ├── api/                    # ✅ REQUIRED
│   │   ├── __init__.py
│   │   ├── routes.py           # FastAPI router
│   │   ├── schemas.py          # Pydantic schemas
│   │   └── dependencies.py     # Route dependencies
│   │
│   ├── application/            # ✅ REQUIRED
│   │   ├── __init__.py
│   │   ├── services/           # Application services
│   │   ├── use_cases/          # Command/Query handlers
│   │   └── dto/                # Data Transfer Objects
│   │
│   ├── domain/                 # ✅ REQUIRED
│   │   ├── __init__.py
│   │   ├── entities/           # Domain entities
│   │   ├── value_objects/      # Value objects
│   │   ├── services/           # Domain services
│   │   ├── events/             # Domain events
│   │   ├── ports/              # Interface definitions
│   │   └── exceptions/         # Domain exceptions
│   │
│   ├── infrastructure/         # ✅ REQUIRED
│   │   ├── __init__.py
│   │   ├── persistence/        # Database models & repos
│   │   ├── integrations/       # External API clients
│   │   └── adapters/           # Port implementations
│   │
│   └── config/                 # ✅ REQUIRED
│       ├── __init__.py
│       └── settings.py         # Module settings
│
├── tests/                      # ✅ REQUIRED
│   ├── __init__.py
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── fixtures/               # Test fixtures
│
└── contracts/                  # ⚠️ RECOMMENDED (future)
    ├── api.yaml                # OpenAPI specification
    ├── events.yaml             # Event schemas
    └── dependencies.yaml       # Module dependencies
```

### 3.2 File Naming Conventions

**Python Files:**
- Use lowercase with underscores: `download_service.py`
- One class per file (generally): `download.py` contains `Download` class
- Group related classes: `exceptions.py` can contain multiple exception classes

**Template Files:**
- Use lowercase with underscores: `download_queue.html`
- Descriptive names: `download_status_card.html` not `status.html`

**Test Files:**
- Prefix with `test_`: `test_download_service.py`
- Mirror source structure: `services/download_service.py` → `tests/unit/test_download_service.py`

### 3.2.1 Module Documentation Requirements

**CHANGELOG.md (Required):**

Each module and submodule MUST have its own `CHANGELOG.md` in addition to the global changelog at the repository root.

**Purpose:**
- Track module-specific version history
- Document breaking changes within the module
- Provide module-level migration guides
- Enable independent module versioning

**Format (Keep a Changelog):**

```markdown
# Changelog - {Module Name}

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this module adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New feature X

### Changed
- Updated Y

## [1.2.0] - 2025-11-20

### Added
- Implemented download queue management
- Added retry mechanism for failed downloads

### Fixed
- Fixed race condition in concurrent downloads
- Corrected metadata encoding issue

### Security
- Updated slskd client to address CVE-2025-XXXX

## [1.1.0] - 2025-10-15

### Changed
- Improved search algorithm performance
- Enhanced error messages

## [1.0.0] - 2025-09-01

### Added
- Initial release
- Basic download functionality
- Search integration
```

**Submodule Changelog Example:**

```markdown
# Changelog - Spotify Auth Submodule

## [1.1.0] - 2025-11-15

### Added
- Token refresh retry logic with exponential backoff
- Support for PKCE flow

### Changed
- Token storage now uses encrypted database instead of plaintext

### Deprecated
- Legacy token storage format (will be removed in 2.0.0)
```

**docs/ Directory (Required):**

Each module and submodule MUST have a `docs/` directory containing detailed documentation.

**Minimum Required Files:**

1. **architecture.md** - Module architecture, design decisions, patterns used
2. **api.md** - Complete API documentation (endpoints, parameters, responses)
3. **events.md** - Event schemas, when they're published, what subscribes to them
4. **configuration.md** - Configuration options, environment variables, settings
5. **development.md** - How to develop, test, and contribute to the module

**Example: modules/soulseek/docs/architecture.md**

```markdown
# Soulseek Module Architecture

## Overview
This module handles all Soulseek/slskd integration for downloading music files.

## Design Decisions

### Why separate Download entity from SearchResult?
We initially considered combining these, but separated them because:
- Search results are ephemeral (cached short-term)
- Downloads persist long-term and have complex state transitions
- Different lifecycle and storage needs

### Circuit Breaker Pattern
We use circuit breaker for slskd API calls because:
- slskd can become temporarily unresponsive
- Prevents cascading failures
- Allows graceful degradation

## Component Diagram
[Diagram showing Download flow]

## State Transitions
[State machine diagram for Download entity]
```

**Example: modules/spotify/submodules/auth/docs/oauth-flow.md**

```markdown
# Spotify OAuth Flow

## Authorization Code Flow

1. User clicks "Connect Spotify"
2. Redirect to Spotify authorization URL
3. User approves
4. Spotify redirects back with code
5. Exchange code for tokens
6. Store encrypted tokens
7. Set refresh timer

## Token Refresh

Tokens refresh automatically 5 minutes before expiry.
If refresh fails, user is prompted to re-authenticate.

## Security Considerations

- Tokens stored encrypted in database
- State parameter prevents CSRF
- PKCE used for additional security
```

**Documentation Location Rules:**

```
✅ Correct:
modules/soulseek/docs/architecture.md        # Module docs in module
modules/spotify/docs/api.md                  # Module docs in module
modules/spotify/submodules/auth/docs/oauth-flow.md  # Submodule docs in submodule

❌ Wrong:
docs/modules/soulseek/architecture.md        # Don't put in global docs/
docs/spotify-api.md                          # Don't mix with global docs
modules/soulseek/architecture.md             # Must be in docs/ subdirectory
```

**Global vs. Module Documentation:**

- **Global docs/** (repository root): System architecture, cross-module patterns, deployment guides
- **Module docs/**: Module-specific implementation, APIs, configuration
- **Submodule docs/**: Submodule-specific details

**Why This Matters:**

1. **Modularity**: Each module is self-documenting and self-contained
2. **Versioning**: Module docs version with the module code
3. **Discovery**: Developers find docs next to the code they're reading
4. **Independence**: Modules can be extracted or reused with docs intact
5. **Clarity**: Clear separation between system-level and module-level concerns

### 3.3 Submodules Support

**Overview:**  
Modules can contain submodules for better organization and separation of concerns. Submodules are self-contained units within a parent module that handle specific functionality.

**Use Cases:**
- **Authentication Submodule**: Handle OAuth, token management separately from main module logic
- **Storage Submodule**: Manage file storage, caching independently
- **Webhook Submodule**: Handle external webhooks in isolation
- **Admin Submodule**: Separate admin functionality from user-facing features

**Example: Spotify Module with Authentication Submodule**

```
modules/spotify/
├── README.md                       # ✅ Parent module overview
├── CHANGELOG.md                    # ✅ Parent module changelog
├── __init__.py                     # Parent module exports
│
├── docs/                           # ✅ Parent module documentation
│   ├── architecture.md
│   ├── api.md
│   └── configuration.md
│
├── submodules/                     # ✅ Submodules directory
│   │
│   ├── auth/                       # Authentication submodule
│   │   ├── README.md               # ✅ Submodule overview
│   │   ├── CHANGELOG.md            # ✅ Submodule changelog
│   │   ├── __init__.py
│   │   │
│   │   ├── docs/                   # ✅ Submodule documentation
│   │   │   ├── oauth-flow.md
│   │   │   └── token-management.md
│   │   │
│   │   ├── backend/
│   │   │   ├── api/
│   │   │   │   ├── routes.py      # /spotify/auth/* routes
│   │   │   │   └── schemas.py
│   │   │   ├── application/
│   │   │   │   └── services/
│   │   │   │       └── token_service.py
│   │   │   ├── domain/
│   │   │   │   └── entities/
│   │   │   │       └── oauth_token.py
│   │   │   └── infrastructure/
│   │   │       └── persistence/
│   │   │           └── token_repository.py
│   │   ├── frontend/
│   │   │   └── pages/
│   │   │       └── auth_callback.html
│   │   └── tests/
│   │
│   └── webhooks/                   # Webhooks submodule (example)
│       ├── README.md               # ✅ Submodule overview
│       ├── CHANGELOG.md            # ✅ Submodule changelog
│       ├── __init__.py
│       ├── docs/                   # ✅ Submodule documentation
│       │   └── webhook-handlers.md
│       └── backend/
│           └── api/
│               └── routes.py       # /spotify/webhooks/* routes
│
├── frontend/                       # Parent module UI
│   ├── pages/
│   │   └── playlist_sync.html
│   └── widgets/
│       └── playlist_widget.html
│
├── backend/                        # Parent module backend
│   ├── api/
│   │   ├── routes.py               # Main Spotify routes
│   │   └── schemas.py
│   ├── application/
│   │   └── services/
│   │       └── playlist_service.py # Uses auth submodule
│   ├── domain/
│   │   └── entities/
│   │       └── playlist.py
│   └── infrastructure/
│       └── integrations/
│           └── spotify_client.py   # Uses auth submodule for tokens
│
└── tests/
    └── integration/
        └── test_playlist_with_auth.py  # Test parent + submodule
```

**Submodule Registration and Discovery:**

```python
# modules/spotify/__init__.py

"""
Spotify Module with Authentication Submodule.

This module handles Spotify integration including playlist sync,
track search, and user authentication.
"""

from .backend.api.routes import router as main_router
from .submodules.auth import router as auth_router, AuthSubmodule
from .backend.config.settings import SpotifySettings

__version__ = "1.0.0"
__description__ = "Spotify integration with OAuth authentication"

class SpotifyModule:
    """Spotify module with authentication submodule."""
    
    name: str = "spotify"
    version: str = __version__
    
    # Submodules
    submodules: dict = {
        "auth": AuthSubmodule,  # Authentication submodule
    }
    
    # Combined routers
    @staticmethod
    def get_router():
        """Get combined router with all submodule routes."""
        from fastapi import APIRouter
        
        router = APIRouter(prefix="/spotify")
        
        # Include main module routes
        router.include_router(main_router, tags=["spotify"])
        
        # Include submodule routes
        router.include_router(
            auth_router,
            prefix="/auth",
            tags=["spotify-auth"]
        )
        
        return router
    
    @staticmethod
    def health_check() -> dict:
        """Check health of module and all submodules."""
        return {
            "module": "spotify",
            "status": "healthy",
            "submodules": {
                "auth": AuthSubmodule.health_check(),
            }
        }

# Export for easy import
module = SpotifyModule()
router = module.get_router()
```

**Authentication Submodule Definition:**

```python
# modules/spotify/submodules/auth/__init__.py

"""
Spotify Authentication Submodule.

Handles OAuth flow, token management, and token refresh.
Isolated from main Spotify module for better separation of concerns.

Hey future me, this is a SUBMODULE. It's part of Spotify module but
self-contained. It handles ONLY authentication - getting tokens,
refreshing them, storing them. The parent Spotify module uses this
for making API calls.
"""

from fastapi import APIRouter
from .backend.api.routes import router as auth_routes
from .backend.application.services.token_service import TokenService

router = auth_routes

class AuthSubmodule:
    """Authentication submodule for Spotify."""
    
    name: str = "spotify.auth"
    parent: str = "spotify"
    version: str = "1.0.0"
    
    # Services exposed to parent module
    token_service: TokenService = TokenService()
    
    @staticmethod
    def health_check() -> dict:
        """Health check for auth submodule."""
        return {
            "submodule": "spotify.auth",
            "status": "healthy",
            "has_valid_token": TokenService().has_valid_token(),
        }
    
    @staticmethod
    def get_capabilities() -> list[str]:
        """Capabilities provided by this submodule."""
        return [
            "oauth.authorize",
            "oauth.callback",
            "oauth.refresh_token",
            "oauth.validate_token",
        ]

# Export
submodule = AuthSubmodule()
```

**Parent Module Using Submodule:**

```python
# modules/spotify/backend/infrastructure/integrations/spotify_client.py

"""
Spotify API client.

Uses the auth submodule for token management.
"""

from ....submodules.auth import submodule as auth_submodule
import httpx

class SpotifyClient:
    """
    Spotify API client.
    
    Hey future me, this client uses the AUTH SUBMODULE to get tokens.
    It doesn't handle auth itself - that's delegated to the submodule.
    Clean separation!
    """
    
    def __init__(self):
        self.base_url = "https://api.spotify.com/v1"
        self.token_service = auth_submodule.token_service
    
    async def get_playlists(self, user_id: str) -> list[dict]:
        """Get user playlists using token from auth submodule."""
        
        # Get token from auth submodule
        token = await self.token_service.get_valid_token()
        
        # Make API call
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/users/{user_id}/playlists",
                headers={"Authorization": f"Bearer {token}"}
            )
            return response.json()
```

**Router Integration:**

```python
# modules/spotify/submodules/auth/backend/api/routes.py

"""
Authentication routes for Spotify OAuth.

These routes are mounted at /spotify/auth/* by the parent module.
"""

from fastapi import APIRouter, Request, HTTPException
from ..application.services.token_service import TokenService

router = APIRouter()
token_service = TokenService()

@router.get("/authorize")
async def authorize():
    """
    Initiate OAuth flow.
    
    Route: GET /spotify/auth/authorize
    """
    auth_url = await token_service.get_authorization_url()
    return {"authorization_url": auth_url}

@router.get("/callback")
async def callback(code: str, state: str):
    """
    OAuth callback handler.
    
    Route: GET /spotify/auth/callback?code=...&state=...
    """
    try:
        token = await token_service.exchange_code_for_token(code, state)
        return {"status": "success", "message": "Authentication successful"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refresh")
async def refresh_token():
    """
    Refresh access token.
    
    Route: POST /spotify/auth/refresh
    """
    token = await token_service.refresh_access_token()
    return {"status": "success", "expires_in": token.expires_in}
```

**Benefits of Submodules:**

✅ **Separation of Concerns**: Auth logic isolated from main module  
✅ **Reusability**: Submodules can be reused across modules  
✅ **Independent Testing**: Test submodule in isolation  
✅ **Clear Boundaries**: Each submodule has well-defined responsibility  
✅ **Easier Maintenance**: Changes to auth don't affect playlist logic  
✅ **Optional Features**: Submodules can be disabled if not needed  

**Module Router Integration:**

```python
# Submodules register their capabilities with the router

# In auth submodule initialization:
module_router.register_capability(
    operation="oauth.get_token",
    module_name="spotify.auth",  # Submodule name
    priority=10,
)

# Other modules can use auth submodule:
token = await module_router.route_request(
    operation="oauth.get_token",
    params={"service": "spotify"}
)
```

**Submodule Communication:**

Submodules can communicate with:
1. **Parent Module**: Direct import and method calls
2. **Other Submodules**: Via parent module or event bus
3. **External Modules**: Via module router or events

```python
# Parent → Submodule (direct)
from .submodules.auth import token_service
token = await token_service.get_token()

# Submodule → Parent (via events)
await event_bus.publish("spotify.auth.token_refreshed", {...})

# Submodule → Other Module (via router)
await module_router.route_request("notify.user", {...})
```

---

## 4. Backend Structure

### 4.1 API Layer (routes.py)

**Purpose:** HTTP endpoint definitions and request/response handling

**Required Elements:**
```python
# modules/{module_name}/backend/api/routes.py

from fastapi import APIRouter, Depends, HTTPException, Request
from .schemas import (
    {Entity}CreateRequest,
    {Entity}UpdateRequest,
    {Entity}Response,
    {Entity}ListResponse,
)
from ..application.services import {Entity}Service

# Router with module prefix
router = APIRouter(
    prefix="/{module_name}",
    tags=["{module_name}"],
)

# Health check (REQUIRED)
@router.get("/health", response_model=dict)
async def health_check() -> dict:
    """Module health check."""
    return {"status": "healthy", "module": "{module_name}"}

# Standard CRUD operations (as needed)
@router.post("/{entities}", response_model={Entity}Response, status_code=201)
async def create_{entity}(
    request: {Entity}CreateRequest,
    service: {Entity}Service = Depends(get_{entity}_service),
) -> {Entity}Response:
    """Create new {entity}."""
    entity = await service.create(request)
    return {Entity}Response.from_entity(entity)

@router.get("/{entities}", response_model={Entity}ListResponse)
async def list_{entities}(
    limit: int = 100,
    offset: int = 0,
    service: {Entity}Service = Depends(get_{entity}_service),
) -> {Entity}ListResponse:
    """List {entities}."""
    entities = await service.list(limit=limit, offset=offset)
    total = await service.count()
    return {Entity}ListResponse(items=entities, total=total)

@router.get("/{entities}/{id}", response_model={Entity}Response)
async def get_{entity}(
    id: str,
    service: {Entity}Service = Depends(get_{entity}_service),
) -> {Entity}Response:
    """Get {entity} by ID."""
    entity = await service.get(id)
    if not entity:
        raise HTTPException(status_code=404, detail="{Entity} not found")
    return {Entity}Response.from_entity(entity)

@router.patch("/{entities}/{id}", response_model={Entity}Response)
async def update_{entity}(
    id: str,
    request: {Entity}UpdateRequest,
    service: {Entity}Service = Depends(get_{entity}_service),
) -> {Entity}Response:
    """Update {entity}."""
    entity = await service.update(id, request)
    if not entity:
        raise HTTPException(status_code=404, detail="{Entity} not found")
    return {Entity}Response.from_entity(entity)

@router.delete("/{entities}/{id}", status_code=204)
async def delete_{entity}(
    id: str,
    service: {Entity}Service = Depends(get_{entity}_service),
) -> None:
    """Delete {entity}."""
    success = await service.delete(id)
    if not success:
        raise HTTPException(status_code=404, detail="{Entity} not found")
```

**Best Practices:**
- ✅ Use appropriate HTTP methods (GET, POST, PATCH, DELETE)
- ✅ Use proper status codes (200, 201, 204, 404, etc.)
- ✅ Validate inputs with Pydantic schemas
- ✅ Use dependency injection for services
- ✅ Include descriptive docstrings
- ✅ Handle errors appropriately
- ❌ Don't put business logic in routes
- ❌ Don't access database directly

### 4.2 API Layer (schemas.py)

**Purpose:** Request/Response data validation with Pydantic

**Required Elements:**
```python
# modules/{module_name}/backend/api/schemas.py

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

# Base schema for common fields
class {Entity}Base(BaseModel):
    """Base {entity} schema."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)

# Request schemas
class {Entity}CreateRequest({Entity}Base):
    """Create {entity} request."""
    pass

class {Entity}UpdateRequest(BaseModel):
    """Update {entity} request (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)

# Response schemas
class {Entity}Response({Entity}Base):
    """Single {entity} response."""
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_entity(cls, entity: {Entity}) -> "{Entity}Response":
        """Convert domain entity to response schema."""
        return cls(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

class {Entity}ListResponse(BaseModel):
    """List of {entities} response."""
    items: List[{Entity}Response]
    total: int
    limit: int = 100
    offset: int = 0
```

**Best Practices:**
- ✅ Use Pydantic Field for validation
- ✅ Separate request/response schemas
- ✅ Use descriptive field names
- ✅ Include docstrings
- ✅ Use Optional for nullable fields
- ✅ Convert from domain entities, not ORM models
- ❌ Don't expose internal IDs or secrets
- ❌ Don't return ORM models directly

### 4.3 Application Layer (services/)

**Purpose:** Business logic orchestration and use case implementation

**Required Elements:**
```python
# modules/{module_name}/backend/application/services/{entity}_service.py

from typing import Optional, List
from ..dto import {Entity}DTO
from ...domain.entities import {Entity}
from ...domain.ports import I{Entity}Repository
from ...domain.exceptions import {Entity}NotFoundError
from core.events import EventBus

class {Entity}Service:
    """
    {Entity} application service.
    
    Hey future me, this service orchestrates business operations for {entity}.
    It uses repository for persistence and publishes events for other modules.
    NEVER put HTTP or database code here - that's infrastructure!
    """
    
    def __init__(
        self,
        repository: I{Entity}Repository,
        event_bus: EventBus,
    ):
        self._repository = repository
        self._event_bus = event_bus
    
    async def create(self, data: dict) -> {Entity}DTO:
        """
        Create new {entity}.
        
        Args:
            data: {Entity} creation data
            
        Returns:
            Created {entity} DTO
        """
        # 1. Create domain entity
        entity = {Entity}(
            id=generate_id(),
            name=data["name"],
            description=data.get("description"),
        )
        
        # 2. Apply business rules (if any)
        entity.validate()
        
        # 3. Save to repository
        saved = await self._repository.save(entity)
        
        # 4. Publish event
        await self._event_bus.publish(
            "{entity}.created",
            {"id": saved.id, "name": saved.name}
        )
        
        # 5. Return DTO
        return {Entity}DTO.from_entity(saved)
    
    async def get(self, entity_id: str) -> Optional[{Entity}DTO]:
        """
        Get {entity} by ID.
        
        Args:
            entity_id: {Entity} ID
            
        Returns:
            {Entity} DTO if found, None otherwise
        """
        entity = await self._repository.get(entity_id)
        return {Entity}DTO.from_entity(entity) if entity else None
    
    async def list(
        self, limit: int = 100, offset: int = 0
    ) -> List[{Entity}DTO]:
        """
        List {entities}.
        
        Args:
            limit: Maximum number of items
            offset: Offset for pagination
            
        Returns:
            List of {entity} DTOs
        """
        entities = await self._repository.list(limit=limit, offset=offset)
        return [{Entity}DTO.from_entity(e) for e in entities]
    
    async def update(
        self, entity_id: str, data: dict
    ) -> Optional[{Entity}DTO]:
        """
        Update {entity}.
        
        Args:
            entity_id: {Entity} ID
            data: Update data
            
        Returns:
            Updated {entity} DTO if found, None otherwise
        """
        # 1. Load entity
        entity = await self._repository.get(entity_id)
        if not entity:
            return None
        
        # 2. Update fields
        if "name" in data:
            entity.name = data["name"]
        if "description" in data:
            entity.description = data["description"]
        
        # 3. Validate
        entity.validate()
        
        # 4. Save
        saved = await self._repository.save(entity)
        
        # 5. Publish event
        await self._event_bus.publish(
            "{entity}.updated",
            {"id": saved.id}
        )
        
        # 6. Return DTO
        return {Entity}DTO.from_entity(saved)
    
    async def delete(self, entity_id: str) -> bool:
        """
        Delete {entity}.
        
        Args:
            entity_id: {Entity} ID
            
        Returns:
            True if deleted, False if not found
        """
        # 1. Check if exists
        entity = await self._repository.get(entity_id)
        if not entity:
            return False
        
        # 2. Delete
        await self._repository.delete(entity_id)
        
        # 3. Publish event
        await self._event_bus.publish(
            "{entity}.deleted",
            {"id": entity_id}
        )
        
        return True
    
    async def count(self) -> int:
        """
        Count {entities}.
        
        Returns:
            Total number of {entities}
        """
        return await self._repository.count()
```

**Best Practices:**
- ✅ Use dependency injection
- ✅ Work with domain entities, not ORM models
- ✅ Return DTOs, not domain entities
- ✅ Publish events for state changes
- ✅ Handle errors appropriately
- ✅ Include comprehensive docstrings
- ❌ Don't access database directly (use repository)
- ❌ Don't handle HTTP requests (use API layer)
- ❌ Don't put UI logic here

### 4.4 Domain Layer (entities/)

**Purpose:** Core business objects and rules

**Required Elements:**
```python
# modules/{module_name}/backend/domain/entities/{entity}.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from ..value_objects import {ValueObject}
from ..exceptions import {Entity}ValidationError

@dataclass
class {Entity}:
    """
    {Entity} domain entity.
    
    Hey future me, this is the CORE business object. Keep it pure - no database,
    no HTTP, no framework stuff! Just business logic and invariants.
    If you need external data, define a Port (interface) instead.
    """
    
    # Identity
    id: str
    
    # Business attributes
    name: str
    description: Optional[str] = None
    
    # Value objects
    status: {StatusValueObject} = field(default_factory=lambda: {StatusValueObject}.ACTIVE)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def validate(self) -> None:
        """
        Validate entity invariants.
        
        Raises:
            {Entity}ValidationError: If validation fails
        """
        if not self.name or len(self.name) == 0:
            raise {Entity}ValidationError("Name cannot be empty")
        
        if len(self.name) > 200:
            raise {Entity}ValidationError("Name too long (max 200 characters)")
        
        if self.description and len(self.description) > 1000:
            raise {Entity}ValidationError("Description too long (max 1000 characters)")
    
    def update_name(self, new_name: str) -> None:
        """
        Update entity name.
        
        Args:
            new_name: New name value
            
        Raises:
            {Entity}ValidationError: If name invalid
        """
        old_name = self.name
        self.name = new_name
        self.updated_at = datetime.utcnow()
        
        try:
            self.validate()
        except {Entity}ValidationError:
            # Rollback on validation failure
            self.name = old_name
            raise
    
    def mark_as_inactive(self) -> None:
        """Mark entity as inactive."""
        self.status = {StatusValueObject}.INACTIVE
        self.updated_at = datetime.utcnow()
    
    def __str__(self) -> str:
        return f"{Entity}(id={self.id}, name={self.name})"
```

**Best Practices:**
- ✅ Use dataclasses for entities
- ✅ Include validation methods
- ✅ Make entities immutable where possible
- ✅ Use value objects for complex values
- ✅ Include business rule methods
- ✅ Keep domain pure (no external dependencies)
- ❌ Don't add ORM annotations
- ❌ Don't import from infrastructure
- ❌ Don't add HTTP/database logic

### 4.5 Domain Layer (ports/)

**Purpose:** Define interfaces for external dependencies

**Required Elements:**
```python
# modules/{module_name}/backend/domain/ports/{entity}_repository.py

from typing import Protocol, Optional, List
from ..entities import {Entity}

class I{Entity}Repository(Protocol):
    """
    Repository interface for {Entity}.
    
    Hey future me, this is just the CONTRACT - the actual implementation
    is in infrastructure/persistence. This keeps domain pure and testable.
    SQLAlchemy implementation will be injected at runtime.
    """
    
    async def get(self, entity_id: str) -> Optional[{Entity}]:
        """
        Get entity by ID.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Entity if found, None otherwise
        """
        ...
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[dict] = None,
    ) -> List[{Entity}]:
        """
        List entities with optional filters.
        
        Args:
            limit: Maximum number of items
            offset: Offset for pagination
            filters: Optional filter criteria
            
        Returns:
            List of entities
        """
        ...
    
    async def save(self, entity: {Entity}) -> {Entity}:
        """
        Save entity (create or update).
        
        Args:
            entity: Entity to save
            
        Returns:
            Saved entity
        """
        ...
    
    async def delete(self, entity_id: str) -> None:
        """
        Delete entity.
        
        Args:
            entity_id: Entity ID to delete
        """
        ...
    
    async def count(self, filters: Optional[dict] = None) -> int:
        """
        Count entities with optional filters.
        
        Args:
            filters: Optional filter criteria
            
        Returns:
            Total count
        """
        ...
```

**Best Practices:**
- ✅ Use Protocol for interface definition
- ✅ Define all required methods
- ✅ Use domain entities, not ORM models
- ✅ Include comprehensive docstrings
- ✅ Keep interfaces focused (ISP)
- ❌ Don't include implementation
- ❌ Don't couple to specific technology

### 4.6 Infrastructure Layer (persistence/)

**Purpose:** Database models and repository implementations

**Required Elements:**
```python
# modules/{module_name}/backend/infrastructure/persistence/models.py

from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from core.database import Base

class {Entity}Model(Base):
    """
    SQLAlchemy model for {Entity}.
    
    Hey future me, this is the DATABASE representation only!
    Never use this directly in business logic - always convert to/from
    domain entities. This keeps database details isolated.
    """
    
    __tablename__ = "{module_name}_{entities}"
    
    # Primary key
    id = Column(String(100), primary_key=True)
    
    # Business fields
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="active")
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    def __repr__(self) -> str:
        return f"<{Entity}Model(id={self.id}, name={self.name})>"

# Repository implementation
# modules/{module_name}/backend/infrastructure/persistence/repositories.py

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ...domain.entities import {Entity}
from ...domain.ports import I{Entity}Repository
from .models import {Entity}Model

class {Entity}RepositorySQLAlchemy:
    """
    SQLAlchemy implementation of {Entity} repository.
    
    Hey future me, this is where we convert between ORM models and domain entities.
    ALWAYS convert to domain entities before returning - never leak ORM outside!
    Use _to_entity() and _to_model() helper methods consistently.
    """
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def get(self, entity_id: str) -> Optional[{Entity}]:
        """Get entity by ID."""
        model = await self._session.get({Entity}Model, entity_id)
        return self._to_entity(model) if model else None
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[dict] = None,
    ) -> List[{Entity}]:
        """List entities."""
        query = select({Entity}Model)
        
        # Apply filters
        if filters:
            if "status" in filters:
                query = query.where({Entity}Model.status == filters["status"])
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        result = await self._session.execute(query)
        models = result.scalars().all()
        
        return [self._to_entity(m) for m in models]
    
    async def save(self, entity: {Entity}) -> {Entity}:
        """Save entity."""
        # Check if exists
        existing = await self._session.get({Entity}Model, entity.id)
        
        if existing:
            # Update existing
            existing.name = entity.name
            existing.description = entity.description
            existing.status = entity.status.value
            existing.updated_at = entity.updated_at
            model = existing
        else:
            # Create new
            model = self._to_model(entity)
            self._session.add(model)
        
        await self._session.flush()
        return self._to_entity(model)
    
    async def delete(self, entity_id: str) -> None:
        """Delete entity."""
        model = await self._session.get({Entity}Model, entity_id)
        if model:
            await self._session.delete(model)
            await self._session.flush()
    
    async def count(self, filters: Optional[dict] = None) -> int:
        """Count entities."""
        query = select(func.count({Entity}Model.id))
        
        if filters and "status" in filters:
            query = query.where({Entity}Model.status == filters["status"])
        
        result = await self._session.execute(query)
        return result.scalar() or 0
    
    def _to_entity(self, model: {Entity}Model) -> {Entity}:
        """Convert ORM model to domain entity."""
        return {Entity}(
            id=model.id,
            name=model.name,
            description=model.description,
            status={StatusValueObject}(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: {Entity}) -> {Entity}Model:
        """Convert domain entity to ORM model."""
        return {Entity}Model(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            status=entity.status.value,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
```

**Best Practices:**
- ✅ Use SQLAlchemy async models
- ✅ Always convert ORM ↔ Domain entities
- ✅ Never return ORM models from repository
- ✅ Use helper methods for conversion
- ✅ Handle nullable fields properly
- ✅ Use database defaults where appropriate
- ❌ Don't put business logic in models
- ❌ Don't leak ORM outside infrastructure

---

## 5. Frontend Structure

### 5.1 Pages

**Purpose:** Full HTML pages for main features

```html
<!-- modules/{module_name}/frontend/pages/{feature}.html -->
{% extends "layouts/base.html" %}

{% block title %}{Feature} - {Module Name}{% endblock %}

{% block extra_css %}
    <link rel="stylesheet" href="/{module_name}/static/styles/{module}.css">
{% endblock %}

{% block content %}
    <div class="container">
        <h1>{Feature} Management</h1>
        
        <!-- Include widgets -->
        {% include "modules/{module_name}/frontend/widgets/{widget}.html" %}
    </div>
{% endblock %}

{% block extra_js %}
    <script src="/{module_name}/static/scripts/{feature}.js"></script>
{% endblock %}
```

### 5.2 Widgets

**Purpose:** Reusable UI components

```html
<!-- modules/{module_name}/frontend/widgets/{component}.html -->
<div class="{component}-widget" id="{component}-widget">
    <div class="widget-header">
        <h2>{{ title }}</h2>
        <button hx-get="/{module_name}/{entities}/refresh"
                hx-target="#{component}-content"
                hx-swap="innerHTML">
            Refresh
        </button>
    </div>
    
    <div class="widget-content" id="{component}-content">
        {% for item in items %}
            {% include "modules/{module_name}/frontend/partials/{item_partial}.html" %}
        {% endfor %}
    </div>
</div>
```

### 5.3 Partials

**Purpose:** Small template fragments

```html
<!-- modules/{module_name}/frontend/partials/{fragment}.html -->
<div class="{entity}-item" data-id="{{ item.id }}">
    <div class="item-info">
        <h3>{{ item.name }}</h3>
        <p>{{ item.description }}</p>
    </div>
    
    <div class="item-actions">
        <button hx-get="/{module_name}/{entities}/{{ item.id }}"
                hx-target="#detail-modal"
                hx-swap="innerHTML">
            View
        </button>
        
        <button hx-delete="/{module_name}/{entities}/{{ item.id }}"
                hx-confirm="Delete this item?"
                hx-target="closest .{entity}-item"
                hx-swap="outerHTML swap:1s">
            Delete
        </button>
    </div>
</div>
```

---

## 6. Configuration

### 6.1 Module Settings

```python
# modules/{module_name}/backend/config/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict

class {ModuleName}Settings(BaseSettings):
    """
    {Module Name} configuration settings.
    
    Hey future me, these settings are loaded from environment variables.
    Prefix with {MODULE}_ to avoid conflicts. Use Pydantic validation
    to catch config errors early!
    """
    
    # Module-specific settings
    feature_enabled: bool = True
    max_items: int = 1000
    cache_ttl_seconds: int = 300
    
    # External service settings (if any)
    external_api_url: str = "https://api.example.com"
    external_api_key: str
    
    # Optional settings with defaults
    debug_mode: bool = False
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_prefix="{MODULE}_",  # e.g., "SOULSEEK_" for soulseek module (uppercase)
        env_file=".env",
        case_sensitive=False,
    )

# Singleton instance
settings = {ModuleName}Settings()
```

---

## 7. Testing Requirements

### 7.1 Test Coverage

**Minimum Coverage Requirements:**
- Overall module coverage: **80%+**
- Domain layer: **90%+**
- Application layer: **85%+**
- API layer: **75%+**
- Infrastructure layer: **70%+**

### 7.2 Test Structure

```python
# modules/{module_name}/tests/unit/test_{entity}_service.py

import pytest
from unittest.mock import AsyncMock, Mock

from ...backend.application.services import {Entity}Service
from ...backend.domain.entities import {Entity}
from ...backend.domain.exceptions import {Entity}ValidationError

@pytest.fixture
def mock_repository():
    """Mock repository fixture."""
    return AsyncMock()

@pytest.fixture
def mock_event_bus():
    """Mock event bus fixture."""
    return AsyncMock()

@pytest.fixture
def service(mock_repository, mock_event_bus):
    """Service fixture."""
    return {Entity}Service(mock_repository, mock_event_bus)

class Test{Entity}ServiceCreate:
    """Tests for {entity} creation."""
    
    async def test_create_{entity}_success(self, service, mock_repository):
        """Test successful {entity} creation."""
        # Arrange
        data = {"name": "Test", "description": "Test description"}
        mock_repository.save.return_value = {Entity}(
            id="test-id",
            name="Test",
            description="Test description",
        )
        
        # Act
        result = await service.create(data)
        
        # Assert
        assert result.name == "Test"
        assert result.description == "Test description"
        mock_repository.save.assert_called_once()
    
    async def test_create_{entity}_validation_error(self, service):
        """Test {entity} creation with invalid data."""
        # Arrange
        data = {"name": "", "description": "Test"}
        
        # Act & Assert
        with pytest.raises({Entity}ValidationError):
            await service.create(data)
```

---

## 8. Documentation Requirements

### 8.1 Module README

Every module MUST have a comprehensive README.md:

```markdown
# {Module Name} Module

## Purpose
Brief description of what this module does.

## Features
- Feature 1: Description
- Feature 2: Description
- Feature 3: Description

## Architecture
Brief overview of module architecture and key components.

## API Endpoints

### {Entity} Management
- `GET /{module}/{entities}` - List {entities}
- `POST /{module}/{entities}` - Create {entity}
- `GET /{module}/{entities}/{id}` - Get {entity}
- `PATCH /{module}/{entities}/{id}` - Update {entity}
- `DELETE /{module}/{entities}/{id}` - Delete {entity}

## Events

### Published
- `{entity}.created` - When {entity} is created
- `{entity}.updated` - When {entity} is updated
- `{entity}.deleted` - When {entity} is deleted

### Subscribed
- `other.event` - Description of what triggers this

## Configuration

### Environment Variables
- `{MODULE}_FEATURE_ENABLED` - Enable/disable feature (default: true)
- `{MODULE}_MAX_ITEMS` - Maximum items (default: 1000)

## Dependencies

### Required
- `core` - Core functionality

### Optional
- `other_module` - For feature X

## Testing

Run module tests:
```bash
pytest modules/{module_name}/tests/ -v
```

## Development

Local development setup:
1. Install dependencies
2. Configure environment
3. Run tests
4. Start development server

## Migration Notes
(If applicable) How this module relates to previous code.
```

---

## 9. Quality Checklist

### 9.1 Code Quality

Before submitting a module, verify:

**Code Structure:**
- [ ] Follows directory structure specification
- [ ] All required files present
- [ ] Proper layer separation (API → Application → Domain → Infrastructure)
- [ ] No circular dependencies
- [ ] No imports from other modules' internals

**Code Quality:**
- [ ] All code passes `ruff check`
- [ ] All code passes `mypy --strict`
- [ ] All code passes `bandit` security scan
- [ ] No hardcoded secrets or credentials
- [ ] Comprehensive docstrings
- [ ] Type hints on all public functions

**Testing:**
- [ ] Unit tests cover all services
- [ ] Integration tests for critical flows
- [ ] Test coverage meets requirements (80%+)
- [ ] All tests pass
- [ ] No skipped tests without good reason

**Documentation:**
- [ ] README.md complete and accurate
- [ ] API endpoints documented
- [ ] Events documented
- [ ] Configuration documented
- [ ] Examples provided

### 9.2 Module Integration

**Registration:**
- [ ] Module registered in main application
- [ ] Router properly mounted
- [ ] Static files properly served
- [ ] Templates properly loaded

**Events:**
- [ ] All published events documented
- [ ] All subscribed events handled
- [ ] Event schemas defined
- [ ] Error handling for events

**Dependencies:**
- [ ] Required dependencies listed
- [ ] Optional dependencies listed
- [ ] Dependency versions specified
- [ ] No conflicting dependencies

---

## 10. Acceptance Criteria

A module is considered complete when:

1. ✅ All code follows this specification
2. ✅ All tests pass with required coverage
3. ✅ All quality checks pass (lint, type, security)
4. ✅ Documentation is complete
5. ✅ Module can run independently
6. ✅ Integration tests pass
7. ✅ Code review approved
8. ✅ No security vulnerabilities
9. ✅ Performance is acceptable
10. ✅ User acceptance testing completed

---

## 11. Module Template Generator

Use this template to create a new module:

```bash
# Create module structure
./scripts/create_module.sh {module_name}

# This will create:
# - All required directories
# - Template files with placeholders
# - Basic tests
# - README template
# - Configuration template
```

---

## 12. Conclusion

This specification ensures all modules follow consistent patterns and meet quality standards. Following this template makes modules:

- **Easy to understand**: Consistent structure
- **Easy to test**: Clear boundaries
- **Easy to maintain**: Isolated changes
- **Easy to integrate**: Standard interfaces

**Next:** See [Soulseek Module Design](./SOULSEEK_MODULE.md) for a complete example implementation.

---

**Related Documents:**
- [Roadmap](./ROADMAP.md)
- [Architecture](./ARCHITECTURE.md)
- [Soulseek Module Design](./SOULSEEK_MODULE.md)
- [Module Communication](./MODULE_COMMUNICATION.md)

**Status:** ✅ Complete - Planning Phase
