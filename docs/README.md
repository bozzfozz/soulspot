# SoulSpot Documentation

> **Version:** 2.0  
> **Last Updated:** 2025-01-06

---

## 📁 Documentation Structure

This documentation is organized by purpose to help you find what you need quickly.

```
docs/
├── api/             # API reference documentation (v2.0)
├── features/        # Feature-specific documentation (v2.0)
├── architecture/    # System architecture and patterns
├── guides/          # User and developer guides
│   ├── user/       # End-user documentation
│   └── developer/  # Developer documentation
├── development/     # Development roadmaps and guidelines
├── project/         # Project-level documentation
├── implementation/  # Implementation details and guides
├── history/         # Historical records of implementations
└── archive/         # Archived and outdated documentation
```

---

## 🚀 Quick Start

### Understanding SoulSpot
New to SoulSpot? Understand the core concept:
- **[SoulSpot Architecture Concept](project/SOULSPOT_ARCHITECTURE_CONCEPT.md)** - SoulSpot as a standalone application
- **[Core Philosophy](architecture/CORE_PHILOSOPHY.md)** - Multi-service aggregation and design principles

### For Users
New to SoulSpot? Start here:
1. [Setup Guide](guides/user/setup-guide.md) - Installation and configuration
2. [User Guide](guides/user/user-guide.md) - How to use all features
3. [Troubleshooting](guides/user/troubleshooting-guide.md) - Common issues and solutions

### For Developers
Contributing to SoulSpot? Start here:
1. [Architecture](project/architecture.md) - System design and structure
2. [Error Handling](architecture/ERROR_HANDLING.md) - Exception hierarchy and patterns
3. [Worker Patterns](architecture/WORKER_PATTERNS.md) - Background task architecture
4. [Contributing Guide](project/contributing.md) - How to contribute

### For Operators
Deploying or maintaining SoulSpot? Start here:
1. [Deployment Guide](guides/developer/deployment-guide.md) - Production deployment
2. [Operations Runbook](guides/developer/operations-runbook.md) - Day-to-day operations
3. [Observability Guide](guides/developer/observability-guide.md) - Monitoring and logging

---

## 📚 Documentation Sections

### API Documentation (`api/`) ⭐ v2.0
Complete REST API reference:
- **[API Overview](api/README.md)** - API introduction and conventions

**Core APIs:**
- **[Library Management API](api/library-management-api.md)** - Library operations
- **[Download Management](api/download-management.md)** - Download queue management
- **[Advanced Search API](api/advanced-search-api.md)** - Search endpoint documentation
- **[Settings API](api/settings-api.md)** - Application configuration

**Spotify Integration:**
- **[Spotify Tracks API](api/spotify-tracks.md)** - Track metadata and ISRC deduplication
- **[Spotify Artist API](api/spotify-artist-api.md)** - Artist metadata sync
- **[Spotify Playlist API](api/spotify-playlist-api.md)** - Playlist sync with snapshots

**Automation & Monitoring:** ⭐ NEW
- **[Automation API](api/automation-api.md)** - Watchlists, discography, quality upgrades
- **[Workers API](api/workers-api.md)** - Background worker status and control
- **[Stats API](api/stats-api.md)** - Dashboard statistics and trends

**Authentication & Infrastructure:**
- **[Auth API](api/auth-api.md)** - OAuth flows for Spotify and Deezer
- **[Onboarding API](api/onboarding-api.md)** - First-run setup wizard
- **[Browse API](api/browse-api.md)** - Discover new releases (Deezer)

**Interactive Documentation:**
- Swagger UI: http://localhost:8765/docs
- ReDoc: http://localhost:8765/redoc

### Feature Documentation (`features/`) ⭐ v2.0
Complete documentation for all implemented features:
- **[Feature Overview](features/README.md)** - Index of all features

**Core Features:**
- **[Authentication](features/authentication.md)** ⭐ NEW - OAuth, sessions, security
- **[Spotify Sync](features/spotify-sync.md)** - Auto-sync artists, playlists, albums
- **[Playlist Management](features/playlist-management.md)** - Import, sync, export playlists
- **[Download Management](features/download-management.md)** - Download queue and operations
- **[Library Management](features/library-management.md)** - Scans, duplicates, broken files

**Automation:**
- **[Automation & Watchlists](features/automation-watchlists.md)** - Artist watchlists and rules
- **[Followed Artists](features/followed-artists.md)** - Spotify followed artists sync
- **[Auto-Import](features/auto-import.md)** - Automatic import of downloads
- **[Album Completeness](features/album-completeness.md)** - Missing album detection

