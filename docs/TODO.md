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

## 🟢 Niedrige Priorität (Refactoring)

### Leere Router entfernen ✅ ERLEDIGT

Die Router `albums.py`, `dashboard.py`, `widget_templates.py`, `widgets.py` existieren nicht mehr.

### Große Router aufteilen

| Router | Endpoints | Vorschlag |
|--------|-----------|-----------|
| `automation.py` | 25 | → `watchlists.py`, `rules.py`, `filters.py`, `discography.py` |
| `ui.py` | 26 | → `ui_pages.py`, `ui_library.py`, `ui_spotify.py` |
| `library.py` | 15 | → `library_scan.py`, `library_duplicates.py`, `library_import.py` |

### Code-Cleanup (siehe CLEANUP.md)
- [ ] Obsolete Templates entfernen
- [ ] Alte CSS-Dateien entfernen
- [ ] Widget-System Reste entfernen

---

## ✅ Erledigt

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
