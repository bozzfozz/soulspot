# Nice-to-Have Features for Version 3.0

This document lists **optional** features identified from the Version 2.x codebase and additional enhancements that could be implemented in Version 3.0 but are **not part of the core roadmap**. These are valuable features that enhance the system but can be implemented after the core modular architecture is stable.

> **Status**: Optional - Not blocking for v3.0 release
> 
> **Implementation Priority**: Post-MVP (Minimum Viable Product)
> 
> **Decision Authority**: Review and approve before implementation

---

## Table of Contents

1. [From Version 2.x Codebase](#from-version-2x-codebase)
2. [Additional Enhancements](#additional-enhancements)
3. [Performance Optimizations](#performance-optimizations)
4. [Developer Experience](#developer-experience)
5. [Implementation Notes](#implementation-notes)

---

## From Version 2.x Codebase

### 1. Quality Upgrade Service

**What it does**: Automatically identifies tracks in your library that could be upgraded to higher quality versions (e.g., 128kbps MP3 → 320kbps FLAC).

**Value**: 
- User gets better audio quality over time
- Automatic quality improvement without manual intervention
- Smart scoring system (40% bitrate + 60% format weight)

**Complexity**: Medium

**Reuse from v2.x**: 
- ✅ `src/soulspot/application/services/quality_upgrade_service.py` (~300 LOC)
- ✅ Domain entities: `QualityUpgradeCandidate`
- ✅ Quality profiles and scoring algorithm

**Adaptation Required**:
- [ ] Refactor to use Database Module instead of direct SQLAlchemy
- [ ] Move to dedicated `quality_upgrade` submodule under Library module
- [ ] Add structured error messages
- [ ] Add comprehensive docstrings
- [ ] Create events: `quality_upgrade.candidate_found`, `quality_upgrade.completed`

**Estimated Effort**: 2-3 days

---

### 2. Artist Watchlist Service

**What it does**: Monitors favorite artists for new releases and optionally auto-downloads them.

**Value**:
- Never miss new albums from favorite artists
- Automation reduces manual checking
- Configurable quality profiles per artist

**Complexity**: Medium-High

**Reuse from v2.x**:
- ✅ `src/soulspot/application/services/watchlist_service.py` (~200 LOC)
- ✅ Domain entities: `ArtistWatchlist`, `WatchlistStatus`
- ✅ Check frequency logic

**Adaptation Required**:
- [ ] Refactor to use Database Module
- [ ] Integrate with Spotify Auth submodule for token refresh
- [ ] Move to `watchlist` submodule under Spotify module
- [ ] Add background worker for periodic checks
- [ ] Create events: `watchlist.new_release_found`, `watchlist.check_completed`
- [ ] Handle token expiry gracefully

**Estimated Effort**: 3-4 days

**Dependencies**: Spotify Auth submodule must be complete

---

### 3. Advanced Search Service

**What it does**: Complex search with multiple filters (artist, album, year range, quality, format, etc.).

**Value**:
- Power users can find exactly what they want
- Better than simple keyword search
- Useful for large libraries

**Complexity**: Medium

**Reuse from v2.x**:
- ✅ `src/soulspot/application/services/advanced_search.py` (~400 LOC)
- ✅ Filter builders and query construction

**Adaptation Required**:
- [ ] Refactor to use Database Module query API
- [ ] Move to Library module
- [ ] Add Pydantic schemas for search filters
- [ ] Optimize query performance (Database Module caching helps)
- [ ] Add search history feature

**Estimated Effort**: 2-3 days

---

### 4. Album Completeness Checker

**What it does**: Identifies incomplete albums in your library (missing tracks).

**Value**:
- Users can complete their collections
- Better library quality
- Automated missing track detection

**Complexity**: Medium

**Reuse from v2.x**:
- ✅ `src/soulspot/application/services/album_completeness.py` (~250 LOC)
- ✅ MusicBrainz integration for track listing

**Adaptation Required**:
- [ ] Refactor to use Database Module
- [ ] Move to Library module
- [ ] Integrate with MusicBrainz client (already abstracted)
- [ ] Add events: `album.incomplete_detected`
- [ ] UI card for incomplete albums

**Estimated Effort**: 2 days

---

### 5. Post-Processing Pipeline

**What it does**: Automated post-download processing (ID3 tagging, artwork, lyrics, renaming).

**Value**:
- Professional metadata quality
- Consistent file naming
- Artwork and lyrics embedded
- No manual cleanup needed

**Complexity**: High

**Reuse from v2.x**:
- ✅ `src/soulspot/application/services/postprocessing/pipeline.py` (~200 LOC)
- ✅ `id3_tagging_service.py` (~300 LOC)
- ✅ `artwork_service.py` (~150 LOC)
- ✅ `lyrics_service.py` (~200 LOC)
- ✅ `renaming_service.py` (~100 LOC)

**Adaptation Required**:
- [ ] Each service becomes a separate step in Module Router pipeline
- [ ] Refactor to use Database Module
- [ ] Move to `postprocessing` submodule under Library module
- [ ] Add events for each step: `postprocessing.tagging.completed`, etc.
- [ ] Configure pipeline order via Settings Service
- [ ] Add comprehensive error handling per step

**Estimated Effort**: 5-7 days (complex integration)

**Dependencies**: Module Router must support configurable pipelines

---

### 6. Discography Service

**What it does**: Fetches and downloads entire artist discographies.

**Value**:
- Bulk download convenience
- Complete artist collections
- Useful for new artists discovery

**Complexity**: Medium

**Reuse from v2.x**:
- ✅ `src/soulspot/application/services/discography_service.py` (~200 LOC)

**Adaptation Required**:
- [ ] Refactor to use Database Module
- [ ] Move to Spotify module
- [ ] Integrate with Module Router for download orchestration
- [ ] Add progress tracking via SSE
- [ ] Filter by release type (album, single, compilation)

**Estimated Effort**: 2-3 days

---

### 7. Last.fm Integration

**What it does**: Scrobbling, similar artist discovery, personal listening statistics.

**Value**:
- Track listening history
- Music discovery via similar artists
- Integration with existing Last.fm account

**Complexity**: Medium

**Reuse from v2.x**:
- ✅ `src/soulspot/infrastructure/integrations/lastfm_client.py` (~300 LOC)

**Adaptation Required**:
- [ ] Create dedicated Last.fm module
- [ ] Auth submodule for Last.fm API key
- [ ] Scrobbling event subscriber (listen to playback events)
- [ ] Settings Service integration for API key
- [ ] Similar artist recommendations

**Estimated Effort**: 3-4 days

**Note**: Requires playback tracking system (not yet implemented)

---

### 8. Automation Workflow Service

**What it does**: User-defined automation rules (e.g., "If new track in playlist X, download in FLAC").

**Value**:
- Advanced automation for power users
- Customizable workflows
- Reduces manual intervention

**Complexity**: High

**Reuse from v2.x**:
- ✅ `src/soulspot/application/services/automation_workflow_service.py` (~400 LOC)
- ✅ Rule engine, triggers, actions

**Adaptation Required**:
- [ ] Refactor to use Database Module
- [ ] Create dedicated Automation module
- [ ] Integrate with Module Router for action execution
- [ ] Visual workflow builder in UI
- [ ] Event-driven triggers
- [ ] Validate workflows before execution

**Estimated Effort**: 7-10 days (complex feature)

**Note**: Post-MVP feature - requires stable core system first

---

### 9. Library Scanner Service

**What it does**: Scans local music directory and imports existing files into database.

**Value**:
- Import existing music collection
- Avoid re-downloading already owned tracks
- Unified library management

**Complexity**: Medium

**Reuse from v2.x**:
- ✅ `src/soulspot/application/services/library_scanner.py` (~300 LOC)
- ✅ File metadata extraction

**Adaptation Required**:
- [ ] Refactor to use Database Module
- [ ] Move to Library module
- [ ] Add background worker for large scans
- [ ] Progress tracking via SSE
- [ ] Duplicate detection and merging
- [ ] Handle various audio formats (MP3, FLAC, M4A, OGG, etc.)

**Estimated Effort**: 3-4 days

---

### 10. Batch Processor Service

**What it does**: Process multiple tracks/albums/playlists in batches with rate limiting.

**Value**:
- Prevent API rate limit violations
- Efficient bulk operations
- Progress tracking for large operations

**Complexity**: Medium

**Reuse from v2.x**:
- ✅ `src/soulspot/application/services/batch_processor.py` (~200 LOC)

**Adaptation Required**:
- [ ] Refactor to use Database Module
- [ ] Move to core utilities (shared across modules)
- [ ] Integration with Module Router
- [ ] Configurable batch sizes via Settings Service
- [ ] Circuit breaker integration

**Estimated Effort**: 2 days

---

## Additional Enhancements

### 11. Smart Duplicate Detection

**What it does**: Identifies duplicate tracks in library using fuzzy matching (metadata + audio fingerprinting).

**Value**:
- Cleaner library
- Save storage space
- Better organization

**Complexity**: High

**Implementation**:
- Audio fingerprinting (e.g., Chromaprint/AcousticID)
- Metadata similarity scoring
- User decision on which version to keep
- Bulk duplicate removal

**Estimated Effort**: 5-7 days

**Dependencies**: Library Scanner

---

### 12. Playlist Synchronization (Bi-directional)

**What it does**: Not just download from Spotify, but also create Spotify playlists from local library.

**Value**:
- Sync local playlists back to Spotify
- Unified playlist management
- Cloud backup of local playlists

**Complexity**: Medium

**Implementation**:
- Spotify Write API integration
- Conflict resolution (local vs. cloud changes)
- Sync strategy selection (one-way, two-way)

**Estimated Effort**: 3-4 days

**Dependencies**: Spotify Auth submodule

---

### 13. Smart Download Queue Management

**What it does**: Intelligent prioritization of downloads based on multiple factors.

**Value**:
- Important downloads first
- Better user experience
- Efficient resource usage

**Complexity**: Medium

**Implementation**:
- Priority scoring algorithm (user preference, track popularity, quality, etc.)
- Dynamic re-prioritization
- User manual override
- Queue position indicators in UI

**Estimated Effort**: 3 days

---

### 14. Download Statistics & Analytics

**What it does**: Comprehensive statistics (downloads per day, success rate, average speed, popular genres, etc.).

**Value**:
- Insights into library growth
- Identify patterns and issues
- Data-driven optimization

**Complexity**: Low-Medium

**Implementation**:
- Database Module integration for queries
- Dashboard with charts (Chart.js or similar)
- Export to CSV/JSON
- Time-series data storage

**Estimated Effort**: 2-3 days

---

### 15. Multi-Source Download Strategy

**What it does**: Try multiple sources (Soulseek, YouTube Music, SoundCloud) if primary fails.

**Value**:
- Higher success rate
- Resilience to source unavailability
- Better coverage

**Complexity**: High

**Implementation**:
- Multiple downloader modules (YouTube, SoundCloud, etc.)
- Source priority configuration
- Fallback mechanism in Module Router
- Quality comparison across sources

**Estimated Effort**: 10+ days (new modules required)

**Note**: Major feature - requires separate modules for each source

---

### 16. Smart File Organization

**What it does**: Automatically organize files into folders based on customizable templates.

**Value**:
- Consistent library structure
- Easy navigation
- Customizable to user preferences

**Complexity**: Medium

**Implementation**:
- Template engine for folder structure (e.g., `{Artist}/{Album}/{TrackNumber} - {Title}`)
- Safe renaming (prevent data loss)
- Conflict resolution
- Settings Service integration for templates

**Estimated Effort**: 3 days

---

### 17. Collaborative Playlists

**What it does**: Share playlists with other SoulSpot users on local network.

**Value**:
- Family/household playlist sharing
- Collaborative music discovery
- Local network feature

**Complexity**: High

**Implementation**:
- Local network discovery (mDNS/Bonjour)
- Playlist export/import format
- Permission system (read-only vs. edit)
- Conflict resolution

**Estimated Effort**: 7-10 days

**Note**: Requires multi-user consideration (currently single-user)

---

### 18. Download History & Replay

**What it does**: Complete audit trail of all downloads with ability to re-download.

**Value**:
- Track what was downloaded when
- Recover from accidental deletions
- Debugging failed downloads

**Complexity**: Low

**Implementation**:
- Database Module integration
- History UI card
- Re-download action
- Filters (date range, status, source)

**Estimated Effort**: 2 days

---

### 19. Audio Format Conversion

**What it does**: Convert downloaded tracks to preferred format (e.g., FLAC → MP3 for mobile).

**Value**:
- Device compatibility
- Storage optimization
- User preference

**Complexity**: Medium

**Implementation**:
- FFmpeg integration
- Quality settings per format
- Batch conversion
- Keep original or replace option

**Estimated Effort**: 3-4 days

**Dependencies**: FFmpeg in Docker container

---

### 20. Smart Re-download Strategy

**What it does**: Automatically re-download failed/corrupted files, better quality versions when available.

**Value**:
- Automatic quality improvement
- Self-healing library
- Reduced manual intervention

**Complexity**: Medium-High

**Implementation**:
- Corruption detection (file size, checksum, audio validation)
- Quality comparison with available sources
- Automatic re-download scheduling
- User notification

**Estimated Effort**: 4-5 days

**Dependencies**: Quality Upgrade Service

---

## Performance Optimizations

### 21. Aggressive Caching Strategy

**What it does**: Multi-tier caching (Redis + in-memory) for frequently accessed data.

**Value**:
- Faster UI response times
- Reduced database load
- Better scalability

**Complexity**: Medium

**Implementation**:
- Redis integration (optional)
- Cache invalidation strategy
- Cache warming for common queries
- Metrics and monitoring

**Estimated Effort**: 3-4 days

**Note**: Database Module already has memory cache; this extends it

---

### 22. Database Query Optimization

**What it does**: Analyze and optimize slow queries, add indexes, denormalize where needed.

**Value**:
- Faster database operations
- Better performance with large libraries
- Scalability

**Complexity**: Medium

**Implementation**:
- Slow query logging in Database Module
- Index optimization
- Query plan analysis
- Periodic performance reviews

**Estimated Effort**: Ongoing (2 days initial)

---

### 23. Lazy Loading & Pagination Everywhere

**What it does**: Lazy load large lists, paginate all API endpoints, infinite scroll in UI.

**Value**:
- Faster initial page loads
- Better UX for large datasets
- Reduced memory usage

**Complexity**: Low-Medium

**Implementation**:
- Pagination in Database Module
- Infinite scroll components (HTMX)
- Virtual scrolling for very large lists

**Estimated Effort**: 3 days

---

## Developer Experience

### 24. GraphQL API (Optional)

**What it does**: Provide GraphQL endpoint alongside REST API for flexible data fetching.

**Value**:
- Reduced over-fetching
- Better developer experience
- Flexible queries

**Complexity**: High

**Implementation**:
- Strawberry or Graphene integration
- Schema design mirroring domain model
- Resolvers for each module
- GraphQL playground

**Estimated Effort**: 7-10 days

**Note**: Nice-to-have for developers, not end-users

---

### 25. CLI Tool

**What it does**: Command-line interface for power users and automation.

**Value**:
- Scriptability
- Server automation
- Power user preference

**Complexity**: Medium

**Implementation**:
- Click or Typer framework
- Commands for common operations
- Output formatting (JSON, table, plain text)
- Integration with Module Router

**Estimated Effort**: 4-5 days

---

### 26. Plugin System

**What it does**: Allow third-party modules/plugins to extend functionality.

**Value**:
- Community contributions
- Extensibility without forking
- Custom integrations

**Complexity**: Very High

**Implementation**:
- Plugin discovery and loading
- Plugin API contract
- Sandboxing and security
- Plugin marketplace/registry

**Estimated Effort**: 15+ days

**Note**: Major architectural addition - post-MVP

---

### 27. Comprehensive API Documentation

**What it does**: OpenAPI/Swagger docs, interactive playground, code examples.

**Value**:
- Better developer onboarding
- API discoverability
- Testing convenience

**Complexity**: Low

**Implementation**:
- FastAPI auto-generated OpenAPI
- Redoc or SwaggerUI
- Example requests for each endpoint
- Authentication flow examples

**Estimated Effort**: 2 days

---

### 28. Integration Test Suite

**What it does**: End-to-end tests covering entire user workflows.

**Value**:
- Prevent regressions
- Confidence in changes
- Production-like testing

**Complexity**: Medium

**Implementation**:
- Pytest with async support
- Docker Compose test environment
- Mock external APIs (Spotify, MusicBrainz, slskd)
- CI/CD integration

**Estimated Effort**: 5-7 days

---

### 29. Performance Benchmarking Suite

**What it does**: Automated performance tests to track regressions.

**Value**:
- Prevent performance degradation
- Identify bottlenecks early
- Data-driven optimization

**Complexity**: Medium

**Implementation**:
- Locust or similar for load testing
- Benchmark common operations
- Historical tracking
- CI integration with thresholds

**Estimated Effort**: 3-4 days

---

### 30. Development Docker Compose

**What it does**: Docker Compose setup optimized for development (hot reload, debug mode, etc.).

**Value**:
- Faster development cycle
- Consistent dev environment
- Easy onboarding for contributors

**Complexity**: Low

**Implementation**:
- Dev-specific docker-compose.dev.yml
- Volume mounts for hot reload
- Debug port exposure
- Development seed data

**Estimated Effort**: 1 day

---

## Implementation Notes

### General Guidelines

1. **Prioritization**:
   - Focus on core modular architecture first
   - Implement nice-to-have features only after MVP is stable
   - User feedback should guide priority

2. **Quality Standards**:
   - All features MUST follow Version 3.0 architecture
   - Use Database Module for all data access
   - Use Settings Service for configuration
   - Comprehensive docstrings required
   - >80% test coverage
   - Structured error messages

3. **Reuse Strategy**:
   - Validate v2.x code against quality checklist (MIGRATION_FROM_V2.md)
   - Refactor to fit modular architecture
   - No direct SQLAlchemy - use Database Module
   - No dead code or placeholders

4. **Documentation**:
   - Each feature must have ADR explaining decision
   - Update module CHANGELOG.md
   - Update relevant docs/ files
   - Add examples in module docs/

5. **Incremental Rollout**:
   - Implement one feature at a time
   - Full testing before moving to next
   - Gather user feedback
   - Iterate based on feedback

### Decision Process

Before implementing any nice-to-have feature:

1. **Review**: Assess value vs. complexity
2. **Approve**: Get user/stakeholder approval
3. **Design**: Create ADR and update architecture docs
4. **Implement**: Follow Version 3.0 standards
5. **Test**: >80% coverage + integration tests
6. **Document**: Update all relevant docs
7. **Release**: Beta test before general availability

### Dependencies

Many features depend on core infrastructure:

- **Must have first**: Database Module, Settings Service, Event Bus, Module Router
- **Pilot modules complete**: Soulseek, Spotify
- **UI Design System**: All 7 card types implemented

### Estimated Total Effort

If implementing all nice-to-have features: **150-200 developer days**

**Recommendation**: Implement selectively based on user demand and value.

---

## Version History

- **2025-11-22**: Initial creation based on v2.x codebase analysis
- Features categorized by source (v2.x vs. new enhancements)
- Complexity and effort estimates added
- Dependencies and prerequisites documented

---

**Next Steps**:
1. Review this document with stakeholders
2. Prioritize top 5-10 features for post-MVP implementation
3. Create GitHub issues for approved features
4. Update ROADMAP.md with selected features in Phase 3+
