# SoulSpot Documentation (v2.0)

**Last Updated:** 2025-12-30  
**Status:** ✅ Complete (114+ files, 335 endpoints)

Welcome to the SoulSpot documentation! This comprehensive guide covers everything from API reference to architecture design.

---

## 📚 Documentation Sections

### 1. [API Reference](./01-api/) (26 files, 335 endpoints)

Complete REST API documentation with code examples.

**Core APIs:**
- [Authentication](./01-api/auth.md) - OAuth 2.0, sessions (9 endpoints)
- [Library](./01-api/library.md) - Scan, import, duplicates (35 endpoints)
- [Playlists](./01-api/playlists.md) - Import, sync, blacklist (14 endpoints)
- [Downloads](./01-api/downloads.md) - Queue management (14 endpoints)
- [Automation](./01-api/automation.md) - Watchlists, rules (20 endpoints)
- [Artists](./01-api/artists.md) - CRUD, sync (9 endpoints)
- [Tracks](./01-api/tracks.md) - Download, enrich (5 endpoints)
- [Search](./01-api/search.md) - Spotify/Soulseek (5 endpoints)
- [Settings](./01-api/settings.md) - Configuration (24 endpoints)

**Coverage:** 100% (335/335 endpoints documented with code validation)

---

### 2. [Architecture](./02-architecture/) (16 files)

System design and implementation patterns.

**Core Architecture:**
- [Core Philosophy](./02-architecture/core-philosophy.md) - Multi-service aggregation, extensibility
- [Data Standards](./02-architecture/data-standards.md) - DTO definitions
- [Data Layer Patterns](./02-architecture/data-layer-patterns.md) - Entity/Repository/DTO
- [Configuration](./02-architecture/configuration.md) - Database-first config
- [Plugin System](./02-architecture/plugin-system.md) - Multi-service plugins
- [Error Handling](./02-architecture/error-handling.md) - 16 exception types
- [Auth Patterns](./02-architecture/auth-patterns.md) - OAuth flows
- [Worker Patterns](./02-architecture/worker-patterns.md) - Background jobs

---

### 3. [Development](./03-development/) (8 files)

Development guides and roadmaps.

- Backend Roadmap, Frontend Roadmap
- CI/CD, Design Guidelines
- Performance Optimization
- And 3 more development docs

---

### 4. [Features](./06-features/) (19 files)

Feature documentation and usage guides.

**Key Features:**
- [Authentication](./06-features/authentication.md) - OAuth flows
- [Spotify Sync](./06-features/spotify-sync.md) - Playlist/artist sync
- [Deezer Integration](./06-features/deezer-integration.md) - Multi-service
- [Playlist Management](./06-features/playlist-management.md)
- [Automation & Watchlists](./06-features/automation-watchlists.md)
- [Download Management](./06-features/download-management.md)
- [Library Management](./06-features/library-management.md)
- [Metadata Enrichment](./06-features/metadata-enrichment.md)
- And 11 more feature docs

---

### 5. [Library](./07-library/) (9 files)

Library system documentation.

- [Lidarr Integration](./07-library/lidarr-integration.md) - Compatibility guide
- [Quality Profiles](./07-library/quality-profiles.md) - Quality tiers
- [Artwork Implementation](./07-library/artwork-implementation.md)
- [Data Models](./07-library/data-models.md) - Artist/Album/Track/TrackFile
- [Workflows](./07-library/workflows.md) - Add artist, import, monitoring
- [UI Patterns](./07-library/ui-patterns.md) - Table/poster/banner views
- And 3 more library docs

---

### 6. [Guides](./08-guides/) (19 files)

User and developer guides.

**User Guides:**
- [Setup Guide](./08-guides/setup-guide.md) - Getting started
- [User Guide](./08-guides/user-guide.md) - Using SoulSpot
- [Troubleshooting](./08-guides/troubleshooting-guide.md) - Common issues
- [Spotify Auth Troubleshooting](./08-guides/spotify-auth-troubleshooting.md)
- [Multi-Device Auth](./08-guides/multi-device-auth.md)
- [Advanced Search](./08-guides/advanced-search-guide.md)

**Developer Guides:**
- [Testing Guide](./08-guides/testing-guide.md) - Manual testing
- [Deployment Guide](./08-guides/deployment-guide.md) - Production deployment
- [HTMX Patterns](./08-guides/htmx-patterns.md) - HTMX integration
- [Observability Guide](./08-guides/observability-guide.md) - Monitoring
- [Operations Runbook](./08-guides/operations-runbook.md) - Production operations
- And 8 more developer guides

---

### 7. [UI](./09-ui/) (9 files)

UI redesign and component library.

- [UI Redesign Master Plan](./09-ui/feat-ui-pro.md) - 4-phase implementation
- [UI Architecture](./09-ui/ui-architecture-principles.md) - Atomic Design
- [Component Library](./09-ui/component-library.md) - 50+ components
- [Accessibility Guide](./09-ui/accessibility-guide.md) - WCAG 2.1 AA
- [Quality Gates A11Y](./09-ui/quality-gates-a11y.md) - Testing framework
- [Service-Agnostic Strategy](./09-ui/service-agnostic-strategy.md) - Multi-service UI
- [Library Artists View](./09-ui/library-artists-view.md) - Hybrid view
- And 2 more UI docs

