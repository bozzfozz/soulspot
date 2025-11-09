# Changelog

All notable changes to the SoulSpot Bridge project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Production deployment configuration
- CI/CD pipeline setup
- Observability (Logging, Metrics, Tracing)
- Performance optimization
- Additional UI features and improvements

## [0.1.0] - 2025-11-08

### Added - Phase 5: Web UI & API Integration

#### Web UI Components
- Complete web-based user interface with Jinja2 templates
- Modern responsive design using Tailwind CSS
- HTMX for dynamic interactions without heavy JavaScript
- Dashboard with real-time statistics
- Playlist management interface
- Downloads monitoring page
- OAuth authentication flow UI

#### REST API Endpoints
- Authentication endpoints (`/api/v1/auth/*`)
  - OAuth authorization flow
  - Token refresh mechanism
  - Session management
- Playlist endpoints (`/api/v1/playlists/*`)
  - Import Spotify playlists
  - List and view playlists
  - Track management
- Download endpoints (`/api/v1/downloads/*`)
  - Download status monitoring
  - Download queue management
- Track endpoints (`/api/v1/tracks/*`)
  - Track search and retrieval

#### Session Management
- Secure server-side session storage
- Cookie-based session tracking with CSRF protection
- Automatic session cleanup
- Token persistence across requests

#### Testing
- 56 new unit tests for Phase 4 components
- 7 integration tests for API endpoints
- Total: 228 tests with 100% pass rate
- Comprehensive test coverage for use cases, caching, and workers

### Fixed
- Migrated from deprecated `datetime.utcnow()` to `datetime.now(UTC)` (87% reduction in warnings)
- Fixed 21 failing integration tests by adding missing pytest-mock dependency
- Resolved OAuth token persistence issues
- Fixed API endpoints that were returning placeholder data

### Changed
- UI routes now display real data from repositories instead of hardcoded values
- Improved dependency injection in API routers
- Enhanced error handling across all API endpoints

## [0.0.4] - 2025-11-08

### Added - Phase 4: Application Layer

#### Use Cases (Business Logic)
- **Import Spotify Playlist** - Complete playlist import workflow
  - Fetch playlist metadata from Spotify
  - Create/update playlist entities
  - Import tracks and artists
  - Handle duplicates and conflicts
- **Enrich Track Metadata** - Metadata enhancement workflow
  - Search MusicBrainz by ISRC
  - Fallback to title/artist search
  - Fetch album and artist information
  - Download and optimize cover art

#### Application Services
- **Token Manager Service** - OAuth token lifecycle management
  - Token expiration checking
  - Automatic token refresh
  - Multi-user token storage
  - Thread-safe operations
- **Session Store Service** - Session persistence
  - In-memory session storage
  - Automatic expiration
  - Session data serialization

#### Worker System
- **Job Queue System** - Asynchronous task processing
  - In-memory job queue (simple profile)
  - Job status tracking (PENDING → RUNNING → COMPLETED/FAILED)
  - Job handlers registration
  - Retry logic with exponential backoff
  - Concurrent job processing

#### Caching Layer
- **Base Cache** - Generic in-memory caching
  - TTL support with automatic cleanup
  - LRU eviction (optional)
  - Cache statistics
- **Spotify Cache** - Spotify API response caching
  - Track, playlist, and search result caching
  - Selective invalidation
- **MusicBrainz Cache** - MusicBrainz API response caching
  - Recording, release, and artist caching
  - ISRC-based lookups
- **Track File Cache** - Track file path caching
  - Fast file existence checks
  - Path resolution optimization

### Technical
- Full async/await support throughout application layer
- Comprehensive error handling with domain exceptions
- Clean architecture with dependency inversion
- 100% type-safe with mypy strict mode
- Dataclass-based request/response patterns

## [0.0.3] - 2025-11-08

### Added - Phase 3: External Integrations

#### Domain Ports
- `ISlskdClient` - Soulseek download operations interface
- `ISpotifyClient` - Spotify API operations interface with OAuth PKCE
- `IMusicBrainzClient` - MusicBrainz metadata operations interface

#### slskd Client
- Async HTTP client for slskd API
- Search functionality with customizable timeout
- Download management (start, monitor, cancel)
- Authentication support (API key and basic auth)
- Comprehensive error handling
- Context manager support for resource cleanup

#### Spotify Client
- Full OAuth 2.0 PKCE implementation
- Authorization URL generation with PKCE challenge
- Token exchange and refresh
- Playlist and track retrieval
- Search functionality
- Rate limiting and retry logic
- Token management with expiration handling

#### MusicBrainz Client
- Recording lookup by ISRC
- Recording search by artist and title
- Release (album) lookup
- Artist lookup
- Rate limiting (1 request/second)
- User-Agent identification
- Retry logic with exponential backoff

