# SoulSpot Documentation & Backend Modernization - Action Plan

**Version:** 1.1  
**Created:** 9. Dezember 2025  
**Last Updated:** 13. Dezember 2025  
**Owner:** Entwicklerteam  
**Timeline:** 5 Wochen (9. Dezember 2025 - 13. Januar 2026)

---

## Quick Start Summary

**✅ COMPLETED (Week 1 & 2):**
1. Created `MODERNIZATION_PLAN.md` - Master plan for documentation cleanup + backend optimization
2. Created `DOCS_STATUS.md` - Comprehensive audit of all documentation vs. actual codebase
3. Marked **2 API docs as DEPRECATED:**
   - `docs/api/spotify-album-api.md` → No albums.py router exists
   - `docs/api/spotify-songs-roadmap.md` → Roadmap outdated, artist_songs.py implemented
4. **ALL 5 critical API docs created** (settings, artist-songs, metadata, onboarding, compilations)
5. **Deezer integration doc** marked as PLANNED (not deprecated)
6. **ALL 7 repository interfaces** implemented in `domain/ports/__init__.py`
7. **ALL client interfaces** implemented (ISpotifyClient, IDeezerClient, ITidalClient, etc.)

**📊 CURRENT STATUS:**
- **200+ API endpoints** across 18 routers
- **API documentation coverage:** ~90% (significant improvement!)
- **Repository Interfaces:** 100% (all implemented)
- **Client Interfaces:** 100% (all implemented)

**🔜 REMAINING (Week 3-5):**
- SessionModel → SpotifySessionModel renaming
- ISRC-based track matching implementation
- Final documentation cleanup and archiving

---

## Week 1: Documentation Audit & Critical Deprecation ✅ COMPLETED

**Duration:** 9. - 13. Dezember 2025  
**Goal:** Mark all outdated docs, create missing critical API docs  
**Status:** ✅ COMPLETED

### Tasks

- [x] **Day 1: Generate Inventories** ✅ COMPLETED
  - [x] Code inventory (200+ endpoints, 50+ services, 28 models)
  - [x] Doc inventory (48 files)
  - [x] Cross-reference analysis (DOCS_STATUS.md)

- [x] **Day 2-3: Mark Deprecated Docs** ✅ COMPLETED
  - [x] `spotify-album-api.md` → DEPRECATED ✅
  - [x] `spotify-songs-roadmap.md` → DEPRECATED ✅
  - [x] `features/spotify-playlist-roadmap.md` → File does not exist (was already removed)
  - [x] `features/deezer-integration.md` → Marked as **PLANNED** ✅
  - [x] Onboarding docs consolidated → Only `onboarding-ui-overview.md` remains

- [x] **Day 4-5: Create Missing Critical API Docs** ✅ COMPLETED
  - [x] `docs/api/settings-api.md` (24 endpoints) - ✅ EXISTS
  - [x] `docs/api/artist-songs-api.md` (5 endpoints) - ✅ EXISTS
  - [x] `docs/api/metadata-api.md` (6 endpoints) - ✅ EXISTS
  - [x] `docs/api/onboarding-api.md` (5 endpoints) - ✅ EXISTS
  - [x] `docs/api/compilations-api.md` (7 endpoints) - ✅ EXISTS

### Template für neue API Docs

```markdown
# [Feature] API Reference

> **Version:** 2.0  
> **Last Updated:** YYYY-MM-DD  
> **Status:** ✅ Active  
> **Related Router:** `src/soulspot/api/routers/[router].py`

---

## Endpoints

### [HTTP METHOD] `/api/[path]`

**Purpose:** [What does this endpoint do?]

**Request:**
```json
{
  "param": "value"
}
```

**Response:**
```json
{
  "result": "data"
}
```

**Errors:**
- `400 Bad Request` - Invalid input
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

**Code Example:**
```python
# src/soulspot/api/routers/[router].py (lines X-Y)
@router.post("/[path]")
async def endpoint_name(...):
    ...
```
```

### Deliverables Week 1 ✅ ALL COMPLETED

- [x] **DOCS_STATUS.md** ✅ Done
- [x] **MODERNIZATION_PLAN.md** ✅ Done
- [x] **5 new API docs** (settings, artist-songs, metadata, onboarding, compilations) ✅ All exist
- [x] **Deprecated docs marked** (spotify-album, spotify-songs) ✅
- [x] **Deezer integration marked PLANNED** ✅
- [x] **Onboarding docs consolidated** ✅

---

## Week 2: Backend Interface Standardization ✅ COMPLETED

**Duration:** 16. - 20. Dezember 2025  
**Goal:** Add missing repository + client interfaces for clean architecture  
**Status:** ✅ COMPLETED (Interfaces already existed!)

### Tasks ✅ ALL COMPLETED

All interfaces already exist in `src/soulspot/domain/ports/__init__.py`:

**Repository Interfaces (all implemented):**
- [x] `IArtistWatchlistRepository` - Line 975
- [x] `IFilterRuleRepository` - Line 1019
- [x] `IAutomationRuleRepository` - Line 1058
- [x] `IQualityUpgradeCandidateRepository` - Line 1097
- [x] `ISessionRepository` - Line 1142

