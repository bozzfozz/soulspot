# Changelog

**Category:** Project Management  
**Format:** [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
**Versioning:** [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

### Added
- **Box-Drawing Logs** - New structured log format using Unicode box-drawing characters for visual Worker → Service → Operation flow tracking
  - New `LogMessages.task_flow_*()` methods for consistent formatting
  - Cycle headers with worker name and cycle number
  - Provider-specific result logging (Spotify/Deezer)
  - Duration tracking for all tasks
  - See [Log Analysis Guide](../10-quality/log-analysis.md)

### Changed
- `UnifiedLibraryWorker` now uses Box-Drawing logs for all task execution
- Improved log readability with visual hierarchy

---

## [2.0.0] - 2025-01-06

### Documentation v2.0 Release

#### New API Documentation (26 files, 335 endpoints)

**Core API References:**
- [Authentication API](../01-api/auth.md) - OAuth 2.0, session management (9 endpoints)
- [Automation API](../01-api/automation.md) - Watchlists, discography, quality upgrades (20 endpoints)
- [Library API](../01-api/library.md) - Scan, import, duplicates, enrichment (35 endpoints)
- [Playlist API](../01-api/playlists.md) - Import, sync, blacklist (14 endpoints)
- [Downloads API](../01-api/downloads.md) - Queue management (14 endpoints)
- [Artists API](../01-api/artists.md) - CRUD, sync, followed artists (9 endpoints)
- [Tracks API](../01-api/tracks.md) - Download, enrich, metadata (5 endpoints)
- [Search API](../01-api/search.md) - Spotify/Soulseek search (5 endpoints)
- [Settings API](../01-api/settings.md) - App configuration (24 endpoints)
- [Metadata API](../01-api/metadata.md) - MusicBrainz/Spotify enrichment (6 endpoints)
- [Onboarding API](../01-api/onboarding.md) - First-run wizard (5 endpoints)
- [Compilations API](../01-api/compilations.md) - Compilation detection (7 endpoints)
- [Infrastructure API](../01-api/infrastructure.md) - Stats, artwork, SSE, workers (7 endpoints)
- [Blocklist API](../01-api/blocklist.md) - Track blocklist management (6 endpoints)
- [Quality Profiles API](../01-api/quality_profiles.md) - Quality preferences (6 endpoints)
- [Stats API](../01-api/stats.md) - Usage statistics (2 endpoints)
- [Workers API](../01-api/workers.md) - Background worker status (2 endpoints)

**Coverage:** 335/335 endpoints documented (100%)

#### Architecture Documentation (16 files)

**Core Architecture:**
- [Core Philosophy](../02-architecture/core-philosophy.md) - Multi-service aggregation, extensibility
- [Data Standards](../02-architecture/data-standards.md) - DTO definitions
- [Data Layer Patterns](../02-architecture/data-layer-patterns.md) - Entity/Repository/DTO patterns
- [Configuration](../02-architecture/configuration.md) - Database-first config
- [Plugin System](../02-architecture/plugin-system.md) - Multi-service plugins (Spotify/Deezer)
- [Error Handling](../02-architecture/error-handling.md) - 16 specialized exceptions
- [Auth Patterns](../02-architecture/auth-patterns.md) - OAuth flows
- [Worker Patterns](../02-architecture/worker-patterns.md) - Background jobs

**Planning & Optimization:**
- [Naming Conventions](../02-architecture/naming-conventions.md)
- [Service-Agnostic Backend](../02-architecture/service-agnostic-backend.md)
- [Database Schema](../02-architecture/database-schema-hybrid-library.md)
- [Transaction Patterns](../02-architecture/transaction-patterns.md)
- And 4 more optimization docs

#### Feature Documentation (19 files)

- [Authentication](../06-features/authentication.md) - OAuth flows
- [Spotify Sync](../06-features/spotify-sync.md) - Playlist/artist sync
- [Deezer Integration](../06-features/deezer-integration.md) - Multi-service support
- [Playlist Management](../06-features/playlist-management.md)
- [Followed Artists](../06-features/followed-artists.md)
- [Automation & Watchlists](../06-features/automation-watchlists.md)
- [Download Management](../06-features/download-management.md)
- [Auto-Import](../06-features/auto-import.md)
- [Track Management](../06-features/track-management.md)
- [Library Management](../06-features/library-management.md)
- [Metadata Enrichment](../06-features/metadata-enrichment.md)
- [Local Library Enrichment](../06-features/local-library-enrichment.md)
- [Album Completeness](../06-features/album-completeness.md)
- [Compilation Analysis](../06-features/compilation-analysis.md)
- [Batch Operations](../06-features/batch-operations.md)
- [Notifications](../06-features/notifications.md)
- [Settings](../06-features/settings.md)
- [Download Manager Roadmap](../06-features/download-manager-roadmap.md)

#### Library Documentation (9 files)

- [Lidarr Integration](../07-library/lidarr-integration.md) - Compatibility guide
- [Quality Profiles](../07-library/quality-profiles.md) - Quality tiers
- [Artwork Implementation](../07-library/artwork-implementation.md)
- [Naming Conventions](../07-library/naming-conventions.md)
- [Data Models](../07-library/data-models.md)
- [Workflows](../07-library/workflows.md)
- [UI Patterns](../07-library/ui-patterns.md)
- [API Reference](../07-library/api-reference.md)

#### UI Documentation (9 files)

- [UI Redesign Master Plan](../09-ui/feat-ui-pro.md) - 4-phase implementation
- [UI Architecture Principles](../09-ui/ui-architecture-principles.md) - Atomic Design
- [Component Library](../09-ui/component-library.md) - 50+ components
- [Accessibility Guide](../09-ui/accessibility-guide.md) - WCAG 2.1 AA
- [Quality Gates A11Y](../09-ui/quality-gates-a11y.md) - Testing framework
- [Service-Agnostic Strategy](../09-ui/service-agnostic-strategy.md) - Multi-service UI
- [UI Router Refactoring](../09-ui/ui-router-refactoring.md)
- [Library Artists View](../09-ui/library-artists-view.md)

#### Guide Documentation (19 files)

**User Guides:**
- Setup Guide, User Guide, Troubleshooting, Spotify Auth, Multi-Device Auth, Advanced Search

**Developer Guides:**
- Testing Guide, Deployment Guide, HTMX Patterns, Observability, Operations Runbook, Component Library, Design Guidelines, Page Reference, Style Guide, Keyboard Navigation, Release Quick Reference, UI/UX Visual Guide

### Backend Architecture Improvements

#### Exception System Overhaul
- 16 specialized exception types (ValidationError, AuthenticationError, ConfigurationError, etc.)
- 7 new exception handlers
- Standardized error handling (26 ValueError → Domain Exceptions)

#### Multi-Service Support
- Deezer plugin implemented (OAuth, search, browse)
- Service-agnostic components (90%+ code reuse)
- ISRC-based cross-service track matching
- Multi-service IDs (spotify_id, deezer_id, tidal_id) on all entities

#### Worker Pattern Documentation
- Job-based worker pattern
- Clear distinction: Workers use ValueError (no retry), Services use Domain Exceptions

### Infrastructure Changes

#### Database Schema
- Session renaming: `SessionModel` → `SpotifySessionModel`
- Added `DeezerSessionModel` for multi-service auth
- ISRC field on tracks (unique, indexed)
- Multi-service ID fields (deezer_id, tidal_id)

#### Quality Improvements
- Linting: 2,322 issues → 145 (94% reduction)
- All ValueError in DTOs → ValidationError
- All RuntimeError in lifecycle → ConfigurationError
- Repository/Client interfaces: 100% coverage

---

## [1.5.0] - 2025-11-26

### Web UI Phase 2 Enhancements

#### UI Quick Wins (8 features)
- Optimistic UI updates
- Ripple effects (Material Design)
- Circular progress indicators (SVG)
- Enhanced keyboard navigation (WCAG 2.1 AA)
- Lazy image loading
- Link prefetching
- Stagger animations
- Skip-to-content link

#### UI Advanced Features (6 features)
- Fuzzy search engine (typo-tolerant)
- Multi-criteria filtering
- Native browser notifications
- Progressive Web App (PWA)
- Mobile gestures (swipe, pull-to-refresh)
- Advanced download filtering

#### Design System
- Glassmorphism (blur, transparency, depth)
- 60fps animations
- Mobile-first responsive (320px - 1920px)
- Service worker caching

---

## [1.4.0] - 2025-11-17

### Real-Time Updates

#### Server-Sent Events (SSE)
- `/api/sse/stream` endpoint
- Event types: connected, downloads_update, heartbeat, error
- Automatic reconnection with exponential backoff
- Heartbeat monitoring (30s intervals)

#### Widget Template System
- JSON-based extensibility
- 5 system widgets (Active Jobs, Spotify Search, Missing Tracks, Quick Actions, Metadata Manager)
- Template discovery and registration
- Category/tag organization

---

## [1.3.0] - 2025-11-16

### Automation & Watchlists

#### Core Features
- Artist watchlist system (monitor new releases)
- Discography completion detection
- Quality upgrade identification
- Filter service (whitelist/blacklist)
- Automation workflow rules

#### Background Workers
- WatchlistWorker (check new releases)
- DiscographyWorker (scan missing albums)
- QualityUpgradeWorker (detect upgrades)
- AutomationWorkerManager (coordination)

#### API
- 26 automation endpoints
- Watchlist CRUD
- Filter management
- Automation rules

---

## Related Documentation

- [TODO List](./todo.md) - Current roadmap
- [TODOs Analysis](./todos-analysis.md) - Technical debt
- [Action Plan](./action-plan.md) - Implementation timeline
