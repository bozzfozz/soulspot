# SoulSpot TODO

> **Stand:** November 2025

---

## 🔴 Hohe Priorität

*(aktuell keine)*

---

## 🟡 Mittlere Priorität

### Tests erweitern
- [ ] Integration Tests für neue API-Endpoints (`/api/library/duplicates/*`, `/api/settings/automation/*`)
- [ ] E2E Tests für Duplicate Review UI
- [ ] Tests für Automation Workers im Zusammenspiel

### Fehlende UI-Seiten
- [ ] Broken Files UI (`/library/broken-files`) - aktuell nur API
- [ ] Incomplete Albums UI (`/library/incomplete-albums`) - aktuell nur API

---

## 🟢 Niedrige Priorität (Refactoring)

### Große Router aufteilen

| Router | Endpoints | Vorschlag |
|--------|-----------|-----------|
| `automation.py` | 25 | → `watchlists.py`, `rules.py`, `filters.py`, `discography.py` |
| `ui.py` | 26 | → `ui_pages.py`, `ui_library.py`, `ui_spotify.py` |
| `library.py` | 15 | → `library_scan.py`, `library_duplicates.py`, `library_import.py` |

### Leere Router entfernen

```bash
rm src/soulspot/api/routers/albums.py
rm src/soulspot/api/routers/dashboard.py
rm src/soulspot/api/routers/widget_templates.py
rm src/soulspot/api/routers/widgets.py
```

Nach dem Löschen: Imports in `routers/__init__.py` prüfen.

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
