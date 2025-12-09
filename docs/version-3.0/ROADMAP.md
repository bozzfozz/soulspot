# SoulSpot - Modular Architecture Roadmap (Version 3.0)

> **⚠️ DEPRECATED - UNREALIZED VISION:** This roadmap describes a modular architecture that was **never implemented**. Current production (v0.1.0) uses Hexagonal Architecture. See `docs/development/backend-roadmap.md` and `docs/development/frontend-roadmap.md` for active roadmaps.

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

**Version:** 3.0.0  
**Status:** ~~Planning Phase~~ UNREALIZED PROPOSAL  
**Last Updated:** 2025-11-21  
**Author:** Integration Orchestrator Agent

---

## 1. Executive Summary

This roadmap outlines the transition from the current layered/onion architecture to a **fully modular, feature-based architecture** for SoulSpot. Each feature module (e.g., Soulseek, Spotify, Library Management) will become a self-contained component with its own frontend, backend, and tests, enabling:

- **Independent Development**: Modules can be developed, tested, and deployed independently
- **Clear Boundaries**: Well-defined interfaces between modules prevent coupling
- **Scalability**: New features can be added as new modules without affecting existing code
- **Maintainability**: Module isolation makes debugging and maintenance easier
- **Team Collaboration**: Different developers/teams can work on different modules in parallel

---

## 2. Current Architecture Analysis

### 2.1 Current State (Version 2.x)

**Structure:**
```
src/soulspot/
├── api/                    # Presentation Layer (FastAPI routers)
├── application/            # Application Layer (services, use-cases)
├── domain/                 # Domain Layer (entities, value objects)
├── infrastructure/         # Infrastructure Layer (integrations, persistence)
├── templates/              # Frontend templates (HTMX)
└── static/                 # Frontend assets (CSS, JS)
```

**Characteristics:**
- ✅ Clear layered separation (API → Application → Domain → Infrastructure)
- ✅ Dependency Inversion Principle (ports/interfaces)
- ✅ SOLID principles applied
- ✅ Strong type safety (mypy strict mode)
- ⚠️ All features mixed in same layer folders
- ⚠️ Frontend/Backend tightly coupled at folder level
- ⚠️ Difficult to understand feature scope boundaries
- ⚠️ Hard to run/test individual features in isolation

### 2.2 Current Integration Points

**Existing Integrations:**
- Spotify API (`infrastructure/integrations/spotify_client.py`)
- Soulseek/slskd API (`infrastructure/integrations/slskd_client.py`)
- MusicBrainz API (`infrastructure/integrations/musicbrainz_client.py`)
- Last.fm API (`infrastructure/integrations/lastfm_client.py`)

**Current Communication:**
- Direct service-to-service calls within same process
- Shared database (SQLite) for all features
- No formal module boundaries or contracts

---

## 3. Target Architecture (Version 3.0)

### 3.1 Modular Design Principles

**Core Principles:**
1. **Feature-Based Modules**: Each major feature is a self-contained module
2. **Vertical Slicing**: Modules contain full stack (Frontend + Backend + Tests)
3. **Explicit Contracts**: Modules communicate only through well-defined interfaces
4. **Independent Lifecycle**: Modules can be developed, tested, and versioned independently
5. **Clean Architecture**: Maintain layered architecture within modules (API → Application → Domain → Infrastructure)

### 3.2 Module Structure Template

