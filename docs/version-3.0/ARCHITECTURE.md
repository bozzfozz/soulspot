# SoulSpot - Modular Architecture Specification (Version 3.0)

> **⚠️ DEPRECATED - UNREALIZED DESIGN:** This modular architecture was **never implemented**. Current production (v0.1.0) uses **Hexagonal/Layered Architecture** (API → Application → Domain → Infrastructure). See `docs/project/architecture.md` for actual implementation.

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

**Version:** 3.0.0  
**Status:** ~~Planning Phase~~ UNREALIZED PROPOSAL  
**Last Updated:** 2025-11-21

---

## 1. Overview

This document defines the **modular architecture** for SoulSpot Version 3.0. The architecture transforms the current layered monolith into a collection of **self-contained feature modules** while maintaining the proven principles of clean architecture, dependency inversion, and SOLID design.

### 1.1 Architecture Goals

1. **Modularity**: Each feature is a self-contained module
2. **Maintainability**: Clear boundaries make code easier to understand
3. **Testability**: Modules can be tested in isolation
4. **Scalability**: New features can be added as new modules
5. **Developer Experience**: Easy to understand and contribute to

### 1.2 Key Principles

**From Clean Architecture:**
- Dependency Inversion (depend on abstractions)
- Separation of Concerns (layers within modules)
- Independence of Frameworks (domain logic is pure)
- Testability (mock boundaries easily)

**New Module-Specific Principles:**
- Feature Ownership (one feature = one module)
- Vertical Slicing (frontend + backend together)
- Explicit Contracts (well-defined interfaces)
- Loose Coupling (modules communicate via contracts)

---

## 2. Architecture Layers

### 2.1 System-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      PRESENTATION TIER                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Browser    │  │   Mobile     │  │   API        │      │
│  │   (HTMX)     │  │   (Future)   │  │   Clients    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓↓↓
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION GATEWAY                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FastAPI Application                                 │  │
│  │  - Routing                                           │  │
│  │  - Module Registration                               │  │
│  │  - Global Middleware (Auth, CORS, Logging)          │  │
│  │  - Static File Serving                              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓↓↓
┌─────────────────────────────────────────────────────────────┐
│                      CORE SERVICES                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │   Event    │  │  Module    │  │   Auth     │            │
│  │    Bus     │  │  Registry  │  │  Service   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────┘
                            ↓↓↓
┌─────────────────────────────────────────────────────────────┐
│                      FEATURE MODULES                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ Soulseek   │  │  Spotify   │  │  Library   │            │
│  │  Module    │  │   Module   │  │   Module   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ Metadata   │  │ Dashboard  │  │  Settings  │            │
│  │  Module    │  │   Module   │  │   Module   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────┘
                            ↓↓↓
┌─────────────────────────────────────────────────────────────┐
│                   INFRASTRUCTURE TIER                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  Database  │  │   Cache    │  │   Queue    │            │
│  │  (SQLite)  │  │  (Memory)  │  │  (Memory)  │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  External  │  │   File     │  │  Logging   │            │
│  │    APIs    │  │  Storage   │  │  & Metrics │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Module-Level Architecture

Each module follows the **Layered Architecture** pattern internally:

```
┌─────────────────────────────────────────────────────────────┐
│                   MODULE: {module_name}                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │              FRONTEND LAYER                        │    │
│  │  - Pages (full HTML pages)                         │    │
│  │  - Widgets (reusable UI components)                │    │
│  │  - Partials (template fragments)                   │    │
│  │  - Styles (CSS)                                    │    │
│  │  - Scripts (JavaScript)                            │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓↓↓                                │
│  ┌────────────────────────────────────────────────────┐    │
│  │              API LAYER (Routes)                    │    │
│  │  - HTTP Endpoints (FastAPI routers)                │    │
│  │  - Request/Response Schemas (Pydantic)             │    │
│  │  - Input Validation                                │    │
│  │  - Error Handling                                  │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓↓↓                                │
│  ┌────────────────────────────────────────────────────┐    │
│  │           APPLICATION LAYER (Services)             │    │
│  │  - Use Cases / Command Handlers                    │    │
│  │  - Service Orchestration                           │    │
│  │  - DTOs (Data Transfer Objects)                    │    │
│  │  - Transaction Management                          │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓↓↓                                │
│  ┌────────────────────────────────────────────────────┐    │
│  │              DOMAIN LAYER (Core Logic)             │    │
│  │  - Entities (business objects)                     │    │
│  │  - Value Objects (immutable values)                │    │
│  │  - Domain Services (business rules)                │    │
│  │  - Domain Events                                   │    │
│  │  - Ports (interface definitions)                   │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓↓↓                                │
│  ┌────────────────────────────────────────────────────┐    │
│  │         INFRASTRUCTURE LAYER (Adapters)            │    │
│  │  - Persistence (repositories, ORM models)          │    │
│  │  - Integrations (external API clients)             │    │
│  │  - Adapters (port implementations)                 │    │
│  │  - Configuration                                   │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Directory Structure

### 3.1 Root Structure

```
soulspot/
├── docs/                           # Documentation
│   ├── version-3.0/                # V3 architecture docs
│   └── ...
├── src/
│   ├── core/                       # Core shared functionality
│   │   ├── events/                 # Event bus
│   │   ├── registry/               # Module registry
│   │   ├── auth/                   # Authentication
│   │   ├── database/               # Database management
│   │   ├── config/                 # Global configuration
│   │   └── utils/                  # Shared utilities
│   │
│   ├── modules/                    # Feature modules
│   │   ├── soulseek/               # Soulseek module
│   │   ├── spotify/                # Spotify module
│   │   ├── library/                # Library module
│   │   ├── metadata/               # Metadata module
│   │   ├── dashboard/              # Dashboard module
│   │   ├── settings/               # Settings module
│   │   └── automation/             # Automation module
│   │
│   └── soulspot/                   # Main application (gateway)
│       ├── main.py                 # FastAPI app entry
│       ├── middleware/             # Global middleware
│       ├── templates/              # Shared templates
│       └── static/                 # Shared static files
│
├── tests/                          # Global integration tests
│   ├── integration/                # Cross-module tests
│   ├── e2e/                        # End-to-end tests
│   └── fixtures/                   # Shared fixtures
│
├── alembic/                        # Database migrations
├── docker/                         # Docker configuration
└── scripts/                        # Utility scripts
```

### 3.2 Module Structure (Detailed)

```
modules/{module_name}/
├── README.md                       # Module documentation
├── __init__.py                     # Module exports
│
├── frontend/                       # Frontend layer
│   ├── __init__.py
│   ├── pages/                      # Full page templates
│   │   ├── {feature}.html
│   │   └── {feature}_detail.html
│   ├── widgets/                    # Reusable components
│   │   ├── {component}.html
│   │   └── {component}_card.html
│   ├── partials/                   # Template fragments
│   │   ├── {fragment}.html
│   │   └── {list_item}.html
│   ├── styles/                     # CSS files
│   │   ├── {module}.css
│   │   └── components/
│   │       └── {component}.css
│   └── scripts/                    # JavaScript files
│       ├── {module}.js
│       └── components/
│           └── {component}.js
│
├── backend/                        # Backend layers
│   ├── __init__.py
│   │
│   ├── api/                        # API/Presentation layer
│   │   ├── __init__.py
│   │   ├── routes.py               # FastAPI router
│   │   ├── schemas.py              # Request/Response schemas
│   │   └── dependencies.py         # Route dependencies
│   │
│   ├── application/                # Application layer
│   │   ├── __init__.py
│   │   ├── services/               # Service orchestration
│   │   │   ├── __init__.py
│   │   │   └── {feature}_service.py
│   │   ├── use_cases/              # Use case handlers
│   │   │   ├── __init__.py
│   │   │   ├── commands/           # Write operations
│   │   │   │   └── {action}_command.py
│   │   │   └── queries/            # Read operations
│   │   │       └── {query}_query.py
│   │   └── dto/                    # Data Transfer Objects
│   │       ├── __init__.py
│   │       └── {entity}_dto.py
│   │
│   ├── domain/                     # Domain layer
│   │   ├── __init__.py
│   │   ├── entities/               # Business entities
│   │   │   ├── __init__.py
│   │   │   └── {entity}.py
│   │   ├── value_objects/          # Value objects
│   │   │   ├── __init__.py
│   │   │   └── {value}.py
│   │   ├── services/               # Domain services
│   │   │   ├── __init__.py
│   │   │   └── {domain_service}.py
│   │   ├── events/                 # Domain events
│   │   │   ├── __init__.py
│   │   │   └── {event}.py
│   │   ├── ports/                  # Interface definitions
│   │   │   ├── __init__.py
│   │   │   └── {port}.py
│   │   └── exceptions/             # Domain exceptions
│   │       ├── __init__.py
│   │       └── {exception}.py
│   │
│   ├── infrastructure/             # Infrastructure layer
│   │   ├── __init__.py
│   │   ├── persistence/            # Database layer
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # SQLAlchemy models
│   │   │   └── repositories.py     # Repository implementations
│   │   ├── integrations/           # External services
│   │   │   ├── __init__.py
│   │   │   └── {external}_client.py
│   │   └── adapters/               # Port implementations
│   │       ├── __init__.py
│   │       └── {adapter}.py
│   │
│   └── config/                     # Module configuration
│       ├── __init__.py
│       └── settings.py             # Pydantic settings
│
├── tests/                          # Module tests
│   ├── __init__.py
│   ├── unit/                       # Unit tests
│   │   ├── test_services.py
│   │   ├── test_entities.py
│   │   └── test_repositories.py
│   ├── integration/                # Integration tests
│   │   └── test_{feature}_flow.py
│   └── fixtures/                   # Test fixtures
│       └── {entity}_fixtures.py
│
└── contracts/                      # Module contracts (future)
    ├── api.yaml                    # OpenAPI specification
    ├── events.yaml                 # Event schemas
    └── dependencies.yaml           # Module dependencies