**Enrichment:**
- **[Metadata Enrichment](features/metadata-enrichment.md)** - Multi-source metadata
- **[Compilation Analysis](features/compilation-analysis.md)** - Compilation detection
- **[Batch Operations](features/batch-operations.md)** - Rate-limit optimized batching

**Utilities:**
- **[Track Management](features/track-management.md)** - Track search, download, editing
- **[Settings](features/settings.md)** - Application configuration
- **[Deezer Integration](features/deezer-integration.md)** - Deezer browse and search
- **[Notifications](features/notifications.md)** - Notification system (stub)

### Architecture Documentation (`architecture/`)
System architecture and design patterns:
- **[Core Philosophy](architecture/CORE_PHILOSOPHY.md)** - Multi-service aggregation
- **[Error Handling](architecture/ERROR_HANDLING.md)** - Exception hierarchy
- **[Worker Patterns](architecture/WORKER_PATTERNS.md)** - Background task patterns
- **[Configuration](architecture/CONFIGURATION.md)** - Database-first config
- **[Data Layer Patterns](architecture/DATA_LAYER_PATTERNS.md)** - Repository patterns

### Project Documentation (`project/`)
Core project information and guidelines:
- **[SoulSpot Architecture Concept](project/SOULSPOT_ARCHITECTURE_CONCEPT.md)** - Core concept
- **[CHANGELOG](project/CHANGELOG.md)** - Version history and release notes
- **[Architecture](project/architecture.md)** - System architecture and design
- **[Contributing](project/contributing.md)** - Contribution guidelines
- **[Documentation Structure](project/DOCUMENTATION_STRUCTURE.md)** - Documentation organization
- **[Issue Tracker](project/fehler-sammlung.md)** - Current issues and improvements

### User Guides (`guides/user/`)
End-user documentation:
- **[Setup Guide](guides/user/setup-guide.md)** - Installation and initial setup
- **[User Guide](guides/user/user-guide.md)** - Complete feature walkthrough
- **[Advanced Search Guide](guides/user/advanced-search-guide.md)** - Search tips and tricks
- **[Troubleshooting Guide](guides/user/troubleshooting-guide.md)** - Problem resolution
- **[Multi-Device Auth](guides/user/MULTI_DEVICE_AUTH.md)** - Multi-device authentication
- **[Spotify Auth Troubleshooting](guides/user/SPOTIFY_AUTH_TROUBLESHOOTING.md)** - OAuth issues

### Developer Guides (`guides/developer/`)
Technical documentation for developers:

**Development:**
- **[Testing Guide](guides/developer/testing-guide.md)** - Test strategies and execution
- **[Deployment Guide](guides/developer/deployment-guide.md)** - Deployment procedures
- **[Operations Runbook](guides/developer/operations-runbook.md)** - Operational procedures
- **[Observability Guide](guides/developer/observability-guide.md)** - Logging and monitoring

**UI/UX Development:**
- **[Component Library](guides/developer/component-library.md)** - Reusable UI components
- **[Design Guidelines](guides/developer/design-guidelines.md)** - Design system and patterns
- **[HTMX Patterns](guides/developer/htmx-patterns.md)** - HTMX integration patterns
- **[Style Guide](guides/developer/soulspot-style-guide.md)** - CSS and styling conventions

---

## 📝 Documentation Standards

All documentation in this repository follows these standards:

### Format
- All documentation is in Markdown format
- Files use `.md` extension
- Use descriptive filenames with hyphens (e.g., `setup-guide.md`)

### Structure
- Every document starts with a title (H1)
- Include version and last updated date at the top
- Use clear headings and subheadings
- Add a table of contents for long documents

### Versioning
- All documentation references **version 1.0**
- No version prefixes in filenames (no v1.0, v2.0)
- Historical versions are in `archived/` directory

### Links
- Use relative links within documentation
- Link to related documentation where appropriate
- Verify links work before committing

---

## 🤝 Contributing to Documentation

Documentation improvements are always welcome! 

- Fix typos or unclear explanations
- Add missing information
- Improve examples and code snippets
- Update outdated content

See the [Contributing Guide](project/contributing.md) for details on how to submit documentation changes.

---

## ❓ Getting Help

Can't find what you're looking for?

1. Check the [Troubleshooting Guide](guides/user/troubleshooting-guide.md)
2. Search the documentation using your IDE or text editor
3. Open an issue on GitHub with the question
4. Check existing GitHub issues for similar questions

---

**SoulSpot version 1.0** - Complete documentation for a complete music automation platform.