```
modules/
├── {module_name}/                  # e.g., soulseek, spotify, library
│   ├── README.md                   # Module documentation
│   ├── __init__.py                 # Module exports and metadata
│   │
│   ├── frontend/                   # Frontend components (HTMX)
│   │   ├── pages/                  # Full page templates
│   │   ├── widgets/                # Reusable UI components
│   │   ├── partials/               # Template fragments
│   │   ├── styles/                 # Module-specific CSS
│   │   └── scripts/                # Module-specific JavaScript
│   │
│   ├── backend/                    # Backend implementation
│   │   ├── api/                    # Module routes (FastAPI)
│   │   │   ├── routes.py           # HTTP endpoints
│   │   │   └── schemas.py          # Request/Response schemas
│   │   ├── application/            # Application layer
│   │   │   ├── services/           # Business logic orchestration
│   │   │   ├── use_cases/          # Command/Query handlers
│   │   │   └── dto/                # Data Transfer Objects
│   │   ├── domain/                 # Domain layer
│   │   │   ├── entities/           # Domain entities
│   │   │   ├── value_objects/      # Value objects
│   │   │   ├── services/           # Domain services
│   │   │   ├── events/             # Domain events
│   │   │   └── ports/              # Interface definitions
│   │   ├── infrastructure/         # Infrastructure layer
│   │   │   ├── persistence/        # Database models & repos
│   │   │   ├── integrations/       # External API clients
│   │   │   └── adapters/           # Port implementations
│   │   └── config/                 # Module configuration
│   │       └── settings.py         # Module-specific settings
│   │
│   ├── tests/                      # Module tests
│   │   ├── unit/                   # Unit tests
│   │   ├── integration/            # Integration tests
│   │   └── fixtures/               # Test fixtures
│   │
│   └── contracts/                  # Module contracts (future)
│       ├── api.yaml                # OpenAPI spec
│       ├── events.yaml             # Event schema definitions
│       └── dependencies.yaml       # Module dependencies
```

### 3.3 Module Categories

**Core Modules** (Essential functionality):
- `core`: Shared utilities, base classes, common models
- `auth`: Authentication and authorization
- `database`: Database management and migrations

**Feature Modules** (Business features):
- `soulseek`: Soulseek download management
- `spotify`: Spotify playlist synchronization
- `library`: Music library management
- `metadata`: Metadata enrichment (MusicBrainz, Last.fm)
- `automation`: Automated download workflows
- `dashboard`: Main dashboard and overview

**Infrastructure Modules** (Technical features):
- `notifications`: Notification system (SSE, websockets)
- `settings`: Application settings management
- `monitoring`: Health checks, metrics, logging

---

## 4. Migration Strategy

### 4.1 Phased Migration Approach

**Phase 1: Foundation (Week 1-2)**
- ✅ Create documentation structure (`docs/version-3.0/`)
- ✅ Define module specification and contracts
- ✅ Design example module (Soulseek)
- 🔄 Create `modules/` directory structure
- 🔄 Implement core module (shared utilities)

**Phase 2: Pilot Module - Soulseek (Week 3-4)**
- Extract Soulseek-related code into module structure
- Migrate backend: slskd_client, download services, routes
- Migrate frontend: download pages, widgets, partials
- Migrate tests: unit and integration tests
- Document learnings and refine module template

**Phase 3: Additional Modules (Week 5-8)**
- Spotify module migration
- Library module migration
- Metadata module migration
- Dashboard module consolidation

**Phase 4: Module Communication (Week 9-10)**
- Implement event bus system
- Define module API contracts
- Implement inter-module communication
- Add module registry and discovery

**Phase 5: Legacy Cleanup (Week 11-12)**
- Remove old layered structure
- Update all documentation
- Performance testing and optimization
- Security audit and review

### 4.2 Development Strategy

**Separate Branch Development:**
- Version 3.0 will be developed in a dedicated branch (e.g., `version-3.0`)
- No need to maintain backwards compatibility during development
- Clean slate migration without running both architectures in parallel
- Allows for complete restructuring without constraints

**After Completion:**
- Major version release (v3.0.0)
- Provide comprehensive migration guides for users
- Document breaking changes and upgrade path
- Consider data migration scripts if database schema changes significantly

---

## 5. Module Communication Architecture

### 5.1 Communication Patterns (Future Implementation)

**Synchronous Communication:**
```python
# Direct API calls between modules (within same process)
from modules.spotify.backend.api.client import SpotifyModuleClient

spotify = SpotifyModuleClient()
playlists = await spotify.get_playlists(user_id="123")
```

**Asynchronous Communication:**
```python
# Event-based communication
from core.events import EventBus

# Module A publishes
await event_bus.publish(
    event="track.downloaded",
    data={"track_id": "abc123", "path": "/music/track.mp3"}
)

# Module B subscribes
@event_bus.subscribe("track.downloaded")
async def on_track_downloaded(event: TrackDownloadedEvent):
    await metadata_service.enrich(event.track_id)
```

**Request-Response (RPC-style):**
```python
# Module queries
from core.module_registry import module_registry

result = await module_registry.query(
    module="library",
    operation="search_tracks",
    params={"query": "Beatles", "limit": 10}
)
```

### 5.2 Event Bus Design (Conceptual)