**Client Interfaces (all implemented):**
- [x] `ISpotifyClient` - Line 564
- [x] `IDeezerClient` - Line 1201
- [x] `ITidalClient` - Line 1351
- [x] `IMusicBrainzClient` - Line 856
- [x] `ILastfmClient` - Line 921
- [x] `ISlskdClient` - Line 494

### Deliverables Week 2 ✅ ALL COMPLETED

- [x] **7 repository interfaces** in `domain/ports/` ✅ All exist
- [x] **6 client interfaces** in `domain/ports/` ✅ All exist
- [x] **Type checking passes** (`mypy --strict`) ✅

---

## Week 3: Database Model Renaming ✅ COMPLETED

**Duration:** 23. - 27. Dezember 2025  
**Goal:** Rename SessionModel → SpotifySessionModel for service-agnostic architecture  
**Status:** ✅ ALREADY COMPLETED (verified 13. Dezember 2025)

### Verification

The renaming was already completed:
- `SpotifySessionModel` exists in `models.py` line 633
- Table name: `spotify_sessions` ✅
- `DeezerSessionModel` also exists in `models.py` line 676
- Table name: `deezer_sessions` ✅
- No generic `SessionModel` remains

### Tasks ✅ ALL COMPLETED

- [x] **Alembic Migration** - Already applied
- [x] **SessionModel → SpotifySessionModel** - Done
- [x] **DeezerSessionModel added** - Done (bonus: multi-service ready!)
- [x] **Table name `spotify_sessions`** - Verified

---

## Week 4: ISRC-Based Track Matching ✅ MOSTLY COMPLETED

**Duration:** 30. Dezember 2025 - 3. Januar 2026  
**Goal:** Implement service-agnostic track matching via ISRC  
**Status:** ✅ Core functionality implemented (verified 13. Dezember 2025)

### Already Implemented ✅

| Component | Status | Location |
|-----------|--------|----------|
| **ISRC field on TrackModel** | ✅ | `models.py` line 244 (`unique=True, index=True`) |
| **`get_by_isrc()` Interface** | ✅ | `domain/ports/__init__.py` line 302 |
| **`get_by_isrc()` Repository** | ✅ | `repositories.py` line 1358 |
| **Service-specific IDs on Track** | ✅ | `deezer_id`, `tidal_id` fields directly on TrackModel |
| **MusicBrainz ISRC lookup** | ✅ | `musicbrainz_client.lookup_recording_by_isrc()` |
| **ISRC caching** | ✅ | `musicbrainz_cache.get_recording_by_isrc()` |

### Architecture Decision

**Flat Structure (IMPLEMENTED):**
```
TrackModel
├── isrc (unique)     ← Primary dedup key
├── spotify_uri       ← Spotify link
├── deezer_id         ← Deezer link  
└── tidal_id          ← Tidal link
```

This flat structure is **simpler and sufficient** for most cases:
- ISRC is the universal identifier (~95% of tracks have one)
- Service IDs are stored directly on Track entity
- No need for separate mapping tables in most scenarios

### Optional/Future (Not Required)

| Component | Status | Notes |
|-----------|--------|-------|
| **Mapping Tables** | ⏳ Optional | Only needed for edge cases (tracks without ISRC) |
| **`get_or_create_track()` Service** | ⏳ Optional | Current flat structure handles dedup via ISRC |
| **ISRC Backfill Script** | ⏳ Nice-to-have | For enriching old tracks without ISRC |

### Tasks Status

- [x] **ISRC Field** - Already exists with unique constraint
- [x] **Repository Method** - `get_by_isrc()` implemented
- [x] **Interface Definition** - In `ITrackRepository`
- [x] **Service ID Fields** - `deezer_id`, `tidal_id` on TrackModel
- [ ] **Mapping Tables** - Optional, not required for current architecture

---

## Week 5: Documentation Update & Final Review ⏳ PENDING

**Duration:** 6. - 10. Januar 2026  
**Goal:** Update all outdated docs, archive deprecated docs, create v2.0 index

### Tasks

- [ ] **Day 1-2: Update API Docs Marked as UPDATE NEEDED**
  - [ ] `spotify-sync-api.md` - Add 4 missing endpoints
  - [ ] `spotify-artist-api.md` - Add Followed Artists section
  - [ ] `advanced-search-api.md` - Verify 5 endpoints
  - [ ] `spotify-tracks.md` - Verify 5 endpoints
  - [ ] `spotify-metadata-reference.md` - Verify against metadata.py

- [ ] **Day 3: Update Feature Docs**
  - [ ] `authentication.md` - Add Session Management, Onboarding sections
  - [ ] `track-management.md` - Verify coverage
  - [ ] `settings.md` - Likely incomplete, needs review
  - [ ] `artists-roadmap.md` - Rename to `artists-management.md` if implemented
  - [ ] `spotify-albums-roadmap.md` - Clarify status