---

### 8. [Quality](./10-quality/) (3 files)

Quality assurance and testing.

- [Linting Report](./10-quality/linting-report.md) - Code quality (94% improvement)
- [Log Analysis](./10-quality/log-analysis.md) - Debugging guide
- [Documentation Status](./10-quality/docs-status.md) - Coverage report

---

### 9. [Project](./11-project/) (5 files)

Project management and planning.

- [TODO List](./11-project/todo.md) - Current roadmap
- [TODOs Analysis](./11-project/todos-analysis.md) - Technical debt (86% resolved)
- [Action Plan](./11-project/action-plan.md) - Implementation timeline
- [Changelog](./11-project/changelog.md) - Version history
- [Contributing](./11-project/contributing.md) - Contribution guidelines

---

## 🚀 Quick Start

### For Users

1. **Setup:** [Setup Guide](./08-guides/setup-guide.md)
2. **Using SoulSpot:** [User Guide](./08-guides/user-guide.md)
3. **Troubleshooting:** [Troubleshooting Guide](./08-guides/troubleshooting-guide.md)

### For Developers

1. **Architecture:** [Core Philosophy](./02-architecture/core-philosophy.md)
2. **API Reference:** [API Index](./01-api/README.md)
3. **Contributing:** [Contributing Guide](./11-project/contributing.md)
4. **Development Setup:** Follow [Contributing Guide](./11-project/contributing.md#getting-started)

---

## 📊 Documentation Stats

| Category | Files | Coverage | Status |
|----------|-------|----------|--------|
| **API Reference** | 26 | 100% (335 endpoints) | ✅ Complete |
| **Architecture** | 16 | 100% | ✅ Complete |
| **Development** | 8 | 100% | ✅ Complete |
| **Features** | 19 | 100% | ✅ Complete |
| **Library** | 9 | 100% | ✅ Complete |
| **Guides** | 19 | 100% | ✅ Complete |
| **UI** | 9 | 100% | ✅ Complete |
| **Quality** | 3 | 100% | ✅ Complete |
| **Project** | 5 | 100% | ✅ Complete |
| **Total** | **114+** | **100%** | ✅ **COMPLETE** |

---

## 🔍 Find What You Need

### By Task

| What do you want to do? | Go to |
|-------------------------|-------|
| **Use SoulSpot** | [User Guide](./08-guides/user-guide.md) |
| **Troubleshoot issues** | [Troubleshooting](./08-guides/troubleshooting-guide.md) |
| **Integrate with API** | [API Reference](./01-api/README.md) |
| **Understand architecture** | [Core Philosophy](./02-architecture/core-philosophy.md) |
| **Contribute code** | [Contributing Guide](./11-project/contributing.md) |
| **Deploy to production** | [Deployment Guide](./08-guides/deployment-guide.md) |
| **Add new feature** | [Architecture](./02-architecture/) + [Contributing](./11-project/contributing.md) |

### By Feature

| Feature | Documentation |
|---------|--------------|
| **Authentication** | [Auth API](./01-api/auth.md) + [Auth Feature](./06-features/authentication.md) |
| **Playlists** | [Playlists API](./01-api/playlists.md) + [Playlist Management](./06-features/playlist-management.md) |
| **Downloads** | [Downloads API](./01-api/downloads.md) + [Download Management](./06-features/download-management.md) |
| **Library** | [Library API](./01-api/library.md) + [Library Docs](./07-library/) |
| **Automation** | [Automation API](./01-api/automation.md) + [Automation Feature](./06-features/automation-watchlists.md) |
| **Multi-Service** | [Plugin System](./02-architecture/plugin-system.md) + [Deezer Integration](./06-features/deezer-integration.md) |

---

## 📝 Documentation Standards

All documentation follows these standards:

- **Code Validation:** API docs include exact line numbers and real code snippets
- **Examples:** Every endpoint includes request/response examples
- **Cross-References:** Related docs are linked at the end of each file
- **Status Tracking:** Each doc shows last updated date and status
- **Consistency:** Standardized structure across all documentation

---

## 🆕 What's New in v2.0

- ✅ **335 API endpoints** fully documented with code validation
- ✅ **Multi-service support** (Spotify + Deezer with Tidal planned)
- ✅ **ISRC-based track matching** for cross-service deduplication
- ✅ **Repository/Client interfaces** (100% coverage)
- ✅ **Improved architecture docs** (16 files)
- ✅ **Comprehensive feature docs** (19 features)
- ✅ **UI redesign documentation** (9 files, 4-phase plan)
- ✅ **Quality assurance docs** (linting, logs, testing)

---

## 🤝 Contributing

We welcome contributions! Please read:

1. [Contributing Guide](./11-project/contributing.md) - How to contribute
2. [TODO List](./11-project/todo.md) - Feature roadmap
3. [Architecture Docs](./02-architecture/) - System design

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/bozzfozz/soulspot/issues)
- **Discussions:** [GitHub Discussions](https://github.com/bozzfozz/soulspot/discussions)
- **Documentation:** You're reading it! 📖

---

**Documentation Version:** 2.0  
**Last Updated:** 2025-12-30  
**Total Files:** 114+  
**API Endpoints:** 335 (100% documented)