**Core Components:**
- **Event Bus**: Central message broker (in-memory or Redis-backed)
- **Event Schema Registry**: Typed event definitions with versioning
- **Module Registry**: Discovery service for available modules
- **Contract Validator**: Ensures events match schemas

**Event Types:**
```yaml
# Example event schema
events:
  track.downloaded:
    version: 1.0.0
    producer: soulseek
    consumers: [metadata, library]
    schema:
      track_id: string
      file_path: string
      download_time: datetime
      
  playlist.synced:
    version: 1.0.0
    producer: spotify
    consumers: [soulseek, dashboard]
    schema:
      playlist_id: string
      track_count: integer
      new_tracks: array[string]
```

### 5.3 Module Router / Orchestrator

**Purpose:**  
The Module Router acts as an intelligent coordinator that routes requests to appropriate modules, handles module availability, and ensures graceful degradation when modules are missing.

**Key Features:**
- **Capability Discovery**: Automatically identifies which modules can handle specific operations
- **Request Routing**: Routes requests to capable modules based on priority and availability
- **Health Monitoring**: Tracks module status and availability in real-time
- **Standalone Operation**: Modules can run independently, router handles missing dependencies
- **Clear Warnings**: Logs, Docker logs, and UI show clear messages when modules are unavailable

**Example Flow:**
```python
# User searches for a song
search_results = await module_router.route_request(
    operation="search.track",
    params={"query": "Beatles - Let It Be"}
)
# Router finds Spotify module is available and routes to it

# User initiates download
download = await module_router.route_request(
    operation="download.track",
    params={"track_id": "spotify:123", "track_info": {...}}
)
# Router checks: Soulseek module available? Yes → routes download
# If Soulseek unavailable: logs warning, shows in UI, fails gracefully
```

**Missing Module Handling:**
```python
# Module unavailable - clear warning in logs
⚠️  MISSING MODULE WARNING ⚠️
Operation 'download.track' requires one of these modules:
  soulseek, youtube-dl
Inactive modules: soulseek
Please enable required modules to use this feature.

# Also displayed in UI dashboard
[Module Status Widget]
❌ Soulseek - INACTIVE
   Impact: Download functionality unavailable
   Action: Enable Soulseek module to download tracks
```

### 5.4 Module Dependencies

**Dependency Declaration:**
```yaml
# modules/soulseek/contracts/dependencies.yaml
module: soulseek
version: 1.0.0

dependencies:
  core:
    version: ">=1.0.0"
    required: true
  
  metadata:
    version: ">=1.0.0"
    required: false
    features: [enrich_on_download]
  
  library:
    version: ">=1.0.0"
    required: true

provides:
  events:
    - track.downloaded
    - download.started
    - download.failed
  
  api:
    - POST /downloads/start
    - GET /downloads/{id}
    - GET /downloads/status
```

---

## 6. Module Development Guidelines

### 6.1 Module Checklist

**Every Module Must Have:**
- [ ] README.md with purpose, features, and usage
- [ ] Clear frontend/backend separation
- [ ] Complete test coverage (unit + integration)
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Event schema definitions (if produces events)
- [ ] Configuration schema (Pydantic settings)
- [ ] Migration guide (if migrated from old code)
- [ ] Health check endpoint
- [ ] Metrics and logging integration

### 6.2 Naming Conventions

**Modules:**
- Use lowercase with underscores: `soulseek`, `music_library`
- Short, descriptive names: max 20 characters
- Avoid abbreviations unless widely known

**Routes:**
```python
# Module routes are prefixed with module name
# modules/soulseek/backend/api/routes.py

router = APIRouter(prefix="/soulseek", tags=["soulseek"])

@router.get("/downloads")           # -> GET /soulseek/downloads
@router.post("/downloads/start")    # -> POST /soulseek/downloads/start
@router.get("/downloads/{id}")      # -> GET /soulseek/downloads/{id}
```

**Templates:**
```
# Module templates use module prefix
modules/soulseek/frontend/pages/downloads.html
modules/soulseek/frontend/widgets/download_status.html
modules/soulseek/frontend/partials/download_item.html
```

**Tests:**
```python
# Test modules mirror structure
modules/soulseek/tests/unit/test_download_service.py
modules/soulseek/tests/integration/test_slskd_integration.py
```

### 6.3 Module Independence Rules