```

---

## 4. Module Design Patterns

### 4.1 Module Interface Pattern

**Every module exposes a standard interface:**

```python
# modules/{module_name}/__init__.py

from .backend.api.routes import router
from .backend.config.settings import ModuleSettings

class Module:
    """Standard module interface."""
    
    # Hey future me, this is the contract every module MUST implement.
    # Don't skip any of these or the module registry will break!
    # The router is what FastAPI needs, settings is for config validation.
    
    name: str = "{module_name}"
    version: str = "1.0.0"
    router: APIRouter = router
    settings: ModuleSettings = ModuleSettings()
    
    @staticmethod
    def health_check() -> dict:
        """Module health check."""
        return {"status": "healthy", "module": "{module_name}"}
    
    @staticmethod
    def get_info() -> dict:
        """Module metadata."""
        return {
            "name": "{module_name}",
            "version": "1.0.0",
            "description": "Module description",
            "endpoints": ["/path1", "/path2"],
            "events": ["event.published"],
        }

# Export module interface
__all__ = ["Module"]
```

### 4.2 Service Layer Pattern

**Application services orchestrate use cases:**

```python
# modules/{module_name}/backend/application/services/{feature}_service.py

from typing import Protocol
from ..dto import EntityDTO
from ...domain.ports import IRepository, IExternalService

class FeatureService:
    """
    Hey future me, this service is the main entry point for business logic.
    It coordinates between domain entities, repositories, and external services.
    NEVER put HTTP or database logic here - that belongs in infrastructure!
    """
    
    def __init__(
        self,
        repository: IRepository,
        external_service: IExternalService,
        event_bus: IEventBus,
    ):
        self._repository = repository
        self._external_service = external_service
        self._event_bus = event_bus
    
    async def execute_business_operation(
        self, params: dict
    ) -> EntityDTO:
        """Execute main business operation."""
        # 1. Validate input (or delegate to use case)
        # 2. Load domain entities
        entity = await self._repository.get(params["id"])
        
        # 3. Execute domain logic
        entity.apply_business_rule(params)
        
        # 4. Persist changes
        await self._repository.save(entity)
        
        # 5. Publish events
        await self._event_bus.publish(
            "entity.updated", {"id": entity.id}
        )
        
        # 6. Return DTO
        return EntityDTO.from_entity(entity)
```

### 4.3 Repository Pattern

**Repositories abstract data access:**

```python
# modules/{module_name}/backend/domain/ports/{entity}_repository.py

from typing import Protocol, List, Optional
from ..entities import Entity

