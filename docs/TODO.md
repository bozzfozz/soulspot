# SoulSpot TODO

> **Stand:** Dezember 2025

---

## 🔴 Hohe Priorität

### Database-First Architecture ✅ ERLEDIGT

**Implementiert:**
- ✅ `spotify_artists.html` - Message: "Keine Künstler in der Datenbank" (statt "nicht verbunden")
- ✅ `import_playlist.html` - Sync-Status statt Connection-Status
- ✅ `onboarding.html` - Sync-Terminologie 
- ✅ `incomplete_albums.html` - DB-First Message
- ✅ `/spotify/artists` Backend - lädt IMMER aus DB, Sync optional

**Prinzip:** Spotify = Datenquelle → Sync → DB/Artwork → Frontend zeigt lokale Daten

---

## 🟡 Mittlere Priorität

### Tests erweitern
- [x] Integration Tests für neue API-Endpoints (`/api/library/duplicates/*`, `/api/automation/watchlist*`)
- [ ] E2E Tests für Duplicate Review UI
- [ ] Tests für Automation Workers im Zusammenspiel

### Fehlende UI-Seiten ✅ BEREITS IMPLEMENTIERT

- ✅ Broken Files UI (`/library/broken-files`) - vollständig funktionsfähig
- ✅ Incomplete Albums UI (`/library/incomplete-albums`) - vollständig funktionsfähig

**Status:** Beide Pages existieren bereits mit API-Endpoints und HTMX-Integration.

---

## 🔵 Feature Roadmap

### Download Manager Erweiterungen
> **Details:** [docs/features/DOWNLOAD_MANAGER_FEATURES.md](features/DOWNLOAD_MANAGER_FEATURES.md)

**Phase 1: Core Improvements**
- [ ] Auto-Retry mit Exponential Backoff
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
- [ ] Statistics Dashboard mit Charts
- [ ] Alternative Source Search
- [ ] Blocklist für User/Files

---

## 🟢 Niedrige Priorität (Refactoring)

### Leere Router entfernen ✅ ERLEDIGT

Die Router `albums.py`, `dashboard.py`, `widget_templates.py`, `widgets.py` existieren nicht mehr.

### Große Router aufteilen ⏳ OPTIONAL

| Router | Endpoints | Vorschlag |
|--------|-----------|-----------|
| `automation.py` | 25 | → `watchlists.py`, `rules.py`, `filters.py`, `discography.py` |
| `ui.py` | 26 | → `ui_pages.py`, `ui_library.py`, `ui_spotify.py` |
| `library.py` | 15 | → `library_scan.py`, `library_duplicates.py`, `library_import.py` |

> **Note:** Funktioniert aktuell, Aufteilen ist Nice-to-Have für bessere Wartbarkeit.

### Code-Cleanup (siehe CLEANUP.md)
- [ ] Obsolete Templates entfernen
- [ ] Alte CSS-Dateien entfernen
- [ ] Widget-System Reste entfernen

---

## ✅ Erledigt (Dezember 2025)

### Backend Refactoring ✅ COMPLETE
- [x] **Table Consolidation:** `spotify_artists/albums/tracks` → `soulspot_*` mit `source` Feld
- [x] **Model Cleanup:** SpotifyArtistModel, SpotifyAlbumModel, SpotifyTrackModel gelöscht
- [x] **Repository Renaming:** `SpotifyBrowseRepository` → `ProviderBrowseRepository`
- [x] **Interface Standardization:** Alle Repositories haben jetzt Interfaces
- [x] **Multi-Service IDs:** `deezer_id`, `tidal_id` zu allen Entities hinzugefügt
- [x] **Session Renaming:** `SessionModel` → `SpotifySessionModel`
- [x] **Sync Status Renaming:** `SpotifySyncStatusModel` → `ProviderSyncStatusModel`

### Previous Items ✅
- [x] Worker-System komplett (12 Worker)
- [x] Automation Tab in Settings UI
- [x] Duplicate Review API + UI
- [x] `api/__init__.py` aktualisiert (alle Module exportiert)
- [x] Link in `library.html` auf `/library/duplicates` korrigiert
- [x] Tests für neue Maintenance Workers

---

## 📝 Notizen

- **API Analyse:** ~136 Endpoints total (siehe Chat-History für Details)
- **Worker-Architektur:** 6 Core + 3 Automation + 3 Maintenance Workers
- **UI/API Trennung:** `/api/*` = JSON, `/*` = HTML (Clean Architecture)
- **Table Consolidation Details:** Siehe `docs/architecture/TABLE_CONSOLIDATION_PLAN.md`
- **Modernization Status:** Siehe `docs/MODERNIZATION_PLAN.md`