#### Testing
- 91 unit tests for all integration clients
- Mock-based testing with pytest-httpx
- Comprehensive error scenario coverage
- OAuth flow testing
- Rate limiting validation

### Technical
- Full async/await implementation
- httpx for HTTP operations
- Proper resource management
- Extensive error handling
- Type-safe implementations

## [0.0.2] - 2025-11-08

### Added - Phase 2: Core Infrastructure

#### Settings Management
- Pydantic-based configuration system
- Profile support (simple/standard)
- Environment variable support with nested delimiter
- Validation for production secrets and ports
- Automatic path resolution for storage directories
- Configuration models:
  - DatabaseSettings
  - SlskdSettings
  - SpotifySettings
  - MusicBrainzSettings
  - StorageSettings
  - APISettings

#### Database Layer
- SQLAlchemy 2.0 async models
- Database models for all domain entities:
  - ArtistModel
  - AlbumModel
  - TrackModel
  - PlaylistModel
  - PlaylistTrackModel
  - DownloadModel
- Repository pattern implementations
- Async database operations
- Connection pooling
- Transaction management

#### FastAPI Application
- Application entry point (`main.py`)
- Health check endpoints
- Readiness checks
- CORS configuration
- Lifespan management
- API documentation (OpenAPI/Swagger)

#### Database Migrations
- Alembic configuration
- Initial migration script
- Schema version management
- Migration templates

### Technical
- SQLite support (simple profile)
- PostgreSQL support (standard profile)
- Async database operations throughout
- Proper dependency injection
- Type-safe configurations

## [0.0.1] - 2025-11-08

### Added - Phase 1: Foundation

#### Project Setup
- Poetry-based dependency management
- Python 3.12+ requirement
- Development tooling configuration:
  - Ruff for linting and formatting
  - Mypy for type checking
  - Bandit for security scanning
  - Pytest for testing
- Pre-commit hooks
- Git configuration
- Docker Compose environment
- Makefile and Justfile for common tasks

#### Domain Layer
- Core domain entities:
  - Artist - Music artist entity
  - Album - Music album entity
  - Track - Music track entity
  - Playlist - Track collection entity
  - Download - Download operation entity
- Value objects:
  - ArtistId, AlbumId, TrackId, PlaylistId, DownloadId
  - FilePath - Validated file path wrapper
  - SpotifyUri - Spotify URI parser and validator
- Domain exceptions:
  - DomainException (base)
  - EntityNotFoundException
  - ValidationException
  - InvalidStateException
  - DuplicateEntityException
- Repository interfaces (ports):
  - IArtistRepository
  - IAlbumRepository
  - ITrackRepository
  - IPlaylistRepository
  - IDownloadRepository

#### Docker Environment
- slskd service configuration
- Volume management for downloads and music
- Health checks
- Networking setup

#### Testing Infrastructure
- Unit test framework with pytest
- Test fixtures and configuration
- Domain entity tests (20+ test cases)
- Value object tests
- 100% test pass rate

#### Documentation
- Comprehensive architecture documentation
- Style guide and design system
- Initial assessment and planning documents
- Issue templates for GitHub
- Development workflow documentation

### Technical
- Layered architecture (Domain, Application, Infrastructure, Presentation)
- Dependency Inversion Principle throughout
- SOLID principles compliance
- Domain-Driven Design (tactical patterns)
- Type safety with full type hints
- Immutable value objects

## Project Initialization - 2025-11-04

### Added
- Initial repository structure
- Project documentation planning
- Architecture design
- Style guide definition

---

## Version History Summary

| Version | Date | Focus | Status |
|---------|------|-------|--------|
| 0.1.0 | 2025-11-08 | Web UI & API Integration | ✅ Complete |
| 0.0.4 | 2025-11-08 | Application Layer | ✅ Complete |
| 0.0.3 | 2025-11-08 | External Integrations | ✅ Complete |
| 0.0.2 | 2025-11-08 | Core Infrastructure | ✅ Complete |
| 0.0.1 | 2025-11-08 | Foundation | ✅ Complete |

---

[Unreleased]: https://github.com/bozzfozz/soulspot-bridge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bozzfozz/soulspot-bridge/releases/tag/v0.1.0
[0.0.4]: https://github.com/bozzfozz/soulspot-bridge/releases/tag/v0.0.4
[0.0.3]: https://github.com/bozzfozz/soulspot-bridge/releases/tag/v0.0.3
[0.0.2]: https://github.com/bozzfozz/soulspot-bridge/releases/tag/v0.0.2
[0.0.1]: https://github.com/bozzfozz/soulspot-bridge/releases/tag/v0.0.1
