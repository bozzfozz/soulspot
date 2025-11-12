# SoulSpot Bridge – Backend Development Roadmap

> **Last Updated:** 2025-11-12  
> **Version:** 0.1.0 (Alpha)  
> **Status:** Phase 6 Complete - Production Ready | Phase 7 Feature Enhancements In Progress  
> **Owner:** Backend Team

---

## 📑 Table of Contents

1. [Vision & Goals](#-vision--goals)
2. [Current Status](#-current-status)
3. [Architecture Overview](#-architecture-overview)
4. [Now (Next 4-8 Weeks)](#-now-next-4-8-weeks)
5. [Next (2-3 Months)](#-next-2-3-months)
6. [Later (>3 Months)](#-later-3-months)
7. [Dependencies & Risks](#-dependencies--risks)
8. [Links & References](#-links--references)

---

## 🎯 Vision & Goals

The backend of SoulSpot Bridge is responsible for:

- 🗄️ **Data Management** – SQLite database layer, Alembic migrations, robust data persistence
- 🔌 **External Integrations** – Spotify API, slskd client, MusicBrainz, metadata providers
- ⚙️ **Business Logic** – Use cases, domain services, download queue management, post-processing pipeline
- 🔄 **Worker System** – Background job processing, async operations, retry logic
- 📊 **API Layer** – FastAPI REST endpoints, request validation, response formatting
- 💾 **Caching & Performance** – SQLite-based caching, connection pooling, query optimization

### Core Principles

- **Clean Architecture** – Domain-driven design with clear separation of concerns
- **Type Safety** – Full type hints, mypy validation
- **Async First** – Async/await patterns throughout
- **Observability** – Structured logging, correlation IDs, health checks
- **Security** – Input validation, secrets management, rate limiting

---

## 📍 Current Status

### ✅ Completed Phases

| Phase | Status | Key Features |
|-------|--------|--------------|
| **Phase 1: Foundation** | ✅ Complete | Domain Layer, Project Setup, Core Models |
| **Phase 2: Core Infrastructure** | ✅ Complete | Settings Management, Database Layer, FastAPI Application |
| **Phase 3: External Integrations** | ✅ Complete | slskd Client, Spotify OAuth, MusicBrainz Integration |
| **Phase 4: Application Layer** | ✅ Complete | Use Cases, Worker System, Token Management, Caching |
| **Phase 6: Production Readiness** | ✅ Complete | Structured Logging, Health Checks, Performance Optimization |

### 🔄 Current Phase: Phase 7 – Feature Enhancements

**Progress:** Planning & Initial Development

**Focus Areas:**
- Enhanced download management (priority queues, retry logic)
- Advanced metadata management (multi-source merging, conflict resolution)
- Post-processing pipeline improvements
- Library scanning and self-healing features

---

## 🏗️ Architecture Overview

### Technology Stack

| Component | Technology | Status |
|-----------|-----------|--------|
| **Framework** | FastAPI | ✅ Implemented |
| **Database** | SQLAlchemy 2.0 + SQLite | ✅ Implemented |
| **Migrations** | Alembic | ✅ Implemented |
| **Async Runtime** | asyncio | ✅ Implemented |
| **Validation** | Pydantic v2 | ✅ Implemented |
| **HTTP Client** | httpx | ✅ Implemented |
| **Testing** | pytest + pytest-asyncio | ✅ Implemented |

### Layered Architecture

```
┌─────────────────────────────────────┐
│      API Layer (FastAPI)            │  ← REST endpoints, request validation
├─────────────────────────────────────┤
│    Application Layer (Use Cases)    │  ← Business logic, orchestration
├─────────────────────────────────────┤
│   Domain Layer (Entities, Services) │  ← Core business models
├─────────────────────────────────────┤
│  Infrastructure (Repositories, APIs) │  ← Data access, external integrations
└─────────────────────────────────────┘
```

### Key Components

#### 1. Database Layer

- **SQLAlchemy 2.0** with async support
- **Alembic** for schema migrations
- **Repository Pattern** for data access
- **Connection Pooling** for performance

#### 2. External Integrations

| Integration | Purpose | Status |
|-------------|---------|--------|
| **Spotify API** | OAuth, playlists, metadata | ✅ Implemented |
| **slskd** | Download client, search | ✅ Implemented |
| **MusicBrainz** | Canonical music metadata | ✅ Implemented |
| **Discogs** | Release details (planned) | 📋 Phase 7 |
| **Last.fm** | Genre tags, stats (planned) | 📋 Phase 7 |

#### 3. Worker System

- **Background Jobs** – Async task processing
- **Job Queue** – SQLite-based queue with priority support
- **Retry Logic** – Exponential backoff (planned)
- **Status Tracking** – Real-time job status updates

#### 4. Caching Layer

- **SQLite Cache** – API response caching
- **TTL Management** – Automatic cache expiration
- **Cache Invalidation** – Smart invalidation strategies

---

## 🚀 Now (Next 4-8 Weeks)

### Priority: HIGH (P0/P1)

#### 1. Download Management Enhancements

**Epic:** Enhanced Download Queue System  
**Owner:** Backend Team  
**Priority:** P0  
**Effort:** Medium (2-3 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Priority-based Queue** | Implement priority field in job queue | P0 | Small | 📋 Planned |
| **Retry Logic** | Exponential backoff with alternative sources | P0 | Medium | 📋 Planned |
| **Concurrent Download Limits** | Configurable parallel download limits (1-3) | P1 | Small | 📋 Planned |
| **Pause/Resume API** | Individual and global pause/resume | P1 | Medium | 📋 Planned |
| **Batch Operations** | Bulk download API endpoints | P1 | Medium | 📋 Planned |

**Acceptance Criteria:**
- [ ] Priority field added to job model and sortable
- [ ] Retry logic with 3 attempts (1s, 2s, 4s backoff)
- [ ] Configurable concurrent download limit
- [ ] Pause/resume endpoints functional
- [ ] Batch download endpoint for multiple tracks
- [ ] Unit tests for all new features (>80% coverage)

**Dependencies:**
- Phase 6 completion (✅ Done)
- Database schema migration for priority field

**Risks:**
- Race conditions in concurrent downloads
- Retry logic complexity

---

#### 2. Metadata Management

**Epic:** Multi-Source Metadata Engine  
**Owner:** Backend Team  
**Priority:** P0  
**Effort:** Large (3-4 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Multi-Source Merge** | Combine metadata from multiple sources | P0 | Large | 📋 Planned |
| **Authority Hierarchy** | Configure source priority per field | P0 | Medium | 📋 Planned |
| **Conflict Resolution** | API for resolving metadata conflicts | P1 | Medium | 📋 Planned |
| **Discogs Integration** | Add Discogs as metadata source | P1 | Medium | 📋 Planned |
| **Last.fm Integration** | Add Last.fm for genres/tags | P1 | Medium | 📋 Planned |
| **Tag Normalization** | Standardize artist names (feat./ft.) | P1 | Small | 📋 Planned |

**Acceptance Criteria:**
- [ ] Metadata merger with configurable source priority
- [ ] Authority hierarchy: Manual > MusicBrainz > Discogs > Spotify > Last.fm
- [ ] Conflict resolution API endpoints
- [ ] Discogs API integration complete
- [ ] Last.fm API integration complete
- [ ] Tag normalization rules implemented
- [ ] Unit + integration tests

**Dependencies:**
- External API rate limits (MusicBrainz: 1 req/sec, Discogs: TBD)

**Risks:**
- API rate limit handling complexity
- Data quality inconsistencies across sources

---

#### 3. Post-Processing Pipeline

**Epic:** Automated Post-Processing  
**Owner:** Backend Team  
**Priority:** P1  
**Effort:** Medium (2 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Pipeline Orchestration** | Coordinate all post-processing steps | P1 | Medium | 📋 Planned |
| **Artwork Download** | Multi-source, multi-resolution | P1 | Small | 📋 Planned |
| **Lyrics Integration** | LRClib, Genius, Musixmatch | P1 | Medium | 📋 Planned |
| **ID3 Tagging** | Comprehensive tag writing | P1 | Medium | 🔄 In Progress |
| **File Renaming** | Template-based renaming | P1 | Small | 🔄 In Progress |
| **Auto-Move Service** | Move to final library location | P0 | Small | ✅ Done |

**Acceptance Criteria:**
- [ ] Pipeline runs automatically after download
- [ ] Multi-resolution artwork download and embedding
- [ ] Lyrics fetching from 3 sources with fallback
- [ ] ID3v2.4 tags with all standard fields
- [ ] Configurable file naming templates
- [ ] Auto-move to organized library structure
- [ ] Comprehensive error handling and logging

**Dependencies:**
- Metadata management complete
- External API integrations (lyrics providers)

---

#### 4. Library Management

**Epic:** Library Scanning & Self-Healing  
**Owner:** Backend Team  
**Priority:** P1  
**Effort:** Large (3-4 weeks)

| Task | Description | Priority | Effort | Status |
|------|-------------|----------|--------|--------|
| **Library Scanner** | Full library scan (files, tags, structure) | P1 | Large | 📋 Planned |
| **Hash-Based Duplicate Detection** | MD5/SHA1 indexing | P1 | Medium | 📋 Planned |
| **Broken File Detection** | Identify corrupted/incomplete files | P1 | Medium | 📋 Planned |
| **Album Completeness Check** | Detect missing tracks | P1 | Medium | 📋 Planned |
| **Auto Re-Download** | Re-download corrupted files | P2 | Medium | 📋 Planned |

**Acceptance Criteria:**
- [ ] Library scanner with progress tracking
- [ ] Hash index for all files in database
- [ ] Duplicate detection with smart unification
- [ ] Broken file detection (validation)
- [ ] Album completeness reporting
- [ ] API endpoints for scan results
- [ ] Unit + integration tests

**Dependencies:**
- Large file operations (performance considerations)
- Database schema for hash index

**Risks:**
- Performance with large libraries (>100k files)
- False positive duplicate detection

---

## 📅 Next (2-3 Months)

### Priority: MEDIUM (P1/P2)

#### 5. Advanced Search & Matching

**Epic:** Intelligent Track Matching  
**Owner:** Backend Team  
**Priority:** P1  
**Effort:** Large (3-4 weeks)

| Feature | Description | Priority | Effort |
|---------|-------------|----------|--------|
| **Fuzzy Matching** | Typo-tolerant search | P1 | Medium |
| **Quality Filters** | Min-bitrate, format filters | P1 | Small |
| **Exclusion Keywords** | Blacklist (Live, Remix, etc.) | P1 | Small |
| **Alternative Sources** | Fallback on failed downloads | P1 | Medium |
| **Smart Scoring** | Improved match algorithm | P2 | Medium |

---

#### 6. Automation & Watchlists

**Epic:** arr-Style Automation  
**Owner:** Backend Team  
**Priority:** P2  
**Effort:** Very Large (4-6 weeks)

| Feature | Description | Priority | Effort |
|---------|-------------|----------|--------|
| **Artist Watchlist** | Auto-download new releases | P2 | Large |
| **Discography Completion** | Detect missing albums | P2 | Medium |
| **Quality Upgrade** | Replace lower-quality versions | P2 | Medium |
| **Automated Workflow** | Detect→Search→Download→Process | P1 | Very Large |
| **Whitelist/Blacklist** | User/keyword filters | P2 | Small |

---

#### 7. Performance & Scalability

**Epic:** Production Performance Optimization  
**Owner:** Backend Team  
**Priority:** P1  
**Effort:** Medium (2 weeks)

| Task | Description | Priority | Effort |
|------|-------------|----------|--------|
| **Query Optimization** | Analyze and optimize slow queries | P1 | Medium |
| **Index Analysis** | Add missing database indexes | P1 | Small |
| **Connection Pool Tuning** | Optimize pool size and overflow | P1 | Small |
| **Batch Operations** | Batch API calls where possible | P1 | Medium |
| **Cache Strategies** | Improved caching for hot paths | P2 | Medium |

---

## 🔮 Later (>3 Months)

### Priority: LOW (P2/P3)

#### 8. Advanced Features

| Feature | Description | Priority | Effort | Phase |
|---------|-------------|----------|--------|-------|
| **Audio Fingerprinting** | AcoustID/Chromaprint matching | P2 | Very Large | Phase 8-9 |
| **Plugin System** | Extensible architecture | P3 | Very Large | Phase 9 |
| **Multi-Library Support** | Multiple library locations | P2 | Large | Phase 9 |

> **Hinweis:** Features zu PostgreSQL, Redis, Jellyfin, Navidrome und Subsonic wurden entfernt, da SoulSpot als lokaler Dienst im privaten Netzwerk betrieben wird.

---

#### 9. Enterprise Features (v3.0)

| Feature | Description | Priority | Effort |
|---------|-------------|----------|--------|
| **Database Connection Pooling** | Efficient connection management | P1 | Medium |
| **Rate Limiting** | Backend rate limiting for APIs | P0 | Medium |
| **Secrets Management** | Vault integration (optional) | P1 | Large |
| **OWASP Compliance** | Security hardening | P0 | Large |

---

## ⚠️ Dependencies & Risks

### External Dependencies

| Dependency | Impact | Risk Level | Mitigation |
|------------|--------|------------|------------|
| **MusicBrainz API** | Metadata quality | HIGH | Respect rate limits (1 req/sec), implement caching |
| **Spotify API** | OAuth, playlists | HIGH | Handle token refresh, graceful degradation |
| **slskd** | Download functionality | CRITICAL | Health checks, fallback error handling |
| **Discogs API** | Metadata enrichment | MEDIUM | Optional feature, graceful fallback |
| **Last.fm API** | Genre tags | LOW | Optional feature, cache results |

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Database Performance (large libraries)** | MEDIUM | HIGH | Indexing strategy, query optimization, pagination |
| **Race Conditions (concurrent downloads)** | MEDIUM | MEDIUM | Proper locking, transaction isolation |
| **API Rate Limiting** | HIGH | MEDIUM | Worker queue with rate limiting, exponential backoff |
| **External API Changes** | MEDIUM | HIGH | Versioned APIs, integration tests, monitoring |
| **Data Corruption** | LOW | CRITICAL | Atomic file operations, checksums, backup strategies |

### Dependencies Between Features

```
Phase 6 (Production Ready) ✅
    ↓
Phase 7 (Feature Enhancements)
    ├─→ Download Management → Post-Processing Pipeline
    ├─→ Metadata Management → Post-Processing Pipeline
    ├─→ Library Management → Automation & Watchlists
    └─→ Advanced Search → Automation & Watchlists
    ↓
Phase 8 (Advanced Features)
    └─→ Audio Fingerprinting
    ↓
v3.0 (Production Hardening)
    └─→ Security Hardening
```

---

## 🔗 Links & References

### Documentation

- [Architecture Documentation](architecture.md)
- [API Documentation](../src/api/README.md)
- [Database Schema](../alembic/README.md)
- [Testing Guide](testing-guide.md)

### Related Roadmaps

- [Frontend Development Roadmap](frontend-development-roadmap.md)
- [Cross-Cutting Concerns Roadmap](roadmap-crosscutting.md)
- [Full Development Roadmap (Index)](development-roadmap.md)

### External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/)
- [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api)

---

## 📝 Changelog

### 2025-11-12: Backend Roadmap Created

**Changes:**
- ✅ Split from monolithic development roadmap
- ✅ Backend-specific focus areas defined
- ✅ Priorities and effort estimates added
- ✅ Dependencies and risks documented
- ✅ Now/Next/Later structure implemented

**Source:** Original `development-roadmap.md` (archived)

---

**End of Backend Development Roadmap**
