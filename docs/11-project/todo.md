# TODO List & Roadmap

**Category:** Project Management  
**Last Updated:** 2025-12-30  
**Status:** ✅ Most Critical Items Complete

---

## 🔴 High Priority

### ✅ Database-First Architecture - COMPLETE

**Implemented:**
- ✅ `spotify_artists.html` - Message: "Keine Künstler in der Datenbank" (not "not connected")
- ✅ `import_playlist.html` - Sync status instead of connection status
- ✅ `onboarding.html` - Sync terminology
- ✅ `incomplete_albums.html` - Database-first messaging
- ✅ `/spotify/artists` Backend - Always loads from DB, sync optional

**Principle:** Spotify = Data Source → Sync → DB/Artwork → Frontend shows local data

---

## 🟡 Medium Priority

### ✅ Tests - NO AUTOMATED TESTS

**Policy:** 🚨 ALL TESTING IS MANUAL/LIVE ONLY  
- ❌ No pytest tests
- ❌ No integration/E2E tests
- ✅ User validates manually via UI/API after each change

### ✅ Missing UI Pages - IMPLEMENTED

- ✅ Broken Files UI (`/library/broken-files`) - Fully functional
- ✅ Incomplete Albums UI (`/library/incomplete-albums`) - Fully functional

**Status:** Both pages exist with API endpoints and HTMX integration.

---

## 🔵 Feature Roadmap

### Download Manager Enhancements

> **Details:** [Download Manager Roadmap](../06-features/download-manager-roadmap.md)

**Phase 1: Core Improvements**
- [ ] Auto-Retry with Exponential Backoff
- [ ] Quality Profiles (FLAC > 320kbps > 256kbps)
- [ ] Batch Operations (Multi-Select)
- [ ] Queue Limits (Max concurrent)
- [ ] Failed History Page

**Phase 2: Post-Processing**
- [ ] Metadata Tagging (ID3 via mutagen)
- [ ] Album Art Embed
- [ ] Auto-Move & Rename nach Pattern
- [ ] Notifications (Toast, Webhook)

**Phase 3: Advanced**
- [ ] Scheduler (Time-based Start/Stop)
- [ ] Statistics Dashboard with Charts
- [ ] Alternative Source Search
- [ ] Blocklist for Users/Files

---

## 🟢 Low Priority (Refactoring)

### ✅ Empty Routers - COMPLETE

The routers `albums.py`, `dashboard.py`, `widget_templates.py`, `widgets.py` no longer exist.

### ⏳ Large Router Splitting - OPTIONAL

| Router | Endpoints | Proposed Split |
|--------|-----------|---------------|
| `automation.py` | 25 | → `watchlists.py`, `rules.py`, `filters.py`, `discography.py` |
| `ui.py` | 26 | → `ui_pages.py`, `ui_library.py`, `ui_spotify.py` |
| `library.py` | 15 | → `library_scan.py`, `library_duplicates.py`, `library_import.py` |

> **Note:** Currently functional, splitting is nice-to-have for maintainability.

### Code Cleanup

- [ ] Remove obsolete templates
- [ ] Remove old CSS files
- [ ] Remove widget system remnants

---

## ✅ Completed (December 2025)

### Backend Refactoring ✅ COMPLETE

- [x] **Table Consolidation:** `spotify_artists/albums/tracks` → `soulspot_*` with `source` field
- [x] **Model Cleanup:** SpotifyArtistModel, SpotifyAlbumModel, SpotifyTrackModel deleted
- [x] **Repository Renaming:** `SpotifyBrowseRepository` → `ProviderBrowseRepository`
- [x] **Interface Standardization:** All repositories have interfaces
- [x] **Multi-Service IDs:** `deezer_id`, `tidal_id` added to all entities
- [x] **Session Renaming:** `SessionModel` → `SpotifySessionModel`
- [x] **Sync Status Renaming:** `SpotifySyncStatusModel` → `ProviderSyncStatusModel`

### Previous Completed Items ✅

- [x] Worker System Complete (12 workers)
- [x] Automation Tab in Settings UI
- [x] Spotify OAuth Flow
- [x] Playlist Import/Sync
- [x] Download Queue Management
- [x] Library Scanner
- [x] Metadata Enrichment
- [x] Artist/Album/Track CRUD
- [x] Watchlist System
- [x] Quality Profiles
- [x] Auto-Import Workflow
- [x] Compilation Detection

---

## Planned Features (2026+)

### Multi-Service Support
- [ ] Tidal Integration
- [ ] Apple Music Integration
- [ ] Universal Track Matching (ISRC-based)
- [ ] Service Badge UI (Spotify/Tidal/Deezer)
- [ ] Cross-Service Library Sync

### Advanced Library Features
- [ ] Artist Biography Scraping
- [ ] Lyrics Fetching (Genius/Musixmatch)
- [ ] Genre Auto-Tagging (Last.fm)
- [ ] Smart Playlists (Rules-based)
- [ ] Listening Statistics

### Pro UI Features
- [ ] Command Palette (Cmd+K / Ctrl+K)
- [ ] Advanced Filtering (Multi-Select)
- [ ] Mobile Bottom Sheets
- [ ] Light Mode Theme
- [ ] PWA Installation

---

## Related Documentation

- [Action Plan](./action-plan.md) - Implementation timeline
- [Changelog](./changelog.md) - Version history
- [Download Manager Roadmap](../06-features/download-manager-roadmap.md) - Download features
- [UI Redesign Master Plan](../09-ui/feat-ui-pro.md) - UI roadmap
