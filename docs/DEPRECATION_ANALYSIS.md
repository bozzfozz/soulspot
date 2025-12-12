# Documentation Redundancy Analysis

**Generated:** 9. Dezember 2025  
**Purpose:** Identify duplicate/outdated documentation for deprecation

---

## Analysis Results

### Category 1: DEPRECATED (Already Marked) ✅

| File | Status | Reason |
|------|--------|--------|
| docs/api/spotify-album-api.md | ✅ DEPRECATED | No albums.py router |
| docs/api/spotify-songs-roadmap.md | ✅ DEPRECATED | artist_songs.py implemented |
| docs/features/spotify-playlist-roadmap.md | ✅ DEPRECATED | playlist-management.md supersedes |
| docs/features/deezer-integration.md | ✅ PLANNED | Design phase, not deprecated |
| docs/implementation/onboarding-ui-implementation.md | ✅ DEPRECATED | Merged into overview |
| docs/implementation/onboarding-ui-visual-guide.md | ✅ DEPRECATED | Merged into overview |

---

### Category 2: REDUNDANT (Should be Deprecated)

#### 2.1 docs/features/authentication.md
- **Overlap:** 90% with **docs/api/auth-api.md**
- **Content:** OAuth flow, session management, CSRF protection
- **Verdict:** **DEPRECATE** - auth-api.md is more comprehensive (9 endpoints vs. feature overview)
- **Keep:** auth-api.md (API reference)
- **Action:** Mark authentication.md as DEPRECATED, redirect to auth-api.md

#### 2.2 docs/features/spotify-sync.md
- **Overlap:** 60% with **docs/api/settings-api.md** (Spotify Sync section)
- **Content:** Auto-sync settings, background worker, intervals
- **Unique:** Architecture diagrams, worker internals, troubleshooting
- **Verdict:** **KEEP BUT UPDATE** - Has unique architectural content
- **Action:** Add note at top: "For API reference, see settings-api.md. This doc focuses on architecture."

#### 2.3 docs/features/spotify-albums-roadmap.md
- **Status:** ROADMAP (what's implemented vs. planned)
- **Content:** Implementation progress, domain layer, infrastructure layer
- **Unique:** Progress tracking, roadmap phases
- **Verdict:** **DEPRECATE** - Roadmaps are outdated after implementation
- **Action:** Mark as DEPRECATED if all features implemented, or convert to CHANGELOG

#### 2.4 docs/features/artists-roadmap.md
- **Status:** ROADMAP (what's implemented vs. planned)
- **Content:** Spotify Artist API endpoints, implementation status
- **Overlap:** 50% with **docs/api/spotify-artist-api.md**
- **Verdict:** **DEPRECATE** - Roadmap format is outdated
- **Action:** Mark as DEPRECATED, redirect to spotify-artist-api.md

#### 2.5 docs/api/spotify-sync-api.md
- **Content:** Spotify sync settings API (GET/PUT /spotify-sync)
- **Overlap:** 80% with **docs/api/settings-api.md** (Spotify Sync section)
- **Verdict:** **DEPRECATE** - settings-api.md covers all endpoints
- **Action:** Mark as DEPRECATED, redirect to settings-api.md

#### 2.6 docs/api/spotify-metadata-reference.md
- **Content:** Metadata enrichment API
- **Overlap:** 90% with **docs/api/metadata-api.md**
- **Verdict:** **DEPRECATE** - metadata-api.md is newer and more complete
- **Action:** Mark as DEPRECATED, redirect to metadata-api.md

---

### Category 3: UNIQUE (Keep)

| File | Unique Value | Verdict |
|------|--------------|---------|
| docs/features/automation-watchlists.md | Watchlist concepts, rules engine | ✅ KEEP |
| docs/features/download-management.md | Download queue strategies | ✅ KEEP |
| docs/features/followed-artists.md | Artist sync workflows | ✅ KEEP |
| docs/features/library-management.md | Local library concepts | ✅ KEEP |
| docs/features/local-library-enrichment.md | Enrichment strategies | ✅ KEEP |
| docs/features/metadata-enrichment.md | Metadata sources, conflicts | ✅ KEEP |
| docs/features/playlist-management.md | Playlist workflows | ✅ KEEP |
| docs/features/settings.md | Settings UI guide | ✅ KEEP |
| docs/features/track-management.md | Track workflows | ✅ KEEP |
| docs/implementation/dashboard-implementation.md | Dashboard internals | ✅ KEEP (pending verification) |
| docs/implementation/onboarding-ui-overview.md | Onboarding wizard | ✅ KEEP |

---

## Recommendations

### High Priority (Clear Redundancy)

1. **docs/features/authentication.md** → DEPRECATE (superseded by auth-api.md)
2. **docs/features/spotify-albums-roadmap.md** → DEPRECATE (roadmap format outdated)
3. **docs/features/artists-roadmap.md** → DEPRECATE (roadmap format outdated)
4. **docs/api/spotify-sync-api.md** → DEPRECATE (superseded by settings-api.md)
5. **docs/api/spotify-metadata-reference.md** → DEPRECATE (superseded by metadata-api.md)

**Total:** 5 additional files to deprecate

### Medium Priority (Partial Overlap)

6. **docs/features/spotify-sync.md** → UPDATE with header: "For API reference, see settings-api.md"

---

## Summary

**Total Files to Deprecate:** 5 new + 6 already deprecated = **11 deprecated files**  
**Files to Update:** 1 (spotify-sync.md)  
**Files to Keep:** 11 (unique feature/implementation docs)

**Action Plan:**
1. Mark 5 files as DEPRECATED with `<details>` archive tags
2. Update spotify-sync.md with API reference link
3. Verify dashboard-implementation.md is still relevant