class IEntityRepository(Protocol):
    """
    Repository interface for Entity.
    
    Hey future me, this is just the CONTRACT - the actual implementation
    is in infrastructure layer. This keeps domain pure and testable.
    Don't add concrete database logic here!
    """
    
    async def get(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        ...
    
    async def list(
        self, filters: dict, limit: int = 100
    ) -> List[Entity]:
        """List entities with filters."""
        ...
    
    async def save(self, entity: Entity) -> Entity:
        """Save entity."""
        ...
    
    async def delete(self, entity_id: str) -> None:
        """Delete entity."""
        ...

# Implementation in infrastructure
# modules/{module_name}/backend/infrastructure/persistence/repositories.py

class EntityRepositorySQLAlchemy:
    """SQLAlchemy implementation of entity repository."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def get(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        model = await self._session.get(EntityModel, entity_id)
        return self._to_entity(model) if model else None
    
    def _to_entity(self, model: EntityModel) -> Entity:
        """Convert ORM model to domain entity."""
        return Entity(
            id=model.id,
            name=model.name,
            # ... map all fields
        )
```

### 4.4 Event-Driven Pattern

**Modules communicate via events:**

```python
# core/events/event_bus.py

from typing import Callable

class EventBus:
    """
    Central event bus for inter-module communication.
    
    Hey future me, this is how modules talk to each other WITHOUT
    direct coupling. Publisher doesn't know who's listening, subscriber
    doesn't know who published. That's the magic!
    """
    
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
    
    def subscribe(self, event_name: str, handler: Callable) -> None:
        """Subscribe to event."""
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)
    
    async def publish(self, event_name: str, data: dict) -> None:
        """Publish event to all subscribers."""
        if event_name in self._handlers:
            for handler in self._handlers[event_name]:
                await handler(data)

# Usage in module
# modules/soulseek/backend/application/services/download_service.py

class DownloadService:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
    
    async def complete_download(self, download_id: str):
        """Complete download and notify other modules."""
        # ... complete download logic
        
        # Publish event
        await self._event_bus.publish(
            "download.completed",
            {
                "download_id": download_id,
                "file_path": "/path/to/file.mp3",
                "track_id": "track-123",
            }
        )

# Another module subscribes
# modules/metadata/backend/application/services/metadata_service.py

class MetadataService:
    def __init__(self, event_bus: EventBus):
        # Subscribe to download completion
        event_bus.subscribe(
            "download.completed",
            self._on_download_completed
        )
    
    async def _on_download_completed(self, event_data: dict):
        """Handle download completion event."""
        file_path = event_data["file_path"]
        await self.enrich_metadata(file_path)
```

---

## 5. Module Communication

### 5.1 Communication Types

**1. Synchronous (Direct Call)**
```python
# Use when: Immediate response needed, within same request context
from core.registry import module_registry

# Get module service
metadata_service = module_registry.get_service("metadata")
result = await metadata_service.get_track_info(track_id)
```

**2. Asynchronous (Events)**
```python
# Use when: Fire-and-forget, loosely coupled communication
from core.events import event_bus

# Publish event
await event_bus.publish("track.downloaded", {"track_id": "123"})

# Subscribe in another module
@event_bus.subscribe("track.downloaded")
async def on_track_downloaded(event_data: dict):
    # Handle event
    pass
```

**3. Request-Response (RPC-style)**
```python
# Use when: Need response but want loose coupling
result = await module_registry.query(
    module="library",
    operation="search",
    params={"query": "Beatles"}
)
```

### 5.2 Communication Rules

**DO:**
- ✅ Use events for cross-module notifications
- ✅ Define clear event schemas
- ✅ Use typed data in events
- ✅ Handle event failures gracefully
- ✅ Log all cross-module communication

**DON'T:**
- ❌ Import implementation from other modules
- ❌ Share mutable state across modules
- ❌ Create circular event dependencies
- ❌ Put business logic in event handlers
- ❌ Skip error handling in event subscribers

---

## 6. Data Management

### 6.1 Database Strategy

**Shared Database with Module Schemas:**

```sql
-- Each module owns its tables
CREATE TABLE soulseek_downloads (
    id TEXT PRIMARY KEY,
    track_id TEXT NOT NULL,
    status TEXT NOT NULL,
    -- ... module-specific fields
);

CREATE TABLE spotify_playlists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    -- ... module-specific fields
);

-- Relationships across modules via IDs only
CREATE TABLE library_tracks (
    id TEXT PRIMARY KEY,
    spotify_track_id TEXT,  -- Reference to spotify module
    download_id TEXT,        -- Reference to soulseek module
    -- ... library-specific fields
);
```

**Migration Management:**
```python
# alembic/versions/{timestamp}_add_soulseek_tables.py

def upgrade():
    """Add Soulseek module tables."""
    op.create_table(
        'soulseek_downloads',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('track_id', sa.String(), nullable=False),
        # ... columns
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    """Remove Soulseek module tables."""
    op.drop_table('soulseek_downloads')
```

### 6.2 Data Consistency

**Cross-Module Transactions:**
```python
# Use events for eventual consistency
async def create_download_and_track(track_data, download_data):
    """Create related entities across modules."""
    
    # 1. Create in first module (transactional)
    async with db_session() as session:
        download = await download_service.create(download_data)
        await session.commit()
    
    # 2. Publish event for other module
    await event_bus.publish(
        "download.created",
        {"download_id": download.id, "track_data": track_data}
    )
    
    # 3. Other module creates its entity
    @event_bus.subscribe("download.created")
    async def on_download_created(event_data):
        async with db_session() as session:
            track = await track_service.create(event_data["track_data"])
            await session.commit()
```

---

## 7. Frontend Architecture

### 7.1 Template Organization

**Base Layout (Shared):**
```html
<!-- src/soulspot/templates/layouts/base.html -->
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}SoulSpot{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/base.css">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav>{% include "partials/navigation.html" %}</nav>
    
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <script src="/static/js/htmx.min.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

**Module Page:**
```html
<!-- modules/soulseek/frontend/pages/downloads.html -->
{% extends "layouts/base.html" %}

{% block title %}Downloads - SoulSpot{% endblock %}

{% block extra_css %}
    <link rel="stylesheet" href="/soulseek/static/styles/soulseek.css">
{% endblock %}

{% block content %}
    <h1>Download Management</h1>
    
    <!-- Module widgets -->
    {% include "modules/soulseek/frontend/widgets/download_queue.html" %}
    {% include "modules/soulseek/frontend/widgets/download_stats.html" %}
{% endblock %}

{% block extra_js %}
    <script src="/soulseek/static/scripts/downloads.js"></script>
{% endblock %}
```

### 7.2 HTMX Patterns

**Module Endpoints with HTMX:**
```html
<!-- Module widget with HTMX -->
<div id="download-queue"
     hx-get="/soulseek/downloads/queue"
     hx-trigger="load, every 2s"
     hx-swap="innerHTML">
    Loading...
</div>

<!-- Form submission -->
<form hx-post="/soulseek/downloads/start"
      hx-target="#download-queue"
      hx-swap="afterbegin">
    <input name="track_id" type="text" required>
    <button type="submit">Start Download</button>
</form>
```

**Backend Route:**
```python
# modules/soulseek/backend/api/routes.py

@router.get("/downloads/queue")
async def get_download_queue(
    request: Request,
    service: DownloadService = Depends(get_download_service)
):
    """Get download queue (HTMX endpoint)."""
    downloads = await service.get_active_downloads()
    
    return templates.TemplateResponse(
        "modules/soulseek/frontend/partials/download_list.html",
        {"request": request, "downloads": downloads}
    )
```

---

## 8. Testing Strategy

### 8.1 Test Pyramid

```
        ┌─────────────┐
        │    E2E      │  ← Few (cross-module flows)
        │   Tests     │
        └─────────────┘
       ┌───────────────┐
       │  Integration  │  ← Some (module boundaries)
       │     Tests     │
       └───────────────┘
      ┌─────────────────┐
      │   Unit Tests    │  ← Many (pure logic)
      │  (per module)   │
      └─────────────────┘
```

### 8.2 Module Testing Levels

**Unit Tests (modules/{name}/tests/unit/)**
```python
# Test domain logic in isolation
async def test_download_entity_can_be_started():
    download = Download(id="dl-1", status=DownloadStatus.QUEUED)
    download.start()
    assert download.status == DownloadStatus.IN_PROGRESS

# Test service logic with mocks
async def test_download_service_starts_download(mock_repo, mock_slskd):
    service = DownloadService(mock_repo, mock_slskd)
    download = await service.start_download(track_id="123")
    assert download.status == DownloadStatus.QUEUED
    mock_repo.save.assert_called_once()
```

**Integration Tests (modules/{name}/tests/integration/)**
```python
# Test module with real dependencies
async def test_download_flow_with_real_database(db_session):
    # Use real database, mock external APIs
    repo = DownloadRepository(db_session)
    slskd = MockSlskdClient()
    service = DownloadService(repo, slskd)
    
    # Execute full flow
    download = await service.start_download(track_id="123")
    await service.complete_download(download.id)
    
    # Verify database state
    saved = await repo.get(download.id)
    assert saved.status == DownloadStatus.COMPLETED
```

**E2E Tests (tests/e2e/)**
```python
# Test cross-module flows
async def test_track_download_and_enrichment_flow(test_client):
    # Start download (soulseek module)
    response = await test_client.post(
        "/soulseek/downloads/start",
        json={"track_id": "123"}
    )
    download_id = response.json()["id"]
    
    # Complete download (triggers event)
    await complete_download_mock(download_id)
    
    # Verify metadata enrichment (metadata module)
    track = await test_client.get(f"/metadata/tracks/123")
    assert track.json()["enriched"] is True
```

---

## 9. Configuration Management

### 9.1 Settings Hierarchy

```python
# core/config/settings.py - Global settings
class GlobalSettings(BaseSettings):
    app_env: str = "development"
    database_url: str
    secret_key: str
    # ... global config

# modules/soulseek/backend/config/settings.py - Module settings
class SoulseekSettings(BaseSettings):
    slskd_url: str
    slskd_api_key: str
    download_dir: str
    max_concurrent_downloads: int = 3
    
    class Config:
        env_prefix = "SLSKD_"  # Environment variables

# Load in module
settings = SoulseekSettings()
```

### 9.2 Environment Variables

```bash
# .env file

# Global
APP_ENV=development
DATABASE_URL=sqlite:///./soulspot.db
SECRET_KEY=your-secret-key

# Soulseek Module
SLSKD_URL=http://localhost:5030
SLSKD_API_KEY=your-api-key
SLSKD_DOWNLOAD_DIR=/mnt/downloads
SLSKD_MAX_CONCURRENT_DOWNLOADS=3

# Spotify Module
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret

# ... other modules
```

---

## 10. Migration Path

### 10.1 From Current to Modular

**Step 1: Create Module Structure**
```bash
# Create module directories
mkdir -p modules/soulseek/{frontend,backend,tests}
mkdir -p modules/soulseek/backend/{api,application,domain,infrastructure,config}
# ... etc
```

**Step 2: Move Code**
```python
# Old location
# src/soulspot/infrastructure/integrations/slskd_client.py

# New location
# modules/soulseek/backend/infrastructure/integrations/slskd_client.py
```

**Step 3: Update Imports**
```python
# Old import
from soulspot.infrastructure.integrations.slskd_client import SlskdClient

# New import
from modules.soulseek.backend.infrastructure.integrations.slskd_client import SlskdClient
```

**Step 4: Register Module**
```python
# src/soulspot/main.py

from modules.soulseek import Module as SoulseekModule

app = FastAPI()

# Register module router
app.include_router(
    SoulseekModule.router,
    prefix="/soulseek",
    tags=["soulseek"]
)
```

---

## 11. Best Practices

### 11.1 Module Development

**DO:**
- ✅ Keep modules focused on single feature
- ✅ Use dependency injection for testability
- ✅ Define clear interfaces (ports)
- ✅ Write tests before/during implementation
- ✅ Document public APIs
- ✅ Version module contracts
- ✅ Handle errors gracefully
- ✅ Log important events

**DON'T:**
- ❌ Access other modules' internals
- ❌ Skip error handling
- ❌ Hardcode configuration
- ❌ Mix layers (API in domain, etc.)
- ❌ Create god objects
- ❌ Ignore security concerns
- ❌ Skip documentation

### 11.2 Code Quality

**Type Safety:**
```python
# Use strict typing
from typing import Protocol, Optional, List

class IRepository(Protocol):
    async def get(self, id: str) -> Optional[Entity]: ...
    async def list(self) -> List[Entity]: ...
```

**Error Handling:**
```python
# Define domain exceptions
class DownloadNotFoundError(Exception):
    """Download not found."""
    pass

# Handle in service
async def get_download(self, download_id: str) -> Download:
    download = await self._repo.get(download_id)
    if not download:
        raise DownloadNotFoundError(f"Download {download_id} not found")
    return download

# Handle in API
@router.get("/downloads/{id}")
async def get_download(id: str, service: DownloadService = Depends()):
    try:
        download = await service.get_download(id)
        return DownloadSchema.from_entity(download)
    except DownloadNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

---

## 12. Performance Considerations

### 12.1 Module Loading

**Lazy Loading:**
```python
# Load modules on-demand
class ModuleLoader:
    def __init__(self):
        self._modules: dict[str, Any] = {}
    
    def load_module(self, name: str) -> Any:
        """Load module lazily."""
        if name not in self._modules:
            module = importlib.import_module(f"modules.{name}")
            self._modules[name] = module.Module()
        return self._modules[name]
```

**Caching:**
```python
# Cache frequently accessed data
from functools import lru_cache

class MetadataService:
    @lru_cache(maxsize=1000)
    async def get_track_info(self, track_id: str) -> TrackInfo:
        """Get track info with caching."""
        return await self._external_api.get_track(track_id)
```

### 12.2 Database Optimization

**Connection Pooling:**
```python
# Use connection pool
engine = create_async_engine(
    database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)
```

**Query Optimization:**
```python
# Eager loading for relationships
query = (
    select(Download)
    .options(joinedload(Download.track))
    .where(Download.status == DownloadStatus.IN_PROGRESS)
)
```

---

## 13. Security

### 13.1 Module Security

**Input Validation:**
```python
# Validate all inputs with Pydantic
class DownloadStartRequest(BaseModel):
    track_id: str = Field(..., min_length=1, max_length=100)
    quality: str = Field(..., regex="^(low|medium|high)$")
```

**Authentication:**
```python
# Protect routes
@router.post("/downloads/start")
async def start_download(
    request: DownloadStartRequest,
    current_user: User = Depends(get_current_user)
):
    # Only authenticated users can download
    ...
```

**Authorization:**
```python
# Check permissions
def require_permission(permission: str):
    async def dependency(user: User = Depends(get_current_user)):
        if not user.has_permission(permission):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dependency

@router.delete("/downloads/{id}")
async def delete_download(
    id: str,
    user: User = Depends(require_permission("download.delete"))
):
    ...
```

---

## 14. Monitoring and Observability

### 14.1 Logging

**Structured Logging:**
```python
import logging
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)

# Log with context
logger.info(
    "Download started",
    extra={
        "module": "soulseek",
        "download_id": download.id,
        "track_id": track.id,
    }
)
```

### 14.2 Metrics

**Module Metrics:**
```python
# Track module performance
class MetricsCollector:
    def record_download_started(self):
        """Record download metric."""
        self._downloads_started.inc()
    
    def record_download_duration(self, duration_seconds: float):
        """Record download duration."""
        self._download_duration.observe(duration_seconds)
```

### 14.3 Health Checks

**Module Health:**
```python
@router.get("/health")
async def health_check(service: DownloadService = Depends()):
    """Module health check."""
    try:
        # Check critical dependencies
        await service.ping_slskd()
        return {"status": "healthy", "module": "soulseek"}
    except Exception as e:
        return {
            "status": "unhealthy",
            "module": "soulseek",
            "error": str(e)
        }
```

---

## 15. Conclusion

This modular architecture provides a solid foundation for SoulSpot's growth while maintaining code quality, testability, and developer experience. Each module is:

- **Self-contained**: All related code in one place
- **Testable**: Clear boundaries enable isolation
- **Maintainable**: Easy to understand and modify
- **Scalable**: New features = new modules
- **Flexible**: Modules can evolve independently

The Soulseek module serves as the **reference implementation** demonstrating all patterns and best practices defined in this specification.

---

**Related Documents:**
- [Roadmap](./ROADMAP.md)
- [Module Specification](./MODULE_SPECIFICATION.md)
- [Soulseek Module Design](./SOULSEEK_MODULE.md)
- [Module Communication Patterns](./MODULE_COMMUNICATION.md)

**Status:** 🔄 In Progress - Planning Phase
