# ⚠️ DEPRECATED - SoulSpot UI - Seitenstruktur & Navigation

> **Status:** ❌ DEPRECATED  
> **Replaced By:** Actual routes in `src/soulspot/api/routers/` + [feat-ui-pro.md](./feat-ui-pro.md) Phase 3 (Command Palette navigation)  
> **Date Deprecated:** 9. Dezember 2025  
> **Reason:** Theoretical navigation structure. Actual routes exist in API routers (auth.py, library.py, downloads.py, playlists.py, etc.). Command Palette design in feat-ui-pro.md Phase 3.

**DO NOT USE THIS FILE. See `src/soulspot/api/routers/` for actual routes.**

---

<details>
<summary>Original Content (Archived)</summary>

## 📍 Navigationsstruktur

### Hauptmenü (Sidebar)

```
┌─ Main
│  ├─ Dashboard          → /dashboard
│  └─ Search             → /search
│
├─ Library
│  ├─ Artists            → /library/artists
│  ├─ Albums             → /library/albums
│  └─ Tracks             → /library/tracks
│
├─ Content
│  ├─ Playlists          → /playlists
│  ├─ Import             → /playlists/import
│  └─ Queue              → /downloads
│
└─ System
   └─ Settings           → /settings
```

---

## 🗺️ Site Map

### 1. Public / Setup
- **[Onboarding](./prototype/templates/new-ui/pages/onboarding.html)**: First-run wizard (Welcome -> Connect -> Configure -> Finish)
- **[Styleguide](./prototype/templates/new-ui/pages/styleguide.html)**: Component overview and design tokens

### 2. Main Application
- **[Dashboard](./prototype/templates/new-ui/pages/dashboard.html)**: Overview of activity and stats
- **[Search](./prototype/templates/new-ui/pages/search.html)**: Global search results

## 📄 Alle Seiten

### 1. **Dashboard** (`/dashboard`)
**Zweck**: Übersicht und Schnellzugriff

**Inhalt**:
- 4 Statistik-Karten (Playlists, Tracks, Downloads, Queue)
- Neueste Playlists (6er-Grid)
- Neueste Aktivität (Feed)
- Spotify-Verbindungsstatus

**Navigation**:
- → Playlists: Klick auf Playlist-Karte
- → Import: "Import Playlist" Button
- → Queue: Klick auf Queue-Statistik

---

### 2. **Search** (`/search`)
**Zweck**: Globale Suche

**Inhalt**:
- Große Suchleiste (Ctrl+K)
- Filter-Buttons (All, Artists, Albums, Tracks, Playlists)
- Ergebnisse nach Kategorie

**Navigation**:
- → Artist Detail: Klick auf Künstler
- → Album Detail: Klick auf Album
- → Playlist Detail: Klick auf Playlist
- → Library: "View All" Links

---

### 3. **Artists** (`/library/artists`)
**Zweck**: Künstler-Bibliothek

**Inhalt**:
- 4 Statistik-Karten
- Suchleiste
- 6er-Grid mit runden Künstler-Avataren
- Pagination

**Navigation**:
- → Artist Detail: Klick auf Künstler
- → Import: "Import from Spotify" Button (wenn leer)

---

### 4. **Artist Detail** (`/library/artists/{id}`)
**Zweck**: Künstler-Detailansicht

**Inhalt**:
- Großer Header mit Künstler-Bild
- Statistiken (Albums, Tracks, Followers)
- Tabs: Albums, Popular Tracks, About
- Play/Download/Follow Buttons

**Navigation**:
- → Album Detail: Klick auf Album
- → Library Artists: Zurück-Button im Browser

---

### 5. **Albums** (`/library/albums`)
**Zweck**: Album-Bibliothek

**Inhalt**:
- 4 Statistik-Karten
- Suchleiste
- 6er-Grid mit Album-Covern
- Download-Status-Badges
- Pagination

**Navigation**:
- → Album Detail: Klick auf Album (TODO: noch zu erstellen)
- → Import: "Import from Spotify" Button (wenn leer)

---

### 6. **Tracks** (`/library/tracks`)
**Zweck**: Track-Bibliothek

**Inhalt**:
- 4 Statistik-Karten
- Suchleiste
- Tabellen-View mit allen Tracks
- Batch-Selection (Checkboxen)
- Status-Badges (Downloaded, Downloading, Pending)
- Pagination

**Navigation**:
- → Artist Detail: Klick auf Künstler-Name
- → Album Detail: Klick auf Album-Name
- → Import: "Import from Spotify" Button (wenn leer)

---

### 7. **Playlists** (`/playlists`)
**Zweck**: Playlists-Übersicht

**Inhalt**:
- 4 Statistik-Karten
- 5er-Grid mit Playlist-Covern
- Download-Status (Downloaded, Pending)
- Sync-Button
- Pagination