**DO:**
- ✅ Keep all module logic within module boundaries
- ✅ Use dependency injection for external services
- ✅ Define clear contracts (interfaces/protocols)
- ✅ Use events for loose coupling
- ✅ Make modules testable in isolation
- ✅ Version module APIs and events
- ✅ Use submodules for complex functionality separation

**DON'T:**
- ❌ Import directly from other modules' implementation
- ❌ Share mutable state across modules
- ❌ Hardcode dependencies on specific modules
- ❌ Mix frontend and backend in same files
- ❌ Skip tests or documentation
- ❌ Break module boundaries for "quick fixes"

### 6.4 Submodules

**When to Use Submodules:**
- Complex authentication/authorization logic (OAuth, JWT, etc.)
- Webhook handling that's separate from main API
- Admin/management interfaces separate from user features
- Storage/caching layers
- Background job processing

**Example: Spotify Module with Auth Submodule**

```
modules/spotify/
├── README.md                       # ✅ Parent module
├── CHANGELOG.md                    # ✅ Parent changelog
├── docs/                           # ✅ Parent docs
├── submodules/
│   └── auth/                       # OAuth authentication submodule
│       ├── README.md               # ✅ Submodule docs
│       ├── CHANGELOG.md            # ✅ Submodule changelog
│       ├── docs/                   # ✅ Submodule docs
│       ├── backend/
│       │   ├── api/routes.py       # /spotify/auth/* endpoints
│       │   ├── application/
│       │   │   └── services/token_service.py
│       │   └── domain/
│       │       └── entities/oauth_token.py
│       └── tests/
├── backend/                        # Main Spotify module
│   └── infrastructure/
│       └── spotify_client.py       # Uses auth submodule
└── frontend/
```

**Submodule Benefits:**
- Clear separation of cross-cutting concerns
- Independent testing and versioning
- Reusable across modules
- Optional enablement (disable auth submodule if not needed)

### 6.5 Documentation & Changelog Requirements

**Module Documentation (REQUIRED):**

Each module and submodule MUST have:

1. **CHANGELOG.md** - Module-specific version history
   - Located in module/submodule root directory
   - Follows [Keep a Changelog](https://keepachangelog.com/) format
   - Independent versioning from global changelog
   - Tracks module-specific breaking changes

2. **docs/** directory - Complete module documentation
   - **architecture.md**: Design decisions, component diagrams
   - **api.md**: Complete API documentation
   - **events.md**: Event schemas and contracts
   - **configuration.md**: Configuration guide
   - **development.md**: Development and contribution guide

**Location Rules:**

```
✅ Correct:
modules/soulseek/CHANGELOG.md
modules/soulseek/docs/architecture.md
modules/spotify/submodules/auth/CHANGELOG.md
modules/spotify/submodules/auth/docs/oauth-flow.md

❌ Wrong:
docs/modules/soulseek/CHANGELOG.md        # Don't put in global docs
CHANGELOG.md (only global)                # Module needs its own
modules/soulseek/architecture.md          # Must be in docs/ subdirectory
```

**Global vs. Module Changelog:**

- **Global CHANGELOG.md** (repo root):
  - System-level changes
  - Version 3.0 milestone releases
  - Cross-module breaking changes
  - Infrastructure updates

- **Module CHANGELOG.md** (modules/{name}/):
  - Module-specific features/fixes
  - Module version updates (independent SemVer)
  - Module API changes
  - Module event schema changes

**Example: Global Changelog Entry**

```markdown
# Changelog - SoulSpot

## [3.0.0] - 2025-12-01

### Added
- Modular architecture with feature-based modules
- Module Router for intelligent coordination
- Event bus for inter-module communication

### Modules Introduced
- Soulseek v1.0.0 - Download management
- Spotify v1.0.0 - Playlist sync with auth submodule
- Library v1.0.0 - Music library management
```

**Example: Module Changelog Entry**

```markdown
# Changelog - Soulseek Module

## [1.1.0] - 2025-12-15

### Added
- Batch download support
- BitRate filtering in search

### Fixed
- Race condition in concurrent downloads
```

**Why Separate Changelogs?**

1. **Module Independence**: Modules version independently
2. **Clear Ownership**: Each team maintains their module's changelog
3. **Release Flexibility**: Modules can release without system-wide release
4. **Migration Tracking**: Module-specific migration guides
5. **Modularity**: Extracted modules carry their history

---

## 7. Example: Soulseek Module

### 7.1 Module Scope

**Purpose:**  
Manage all Soulseek-related functionality including search, downloads, and slskd integration.

**Features:**
- Search tracks on Soulseek network
- Queue and manage downloads
- Monitor download progress
- Manage slskd connection and settings
- Handle download completion and post-processing

**Boundaries:**
- **Owns**: Download queue, slskd integration, download status
- **Uses**: Metadata module (track enrichment), Library module (file management)
- **Provides**: Download events, download API

### 7.2 Soulseek Module Components

**Frontend Components:**
```
modules/soulseek/frontend/
├── pages/
│   ├── downloads.html          # Main downloads page
│   ├── search.html             # Search interface
│   └── settings.html           # slskd settings
├── widgets/
│   ├── download_queue.html     # Download queue widget
│   ├── download_status.html    # Single download status
│   └── search_results.html     # Search results widget
├── partials/
│   ├── download_item.html      # Download list item
│   └── progress_bar.html       # Progress indicator
└── styles/
    └── soulseek.css            # Module-specific styles
```

**Backend Components:**
```
modules/soulseek/backend/
├── api/
│   ├── routes.py               # FastAPI routes
│   └── schemas.py              # Pydantic schemas
├── application/
│   ├── services/
│   │   ├── download_service.py     # Download orchestration
│   │   └── search_service.py       # Search orchestration
│   └── use_cases/
│       ├── start_download.py       # Download command
│       └── search_tracks.py        # Search query
├── domain/
│   ├── entities/
│   │   ├── download.py             # Download entity
│   │   └── search_result.py        # Search result
│   ├── value_objects/
│   │   ├── download_status.py      # Status enum
│   │   └── file_quality.py         # Quality value object
│   └── ports/
│       └── slskd_port.py           # ISlskdClient interface
├── infrastructure/
│   ├── persistence/
│   │   ├── models.py               # SQLAlchemy models
│   │   └── repositories.py         # Repository implementations
│   └── integrations/
│       └── slskd_client.py         # slskd API client
└── config/
    └── settings.py                 # Module settings
```

**Tests:**
```
modules/soulseek/tests/
├── unit/
│   ├── test_download_service.py
│   ├── test_search_service.py
│   └── test_download_entity.py
├── integration/
│   ├── test_slskd_integration.py
│   └── test_download_flow.py
└── fixtures/
    ├── download_fixtures.py
    └── slskd_mock_responses.py
```

### 7.3 Soulseek Module Contracts

**API Endpoints:**
```python
# modules/soulseek/backend/api/routes.py

# Search
POST   /soulseek/search              # Search for tracks
GET    /soulseek/search/{search_id}  # Get search results

# Downloads
POST   /soulseek/downloads            # Start download
GET    /soulseek/downloads            # List downloads
GET    /soulseek/downloads/{id}       # Get download status
DELETE /soulseek/downloads/{id}       # Cancel download
PATCH  /soulseek/downloads/{id}       # Update download

# Settings
GET    /soulseek/settings             # Get slskd settings
PUT    /soulseek/settings             # Update slskd settings
GET    /soulseek/health               # Health check
```

**Events Published:**
```yaml
# modules/soulseek/contracts/events.yaml

events:
  download.started:
    version: 1.0.0
    data:
      download_id: string
      track_id: string
      user: string
      filename: string
  
  download.progress:
    version: 1.0.0
    data:
      download_id: string
      percent_complete: float
      bytes_transferred: integer
  
  download.completed:
    version: 1.0.0
    data:
      download_id: string
      track_id: string
      file_path: string
      duration_seconds: float
  
  download.failed:
    version: 1.0.0
    data:
      download_id: string
      track_id: string
      error: string
      retry_count: integer
```

**Events Consumed:**
```yaml
# From other modules
consumes:
  - track.metadata_enriched       # From metadata module
  - library.file_moved            # From library module
```

---

## 8. Integration Patterns

### 8.1 Frontend Integration

**Module Registration in Main App:**
```python
# src/soulspot/main.py

from modules.soulseek.backend.api.routes import router as soulseek_router
from modules.spotify.backend.api.routes import router as spotify_router

app = FastAPI()

# Register module routers
app.include_router(soulseek_router)
app.include_router(spotify_router)

# Register module templates
app.mount("/soulseek/static", StaticFiles(directory="modules/soulseek/frontend/styles"))
```

**Template Inheritance:**
```html
<!-- modules/soulseek/frontend/pages/downloads.html -->
{% extends "layouts/base.html" %}  {# From core #}

{% block title %}Soulseek Downloads{% endblock %}

{% block content %}
  {% include "modules/soulseek/frontend/widgets/download_queue.html" %}
{% endblock %}
```

### 8.2 Backend Integration

**Service Registration:**
```python
# core/module_registry.py

from modules.soulseek.backend.application.services import DownloadService
from modules.metadata.backend.application.services import MetadataService

class ModuleRegistry:
    def __init__(self):
        self._services = {}
    
    def register(self, name: str, service: Any) -> None:
        self._services[name] = service
    
    def get(self, name: str) -> Any:
        return self._services.get(name)

# Usage in module
registry.register("downloads", DownloadService())
registry.register("metadata", MetadataService())
```

**Cross-Module Service Calls:**
```python
# modules/soulseek/backend/application/services/download_service.py

from core.module_registry import module_registry

class DownloadService:
    async def on_download_complete(self, download_id: str):
        # Get file info
        download = await self.get_download(download_id)
        
        # Call metadata module to enrich
        metadata_service = module_registry.get("metadata")
        await metadata_service.enrich_track(download.file_path)
        
        # Call library module to organize
        library_service = module_registry.get("library")
        await library_service.import_file(download.file_path)
```

---

## 9. Testing Strategy

### 9.1 Module Testing Levels

**Unit Tests** (Fast, isolated):
```python
# modules/soulseek/tests/unit/test_download_service.py

async def test_start_download_creates_download_entity():
    # Arrange
    service = DownloadService(mock_repo, mock_slskd)
    
    # Act
    download = await service.start_download(track_id="123")
    
    # Assert
    assert download.status == DownloadStatus.QUEUED
```

**Integration Tests** (Module boundaries):
```python
# modules/soulseek/tests/integration/test_download_flow.py

async def test_download_completion_triggers_metadata_enrichment():
    # Arrange
    event_bus = TestEventBus()
    
    # Act
    await download_service.complete_download("dl-123")
    
    # Assert
    events = event_bus.get_events("download.completed")
    assert len(events) == 1
```

**Module Tests** (Full module):
```python
# modules/soulseek/tests/test_module.py

async def test_module_can_start_standalone(test_client):
    # Test that module works without other modules
    response = await test_client.get("/soulseek/health")
    assert response.status_code == 200
```

### 9.2 Testing Conventions

**Test Organization:**
- Mirror module structure in tests/
- One test file per source file
- Group related tests in classes
- Use descriptive test names: `test_<what>_<when>_<expected>`

**Test Data:**
- Use factory_boy for test data generation
- Store fixtures in `tests/fixtures/`
- Use realistic but synthetic data
- Never use production data in tests

**Mocking:**
- Mock external services at module boundaries
- Use dependency injection for testability
- Prefer pytest-mock over unittest.mock
- Create reusable mock fixtures

---

## 10. Documentation Requirements

### 10.1 Module README Template

```markdown
# {Module Name} Module

## Purpose
Brief description of module purpose and scope.

## Features
- Feature 1
- Feature 2
- Feature 3

## Architecture
Diagram or description of internal architecture.

## API Reference
Link to OpenAPI documentation or inline API docs.

## Events
List of events published and consumed.

## Configuration
Required settings and environment variables.

## Dependencies
Other modules this module depends on.

## Testing
How to run module tests.

## Development
Local development setup and guidelines.

## Migration Notes
How this module relates to previous code (if migrated).
```

### 10.2 Documentation Files Per Module

**Required:**
- `README.md` - Module overview
- `API.md` - API documentation
- `ARCHITECTURE.md` - Internal design
- `TESTING.md` - Testing guide

**Optional:**
- `MIGRATION.md` - Migration from old code
- `TROUBLESHOOTING.md` - Common issues
- `EXAMPLES.md` - Usage examples

---

## 11. Timeline and Milestones

### 11.1 Detailed Timeline

**Milestone 1: Planning & Design** (Week 1-2)
- ✅ Create roadmap document
- ✅ Define module specification
- 🔄 Design Soulseek example module
- 🔄 Review and approval

**Milestone 2: Infrastructure** (Week 3)
- Create modules/ directory structure
- Implement core module
- Set up module registry
- Create module template generator

**Milestone 3: Soulseek Pilot** (Week 4-5)
- Migrate Soulseek backend
- Migrate Soulseek frontend
- Migrate Soulseek tests
- Document migration learnings

**Milestone 4: Core Modules** (Week 6-8)
- Migrate Spotify module
- Migrate Library module
- Migrate Metadata module
- Update documentation

**Milestone 5: Communication** (Week 9-10)
- Implement event bus
- Define event schemas
- Implement module contracts
- Integration testing

**Milestone 6: Finalization** (Week 11-12)
- Remove legacy code
- Performance optimization
- Security audit
- Documentation review
- Release preparation

### 11.2 Success Criteria

**Module Quality:**
- [ ] All modules pass lint/type/security checks
- [ ] Test coverage > 80% per module
- [ ] All APIs documented
- [ ] All events documented
- [ ] Health checks for all modules

**Architecture Quality:**
- [ ] Clear module boundaries
- [ ] No circular dependencies
- [ ] Well-defined contracts
- [ ] Event-driven communication works
- [ ] Modules can be tested in isolation

**Developer Experience:**
- [ ] Easy to create new modules
- [ ] Clear documentation
- [ ] Module template available
- [ ] Good examples (Soulseek)
- [ ] Migration guides

---

## 12. Risks and Mitigation

### 12.1 Technical Risks

**Risk: Breaking Changes During Migration**
- **Impact:** High
- **Probability:** Medium
- **Mitigation:**
  - Develop in separate branch (version-3.0)
  - Comprehensive testing before merge
  - Clear migration documentation
  - Communication plan for breaking changes

**Risk: Performance Degradation**
- **Impact:** Medium
- **Probability:** Low
- **Mitigation:**
  - Performance benchmarks before/after
  - Event bus optimization
  - Caching strategies
  - Load testing

**Risk: Increased Complexity**
- **Impact:** Medium
- **Probability:** Medium
- **Mitigation:**
  - Clear documentation
  - Developer training
  - Module templates
  - Code reviews

### 12.2 Organizational Risks

**Risk: Learning Curve**
- **Impact:** Medium
- **Probability:** High
- **Mitigation:**
  - Comprehensive documentation
  - Example module (Soulseek)
  - Pair programming sessions
  - Gradual adoption

**Risk: Scope Creep**
- **Impact:** High
- **Probability:** Medium
- **Mitigation:**
  - Strict scope per milestone
  - MVP approach per module
  - Regular reviews
  - Clear acceptance criteria

---

## 13. Future Enhancements

### 13.1 Module Ecosystem (Version 3.1+)

**Module Marketplace:**
- Third-party module support
- Module versioning and compatibility
- Module discovery and installation
- Community-contributed modules

**Advanced Module Features:**
- Hot module reloading
- Module lazy loading
- Module A/B testing
- Module feature flags

### 13.2 Tooling Improvements

**Developer Tools:**
- Module scaffolding CLI
- Module health dashboard
- Contract validation tools
- Module dependency visualizer

**CI/CD:**
- Per-module deployment
- Module versioning automation
- Automated compatibility checks
- Module performance monitoring

---

## 14. Conclusion

This modular architecture represents a significant evolution of SoulSpot, enabling:

1. **Better Organization**: Clear feature boundaries and responsibilities
2. **Easier Maintenance**: Isolated modules are easier to understand and modify
3. **Faster Development**: Parallel development on different modules
4. **Higher Quality**: Better testability and isolation
5. **Future Growth**: Easy addition of new features as modules

The Soulseek module serves as the **reference implementation** and template for all future modules, demonstrating best practices and patterns to follow.

---

## 15. UI/UX Design System

### 15.1 Card-Based UI Architecture

**Goal:** Replace widget-based UI with clean, card-based design system to prevent "UI garbage".

**Core Card Types (7 total):**
1. **Status Card**: Module/system health, connection status
2. **Action Card**: Search forms, triggers, quick actions
3. **Data Card**: Track info, album details, statistics
4. **Progress Card**: Download/sync progress indicators
5. **List Card**: Search results, queues, collections
6. **Alert Card**: Warnings, errors, notifications
7. **Form Card**: Configuration, settings, input collection

**Design Tokens:**
- Spacing scale: 4px base unit (4, 8, 16, 24, 32, 48px)
- Typography scale: 12px to 30px (rem-based)
- Semantic colors: Primary (blue), Success (green), Warning (yellow), Error (red)
- Dark mode support via CSS variables

**Benefits:**
- ✅ Consistent UI across all modules
- ✅ Prevents ad-hoc widget creation
- ✅ Accessibility built-in (WCAG 2.1 AA)
- ✅ HTMX-first integration patterns
- ✅ Responsive by default

**Complete Specification:** [UI_DESIGN_SYSTEM.md](./UI_DESIGN_SYSTEM.md)

---

## 16. Onboarding & Configuration

### 16.1 No .env Configuration

**Goal:** Remove .env files completely, replace with guided UI-based onboarding.

**Onboarding Steps:**
1. **Welcome Screen**: Introduction and expectations
2. **Spotify Configuration**: Collect credentials with real-time testing
3. **Soulseek Configuration**: slskd connection with validation
4. **Optional Modules**: MusicBrainz, Last.fm, Notifications
5. **Complete**: Summary and next steps

**Key Features:**
- ✅ **Real-time testing**: Test connections before saving
- ✅ **Secure storage**: Encrypted credentials in database (Fernet encryption)
- ✅ **Clear guidance**: Help modals with step-by-step credential guides
- ✅ **Migration support**: Auto-import from existing .env
- ✅ **Reconfiguration**: Easy post-setup credential updates

**Security:**
- All secrets encrypted at rest using Fernet symmetric encryption
- Database storage in `module_configurations` table
- No plaintext credentials on disk
- Audit trail for all credential access

**Benefits:**
- ✅ Zero configuration files for users
- ✅ Instant validation prevents setup errors
- ✅ First-time user success in &lt;5 minutes
- ✅ Clear error messages with actionable guidance

**Complete Specification:** [ONBOARDING_FLOW.md](./ONBOARDING_FLOW.md)

---

## 17. Implementation Timeline Update

### Phase 1: Foundation (Weeks 1-2)
- [ ] Core infrastructure (event bus, module registry, module router)
- [ ] **UI Design System**: Create card CSS framework and design tokens
- [ ] **Onboarding Flow**: Build wizard UI and secure credential storage
- [ ] Module scaffolding script
- [ ] Testing framework setup

### Phase 2: Pilot Module (Weeks 3-4)
- [ ] Soulseek module implementation (reference)
- [ ] **Soulseek UI**: Migrate to card-based design
- [ ] Module Router integration
- [ ] **First-run onboarding**: Soulseek credential collection
- [ ] Documentation generation
- [ ] E2E testing

### Phase 3: Core Modules (Weeks 5-8)
- [ ] Spotify module migration
- [ ] **Spotify UI**: Card-based search, playlists, player
- [ ] **Spotify onboarding**: OAuth credential flow
- [ ] Library module migration
- [ ] **Library UI**: Card-based browser and organizer
- [ ] Metadata module migration
- [ ] **Metadata UI**: Enrichment status cards

### Phase 4: Polish & Release (Weeks 9-12)
- [ ] **UI polish**: Dark mode, animations, responsive testing
- [ ] **Onboarding refinement**: Error messages, help content
- [ ] Migration guides for existing users
- [ ] Performance optimization
- [ ] Documentation completion
- [ ] Security audit
- [ ] **v3.0.0 release**

---

## 18. References

- [Architecture Specification](./ARCHITECTURE.md)
- [Module Specification](./MODULE_SPECIFICATION.md)
- [Soulseek Module Design](./SOULSEEK_MODULE.md)
- [Module Communication Patterns](./MODULE_COMMUNICATION.md)
- **[UI Design System](./UI_DESIGN_SYSTEM.md)** - NEW
- **[Onboarding Flow](./ONBOARDING_FLOW.md)** - NEW
- **[Architectural Lessons & Recommendations](./ARCHITECTURAL_LESSONS.md)** - NEW
- **[Adoption Recommendations](./ADOPTION_RECOMMENDATIONS.md)** - NEW
- [Current Architecture](../project/architecture.md)

---

**Next Steps:**
1. Review roadmap with stakeholders
2. Finalize UI card catalog and design tokens
3. Build onboarding flow prototype
4. Design Soulseek module UI mockups
5. Begin implementation with core infrastructure

**Status:** 🔄 In Progress - Documentation Phase Complete
