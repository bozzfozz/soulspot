# SoulSpot Bridge – Backend Development Roadmap

> **Last Updated:** 2025-11-13  
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
7. [Cross-Cutting Concerns](#-cross-cutting-concerns)
8. [Dependencies & Risks](#-dependencies--risks)
9. [Links & References](#-links--references)

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
| **Multi-Source Merge** | Combine metadata from multiple sources | P0 | Large | ✅ Done |
| **Authority Hierarchy** | Configure source priority per field | P0 | Medium | ✅ Done |
| **Conflict Resolution** | API for resolving metadata conflicts | P1 | Medium | ✅ Done |
| **Last.fm Integration** | Add Last.fm for genres/tags | P1 | Medium | ✅ Done |
| **Tag Normalization** | Standardize artist names (feat./ft.) | P1 | Small | ✅ Done |

**Acceptance Criteria:**
- [x] Metadata merger with configurable source priority
- [x] Authority hierarchy: Manual > MusicBrainz > Spotify > Last.fm
- [x] Conflict resolution API endpoints
- [x] Last.fm API integration complete
- [x] Tag normalization rules implemented
- [x] Unit + integration tests

**Dependencies:**
- External API rate limits (MusicBrainz: 1 req/sec)

**Risks:**
- API rate limit handling complexity
- Data quality inconsistencies across sources

**Implementation Notes:**
- Created `LastfmClient` for Last.fm API integration
- Implemented `MetadataMerger` service with authority hierarchy
- Added `EnrichMetadataMultiSourceUseCase` for multi-source enrichment
- Created `/api/metadata` REST endpoints for conflict resolution
- Added `genres`, `tags`, and `metadata_sources` fields to Track, Artist, and Album entities
- Implemented tag normalization for artist names (feat./ft. standardization)

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

## 🔄 Cross-Cutting Concerns

Cross-cutting concerns affect both backend and frontend, ensuring:

- 🔐 **Security** – Authentication, authorization, secrets management, OWASP compliance
- 🔄 **CI/CD** – Automated testing, building, deployment pipelines
- 📊 **Observability** – Logging, monitoring, health checks, tracing
- 🚀 **Deployment** – Docker, Kubernetes, multi-environment setup
- 🎯 **Release Management** – Versioning, changelogs, rollback procedures
- ⚡ **Performance** – Caching, compression, optimization strategies

### ✅ Completed Cross-Cutting Features (Phase 6)

| Area | Status | Key Features |
|------|--------|--------------|
| **Observability** | ✅ Complete | Structured Logging, Correlation IDs, Health Checks |
| **CI/CD** | ✅ Complete | GitHub Actions, Automated Testing, Code Quality |
| **Docker** | ✅ Complete | Multi-stage Build, Security Hardening, Compose Setup |
| **Security** | 🔄 Basic | OAuth PKCE, Input Validation, Basic Hardening |
| **Performance** | ✅ Complete | Connection Pooling, Compression, Query Optimization |

**Implemented:**
- ✅ JSON structured logging with correlation IDs
- ✅ Health check endpoints (liveness, readiness, dependencies)
- ✅ GitHub Actions CI/CD pipeline
- ✅ Automated testing (unit, integration)
- ✅ Code quality checks (ruff, mypy, bandit)
- ✅ Docker production setup
- ✅ Docker Compose configuration
- ✅ Deployment automation (dev, staging, prod)
- ✅ Response compression (GZip)
- ✅ Database connection pooling

### 🚀 Planned Cross-Cutting Enhancements

#### Authentication & Authorization Enhancements
**Priority:** P1 | **Effort:** Medium (2-3 weeks)

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| **Session Management** | Improve session handling | P1 | 📋 Planned |
| **Token Encryption** | Encrypt tokens at rest | P1 | 📋 Planned |
| **Token Revocation** | Proper logout with API call | P1 | 📋 Planned |
| **Session Monitoring** | Activity-based timeout | P2 | 📋 Planned |

#### Enhanced Observability
**Priority:** P1 | **Effort:** Medium (2 weeks)

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| **Metrics Endpoint** | Basic metrics (counts, timings) | P1 | 📋 Planned |
| **Structured Errors** | Consistent error logging | P1 | 📋 Planned |
| **Request Tracing** | Correlation ID propagation | P1 | ✅ Done |
| **Performance Profiling** | Identify bottlenecks | P1 | 📋 Planned |
| **Health Check Details** | Detailed dependency status | P1 | 📋 Planned |

#### CI/CD Enhancements
**Priority:** P1 | **Effort:** Small (1 week)

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| **Faster Builds** | Cache optimization | P1 | 📋 Planned |
| **Parallel Testing** | Run tests in parallel | P1 | 📋 Planned |
| **E2E Tests** | End-to-end test suite | P1 | 📋 Planned |
| **Deployment Rollback** | Automated rollback on failure | P1 | 📋 Planned |
| **Preview Deployments** | PR preview environments | P2 | 📋 Planned |

#### Security Hardening (Phase 7)
**Priority:** P1 | **Effort:** Large (3-4 weeks)

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| **Input Validation** | Comprehensive validation | P1 | 📋 Planned |
| **Rate Limiting** | API rate limiting | P1 | 📋 Planned |
| **CORS Hardening** | Strict CORS policies | P1 | 📋 Planned |
| **Security Headers** | CSP, HSTS, X-Frame-Options | P1 | 📋 Planned |
| **Secrets Rotation** | Automated secret rotation | P2 | 📋 Planned |
| **Audit Logging** | Comprehensive audit trail | P1 | 📋 Planned |

#### Operational Excellence (v3.0)
**Priority:** P1 (v3.0) | **Effort:** Medium (2-3 weeks)

| Task | Description | Priority | Status |
|------|-------------|----------|--------|
| **Backup & Recovery** | Automated backup procedures | P0 | 📋 v3.0 |
| **Disaster Recovery** | Full system recovery plan | P1 | 📋 v3.0 |
| **Rollback Procedures** | Database and app rollback | P0 | 📋 v3.0 |
| **Incident Response** | Runbook for common issues | P1 | ✅ Done |
| **Capacity Planning** | Resource usage projections | P1 | 📋 v3.0 |

> **Note:** PostgreSQL, Redis, nginx und Kubernetes wurden entfernt (lokal-only Betrieb mit SQLite).

---

## ⚠️ Dependencies & Risks

### External Dependencies

| Dependency | Impact | Risk Level | Mitigation |
|------------|--------|------------|------------|
| **MusicBrainz API** | Metadata quality | HIGH | Respect rate limits (1 req/sec), implement caching |
| **Spotify API** | OAuth, playlists | HIGH | Handle token refresh, graceful degradation |
| **slskd** | Download functionality | CRITICAL | Health checks, fallback error handling |
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
- [Testing Guide](guide/testing-guide.md)

### Related Roadmaps

- [Frontend Development Roadmap](frontend-development-roadmap.md)
- [Full Development Roadmap (Index)](archived/development-roadmap.md)

### External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/)
- [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api)

---

## 📝 Changelog

### 2025-11-15: Merged Cross-Cutting Concerns

**Changes:**
- ✅ Integrated cross-cutting concerns (CI/CD, security, observability) into backend roadmap
- ✅ Added dedicated section for infrastructure and DevOps concerns

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