**Navigation**:
- → Playlist Detail: Klick auf Playlist
- → Import: "Import Playlist" Button

---

### 8. **Playlist Detail** (`/playlists/{id}`)
**Zweck**: Playlist-Detailansicht

**Inhalt**:
- Großer Header mit Cover
- Playlist-Info (Tracks, Duration, Downloaded)
- Tabellen-View mit allen Tracks
- Play/Download/Sync Buttons
- Track-Aktionen (Play, Download, Remove)

**Navigation**:
- → Artist Detail: Klick auf Künstler-Name
- → Album Detail: Klick auf Album-Name
- → Playlists: Zurück-Button im Browser

---

### 9. **Import** (`/playlists/import`)
**Zweck**: Spotify-Import

**Inhalt**:
- Spotify-Verbindungsstatus
- Import by URL (Formular)
- Sync All Playlists (mit Optionen)
- Grid mit Spotify-Playlists
- Import-Historie

**Navigation**:
- → Spotify Auth: "Connect Spotify" Button
- → Playlist Detail: Nach Import oder "View" Button
- → Settings: Spotify-Einstellungen

---

### 10. **Queue/Downloads** (`/downloads`)
**Zweck**: Download-Queue-Manager

**Inhalt**:
- 4 Statistik-Karten (Active, Queue, Completed, Failed)
- Tabs: Queue, History
- Queue-Liste mit Echtzeit-Fortschritt
- Batch-Aktionen (Pause All, Clear Completed)
- Track-Aktionen (Pause, Resume, Retry, Cancel)

**Navigation**:
- → Playlists: "Add to Queue" von Playlists
- → Library: Downloads erscheinen in Library

---

### 11. **Settings** (`/settings`)
**Zweck**: Einstellungen

**Inhalt**:
- Sidebar-Navigation (5 Sektionen)
- General: Theme, Sprache
- Spotify: Verbindung, Auto-Sync
- Downloads: Pfad, Qualität, Concurrent
- Library: Organisation, Struktur
- Advanced: Debug, Cache

**Navigation**:
- → Spotify Auth: "Connect Spotify" Button
- → Dashboard: Nach Änderungen

---

## 🔄 Navigationsfluss

### Typischer User-Flow 1: Neue Playlist importieren
```
Dashboard
  → Import (/playlists/import)
    → Connect Spotify (wenn nötig)
    → Playlist auswählen
  → Playlist Detail (/playlists/{id})
    → "Download All" klicken
  → Queue (/downloads)
    → Fortschritt beobachten
  → Library (/library/tracks)
    → Heruntergeladene Tracks sehen
```

### Typischer User-Flow 2: Künstler durchsuchen
```
Search (/search)
  → Künstler suchen
  → Artist Detail (/library/artists/{id})
    → Albums-Tab
    → Album auswählen
  → Album Detail (TODO)
    → Tracks sehen
    → "Download Album" klicken
  → Queue (/downloads)
```

### Typischer User-Flow 3: Queue verwalten
```
Dashboard
  → Queue-Statistik klicken
  → Queue (/downloads)
    → Aktive Downloads sehen
    → Pause/Resume/Cancel
    → History-Tab
```

---

## ✅ Konsistenz-Regeln

### 1. **Breadcrumbs** (TODO: noch hinzufügen)
```
Dashboard > Library > Artists > {Artist Name}
Dashboard > Playlists > {Playlist Name}
```

### 2. **Zurück-Navigation**
- Browser-Zurück-Button funktioniert immer
- Breadcrumbs für tiefe Navigation
- Logo klickt immer zu Dashboard

### 3. **Aktiv-Zustand**
- Sidebar zeigt aktive Seite
- Tabs zeigen aktiven Tab
- Filter zeigen aktiven Filter

### 4. **Empty States**
- Alle Listen haben Empty States
- Empty States haben Call-to-Action
- CTA führt zu relevanter Aktion (meist Import)

### 5. **Statistik-Karten**
- Immer 4 Karten
- Klickbar (führen zu relevanter Ansicht)
- Zeigen aktuelle Zahlen

---

## 📋 Fehlende Seiten (TODO)

1. **Album Detail** (`/library/albums/{id}`)
   - Ähnlich wie Playlist Detail
   - Zeigt alle Tracks des Albums
   - Artist-Link, Download-Button

2. **404 Error Page**
   - Wenn Seite nicht gefunden
   - Link zurück zu Dashboard

3. **Loading States**
   - Skeleton Screens für langsame Ladevorgänge

---

## 🎯 Nächste Schritte

1. ✅ Alle Haupt-Seiten erstellt
2. ✅ Navigation konsistent
3. ⏳ Album Detail Seite erstellen
4. ⏳ Breadcrumbs hinzufügen
5. ⏳ Backend-Integration testen

---

**Erstellt**: 2025-11-26  
**Status**: Navigation komplett, bereit für Backend-Integration