- [ ] **Day 4: Create Missing Feature Docs**
  - [ ] `album-completeness.md`
  - [ ] `auto-import.md`
  - [ ] `batch-operations.md`
  - [ ] `compilation-detection.md`
  - [ ] `notifications.md`

- [ ] **Day 5: Archive & Index**
  - [ ] Move deprecated docs to `docs/archive/v1.0/`
  - [ ] Update `docs/README.md` with v2.0 index
  - [ ] Update `docs/api/README.md` to reflect new API docs
  - [ ] Update `docs/features/README.md` to reflect new feature docs
  - [ ] Create `CHANGELOG.md` entry for v2.0 documentation update

### Deliverables Week 5

- [ ] **All UPDATE NEEDED docs updated**
- [ ] **5 new feature docs created**
- [ ] **Deprecated docs archived** to `docs/archive/v1.0/`
- [ ] **docs/README.md** updated to v2.0
- [ ] **CHANGELOG.md** entry created

---

## Post-Completion Checklist

### Documentation Quality Gates

- [x] All routers have dedicated API documentation ✅
- [ ] All services have feature documentation
- [ ] No DEPRECATED docs in active directories (all archived)
- [ ] README.md indexes updated to v2.0
- [x] Code examples in docs match actual code ✅
- [ ] All links between docs work

### Backend Architecture Quality Gates

- [x] All repositories have interfaces defined in `domain/ports/` ✅
- [x] SpotifyClient interface defined (ISpotifyClient) ✅
- [x] SessionModel renamed to SpotifySessionModel ✅
- [x] DeezerSessionModel added (bonus!) ✅
- [x] ISRC field on Track model with unique constraint ✅
- [x] Service-specific IDs (deezer_id, tidal_id) on Track ✅
- [ ] Mapping tables (optional) - Not required for current architecture
- [x] Type checking passes (`mypy --strict`) ✅
- [ ] All tests pass (`pytest tests/ -q`)

### Review Metrics

| Metric | Before | After (13.12.2025) | Target |
|--------|--------|-------|--------|
| API Documentation Coverage | 57% (113/200) | ~90% | 95%+ |
| Feature Documentation Coverage | 72% (13/18) | ~85% | 100% |
| Repository Interfaces | 42% (5/12) | 100% (12/12) ✅ | 100% |
| Client Interfaces | N/A | 100% (6/6) ✅ | 100% |
| Service-Agnostic Models | 71% (20/28) | ~95% | 100% |
| Deprecated Docs Archived | 29% (14/48) | ~50% | 100% |

---

## Maintenance Plan (Post-v2.0)

### Weekly Documentation Review

**Every Monday:**
- [ ] Check for new routers added (grep for `@router.` in new PRs)
- [ ] Check for new services added (grep for `class.*Service` in new PRs)
- [ ] Update API docs if endpoints changed
- [ ] Update feature docs if services changed

### Quarterly Architecture Review

**Every 3 months:**
- [ ] Review `domain/ports/` for missing interfaces
- [ ] Review models for service-agnostic compliance
- [ ] Review ISRC coverage (should be 90%+ of tracks)
- [ ] Plan next backend optimization phase

### Pre-Commit Hooks (Future)

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Check if any API route changed
if git diff --cached --name-only | grep -q "src/soulspot/api/routers/"; then
  echo "⚠️  API routes changed. Please update docs/api/ accordingly."
  echo "Run: python scripts/generate_api_docs.py"
  # Uncomment to enforce:
  # exit 1
fi
```

---

## Resources & References

### Key Documents

- **Master Plan:** `docs/MODERNIZATION_PLAN.md` (comprehensive 5-week roadmap)
- **Status Report:** `docs/DOCS_STATUS.md` (current state analysis)
- **This File:** `docs/ACTION_PLAN.md` (week-by-week tasks)

### Architecture Patterns

- **Service-Agnostic Strategy:** `docs/feat-ui/SERVICE_AGNOSTIC_STRATEGY.md`
- **Hexagonal Architecture:** `docs/project/architecture.md` (if exists)
- **ISRC Matching:** See Week 4 implementation

### Codebase References

- **API Routers:** `src/soulspot/api/routers/*.py` (18 routers, 200+ endpoints)
- **Application Services:** `src/soulspot/application/services/*.py` (50+ services)
- **Domain Ports:** `src/soulspot/domain/ports/*.py` (interfaces)
- **Infrastructure:** `src/soulspot/infrastructure/` (repositories, clients)

---

## Contact & Support

**Questions?**
- Review `MODERNIZATION_PLAN.md` for detailed technical explanations
- Check `DOCS_STATUS.md` for specific file-by-file analysis
- Consult `copilot-instructions.md` for coding patterns

**Weekly Sync Meetings:**
- Mondays @ 10:00 - Review progress, unblock issues
- Fridays @ 15:00 - Week wrap-up, plan next week

**Review Cadence:**
- Weekly sync meetings to track progress
- Next review: Week of 16. Dezember 2025

---

**Good luck! 🚀**
