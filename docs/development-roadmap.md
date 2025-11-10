# SoulSpot Bridge – Development Roadmap

> **Letzte Aktualisierung:** 2025-11-10  
> **Version:** 0.1.0 (Alpha)  
> **Status:** Phase 6 In Progress - Production Readiness

---

## 📑 Inhaltsverzeichnis

1. [Vision & Gesamtziel](#-vision--gesamtziel)
2. [Aktueller Status](#-aktueller-status)
3. [Kernkonzepte & Architektur](#-kernkonzepte--architektur)
4. [Entwicklungsphasen](#-entwicklungsphasen)
5. [Feature-Kategorien](#-feature-kategorien)
6. [Prioritäts-Matrix](#-prioritäts-matrix)
7. [Release-Plan](#-release-plan)
8. [Contributing](#-contributing)
9. [Offene Fragen](#-offene-fragen)

---

## 🎯 Vision & Gesamtziel

**SoulSpot Bridge** ist ein **vollständig automatisiertes, selbstheilendes Musikverwaltungssystem**, das:

- 🎵 **Spotify & Soulseek intelligent verbindet** – automatische Synchronisation zwischen Streaming und lokalem Download
- ⬇️ **Musik automatisch findet, herunterlädt und sauber taggt** – keine manuelle Arbeit mehr
- 🗂️ **Sich selbst organisiert** – konsistente Tags, Cover, Ordnerstruktur und Metadaten
- 🔄 **Mit Media-Servern synchronisiert** – Plex, Jellyfin, Navidrome, Subsonic Integration
- 🤖 **Langfristig lernfähig und modular bleibt** – KI-gestützt, Plugin-System, erweiterbar

### 🎯 Kernnutzen

- **Vollautomatische Bibliotheks-Ergänzung** – fehlende Songs werden erkannt und heruntergeladen
- **Konsistente, perfekte Metadaten** – kombiniert aus Spotify, MusicBrainz, Discogs, Last.fm
- **Kein manuelles Suchen, Sortieren oder Taggen** – Post-Processing-Pipeline automatisiert alles
- **Self-Healing Library** – erkennt Defekte, Duplikate, fehlende Dateien und behebt sie automatisch
- **Plattformübergreifende Synchronisation** – Playlists, Ratings, Play-Counts bleiben überall aktuell

---

## 📍 Aktueller Status

### ✅ Abgeschlossene Phasen

| Phase | Status | Features |
|-------|--------|----------|
| **Phase 1: Foundation** | ✅ Completed | Domain Layer, Project Setup, Docker Environment |
| **Phase 2: Core Infrastructure** | ✅ Completed | Settings Management, Database Layer, FastAPI Application |
| **Phase 3: External Integrations** | ✅ Completed | slskd Client, Spotify OAuth, MusicBrainz Integration |
| **Phase 4: Application Layer** | ✅ Completed | Use Cases, Worker System, Token Management, Caching |
| **Phase 5: Web UI & API** | ✅ Completed | Jinja2 Templates, HTMX, Tailwind CSS, REST API, Session Management |

### 🔄 Aktuelle Phase

**Phase 6: Production Readiness** (In Progress)

**Fortschritt:** ~60% (6/10 Hauptkomponenten abgeschlossen)

**Abgeschlossen:**
- ✅ Structured Logging (JSON, Correlation IDs)
- ✅ Enhanced Health Checks (Liveness, Readiness, Dependencies)
- ✅ Docker Production Setup (Multi-stage Build, Security Hardening)
- ✅ Docker Compose Configuration (slskd Integration, Volume Management)
- ✅ Docker Entrypoint Script (Directory Validation, PUID/PGID)
- ✅ Auto Music Import Service (Background File Moving)

**In Arbeit:**
- 🔄 CI/CD Pipeline (GitHub Actions)
- 🔄 Automated Release Process
- 🔄 Performance Optimization
- 🔄 Security Hardening

**Nächste Schritte:** [Phase 6 Details](#phase-6-production-readiness-priority-high)

---

## 🏗️ Kernkonzepte & Architektur

### 1. Quellen & Integrationen

SoulSpot Bridge verbindet mehrere Datenquellen zu einem einheitlichen System:

#### 🎵 Musik-Quellen

| Quelle | Zweck | Status | Phase |
|--------|-------|--------|-------|
| **Spotify** | Playlists, Artists, Metadaten, OAuth | ✅ Implemented | Phase 3 |
| **Soulseek (slskd)** | Download-Quelle, REST API | ✅ Implemented | Phase 3 |
| **Lokale Bibliothek** | Datei-Management, Indexierung | ✅ Implemented | Phase 4 |
| **SoundCloud** | Optional, zusätzliche Quelle | 📋 Planned | Phase 8 |
| **Bandcamp** | Optional, zusätzliche Quelle | 📋 Planned | Phase 8 |
| **YouTube Music** | Optional, zusätzliche Quelle | 📋 Planned | Phase 8 |

#### 📊 Metadaten-Quellen

| Quelle | Zweck | Status | Phase |
|--------|-------|--------|-------|
| **MusicBrainz** | IDs, Labels, Releases, Canonical Data | ✅ Implemented | Phase 3 |
| **Spotify** | Artist/Track Names, Popularity, ISRC | ✅ Implemented | Phase 3 |
| **Discogs** | Release Details, Year, Edition, Label | 📋 Planned | Phase 7 |
| **Last.fm** | Genre Tags, Mood, Hörerzahlen | 📋 Planned | Phase 7 |
| **CoverArtArchive** | Cover-Art (various resolutions) | ✅ Implemented | Phase 4 |
| **Fanart.tv** | High-res Artwork | 📋 Planned | Phase 7 |
| **LRClib / Genius / Musixmatch** | Lyrics (LRC, Text) | 📋 Planned | Phase 7 |

#### 🖥️ Media-Server-Integrationen

| Server | Funktionen | Status | Phase |
|--------|-----------|--------|-------|
| **Plex** | Rescan Trigger, Ratings Sync, Path Mapping | 📋 Planned | Phase 8 |
| **Jellyfin** | Rescan Trigger, Ratings Sync, Path Mapping | 📋 Planned | Phase 8 |
| **Navidrome** | Rescan Trigger, Path Mapping | 📋 Planned | Phase 8 |
| **Subsonic** | API Integration | 📋 Planned | Phase 8 |

#### 🔔 Benachrichtigungen & Webhooks

| Service | Zweck | Status | Phase |
|---------|-------|--------|-------|
| **Discord** | Webhooks für Download-Status | 📋 Planned | Phase 8 |
| **Telegram** | Bot für Notifications | 📋 Planned | Phase 8 |
| **Email** | SMTP Notifications | 📋 Planned | Phase 8 |
| **Generic Webhooks** | Event-basierte Automation | 📋 Planned | Phase 8 |

### 2. Suche & Matching-Engine

**Beschreibung:** Intelligenter Abgleich zwischen Spotify-Metadaten und Soulseek-Suchergebnissen.

**Scoring-Algorithmus:**
```
Match Score = (Title Similarity × 0.4) 
            + (Artist Match × 0.3) 
            + (Duration Match × 0.2) 
            + (Bitrate/Quality × 0.1)
```

**Features:**

| Feature | Beschreibung | Status | Phase |
|---------|--------------|--------|-------|
| **Basic Matching** | Titel + Artist Abgleich | ✅ Implemented | Phase 4 |
| **Smart Scoring** | Algorithmus mit Gewichtung | ✅ Implemented | Phase 4 |
| **Quality Filter** | Min-Bitrate, Format-Filter (FLAC/MP3) | 📋 Planned | Phase 7 |
| **Exclusion Keywords** | Blacklist (Live, Remix, Radio Edit) | 📋 Planned | Phase 7 |
| **Audio Fingerprinting** | AcoustID/Chromaprint Matching | 🔬 Research | Phase 8-9 |
| **Fuzzy Matching** | Typo-tolerante Suche | 📋 Planned | Phase 7 |
| **Alternative Sources** | Fallback bei fehlgeschlagenen Downloads | 📋 Planned | Phase 7 |

### 3. Download-System & Queue-Management

**Beschreibung:** Vollständig automatisierte Download-Verwaltung mit intelligenter Queue.

**Komponenten:**

| Komponente | Beschreibung | Status | Phase |
|------------|--------------|--------|-------|
| **Job Queue** | SQLite-basierte Queue mit Status Tracking | ✅ Implemented | Phase 4 |
| **Parallel Downloads** | Konfigurierbare Anzahl (Standard: 2) | ✅ Implemented | Phase 4 |
| **Priority System** | Prioritäts-basierte Verarbeitung | 📋 Planned | Phase 7 |
| **Retry Logic** | 3 Versuche mit Exponential Backoff | 📋 Planned | Phase 7 |
| **Scheduler** | Zeitfenster-Steuerung (Nachtmodus) | 📋 Planned | Phase 7 |
| **Pause/Resume** | Download-Kontrolle | 📋 Planned | Phase 7 |
| **Batch Import** | CSV, JSON, M3U, TXT Import | 📋 Planned | Phase 7 |
| **Spotify Export** | Direkter Playlist-Export | 📋 Planned | Phase 7 |

### 4. Post-Processing Pipeline

**Beschreibung:** Automatische Verarbeitung nach erfolgreichem Download.

**Pipeline-Schritte:**

```
Download Complete
    ↓
1. Metadata Enrichment (Spotify + MusicBrainz + Discogs + Last.fm)
    ↓
2. Cover Art Download (Multi-Source, Multi-Resolution)
    ↓
3. Lyrics Fetch (LRClib, Genius, Musixmatch)
    ↓
4. ID3 Tagging (Comprehensive Tags, Artwork Embedding)
    ↓
5. File Renaming (Template: Artist/Year - Album/Track - Title.ext)
    ↓
6. File Organization (Move to Final Library Location)
    ↓
7. Audio Analysis (BPM, Key, Loudness, optional)
    ↓
8. Media Server Rescan (Plex, Jellyfin, Navidrome Trigger)
    ↓
9. Cleanup (Temp Files, Empty Directories)
```

**Status:**

| Schritt | Status | Phase |
|---------|--------|-------|
| 1-3: Basic Tagging | ✅ Implemented | Phase 4-5 |
| 4: Advanced Tagging | 🔄 In Progress | Phase 6 |
| 5: File Renaming | 🔄 In Progress | Phase 6-7 |
| 6: Auto-Move | ✅ Implemented | Phase 6 |
| 7: Audio Analysis | 📋 Planned | Phase 7-8 |
| 8: Server Rescan | 📋 Planned | Phase 8 |
| 9: Cleanup | ✅ Implemented | Phase 6 |

### 5. Metadata-Engine & Authority System

**Beschreibung:** Zentrale Metadaten-Verwaltung mit intelligenter Source-Priorisierung.

**Authority Hierarchy (Standardkonfiguration):**

```
1. Manual User Edits      (Höchste Priorität)
2. MusicBrainz           (Canonical Data)
3. Discogs               (Release Details)
4. Spotify               (User-facing Names, Popularity)
5. Last.fm               (Genre, Mood)
6. File Tags             (Fallback)
```

**Features:**

| Feature | Beschreibung | Status | Phase |
|---------|--------------|--------|-------|
| **Multi-Source Merge** | Kombiniert mehrere Quellen | 📋 Planned | Phase 7 |
| **Field-wise Priority** | Pro-Feld Gewichtung | 📋 Planned | Phase 7 |
| **SQLite Cache** | API-Response Caching | ✅ Implemented | Phase 4 |
| **Tag Normalization** | feat./ft. Standardisierung | 📋 Planned | Phase 7 |
| **Batch Tag Fixer** | UI mit Dry-Run + Commit | 📋 Planned | Phase 7 |
| **Conflict Resolution** | UI für Konflikte | 📋 Planned | Phase 7 |
| **Änderungslog** | Vorher/Nachher Tracking | 📋 Planned | Phase 7 |
| **Periodic Refresh** | Auto-Update veralteter Tags | 📋 Planned | Phase 7 |

### 6. Library-Management & Self-Healing

**Beschreibung:** Überwachung und automatische Pflege der gesamten Musikbibliothek.

**Features:**

| Feature | Beschreibung | Status | Phase |
|---------|--------------|--------|-------|
| **Hash Index** | MD5/SHA1 für Duplikaterkennung | 📋 Planned | Phase 7 |
| **Audio Fingerprint** | AcoustID Duplicate Detection | 🔬 Research | Phase 8-9 |
| **Broken File Detection** | Defekte Dateien erkennen | 📋 Planned | Phase 7 |
| **Completeness Check** | Fehlende Tracks pro Album | 📋 Planned | Phase 7 |
| **Smart Unify** | Beste Version behalten | 📋 Planned | Phase 7 |
| **Auto Re-Download** | Defekte Dateien neu laden | 📋 Planned | Phase 7 |
| **Multi-Library** | NAS, Local, Cloud Support | 📋 Planned | Phase 9 |
| **History Log** | Alle Änderungen dokumentieren | 📋 Planned | Phase 7 |

### 7. Automation & Watchlists ("arr"-Style)

**Beschreibung:** Sonarr/Radarr-ähnliche Automation für Musik.

**Workflow:**
```
Library Scan → Missing Detection → Soulseek Search → Quality Check → Auto Download → Post-Process → Verify → Rescan
```

**Features:**

| Feature | Beschreibung | Status | Phase |
|---------|--------------|--------|-------|
| **Artist Watchlist** | Auto-Download neue Releases | 📋 Planned | Phase 7 |
| **Label Watchlist** | Überwache Labels | 📋 Planned | Phase 7 |
| **Genre Watchlist** | Auto-Download nach Genre | 📋 Planned | Phase 7 |
| **Discography Completion** | Fehlende Alben erkennen | 📋 Planned | Phase 7 |
| **Quality Upgrade** | Bessere Versionen ersetzen | 📋 Planned | Phase 7 |
| **Whitelist/Blacklist** | Nutzer-/Keyword-Filter | 📋 Planned | Phase 7 |
| **Dry-Run Mode** | Testen ohne Aktionen | 📋 Planned | Phase 7 |

### 8. Ratings & Playcount Sync

**Beschreibung:** Synchronisation von Bewertungen zwischen Systemen.

**Features:**

| Feature | Beschreibung | Status | Phase |
|---------|--------------|--------|-------|
| **Plex Sync** | Ratings ↔ ID3v2 POPM | 📋 Planned | Phase 7 |
| **Jellyfin Sync** | Ratings ↔ ID3v2 POPM | 📋 Planned | Phase 7-8 |
| **Navidrome Sync** | Ratings ↔ ID3v2 POPM | 📋 Planned | Phase 8 |
| **Two-Way Sync** | Bidirektionale Synchronisation | 📋 Planned | Phase 7 |
| **Conflict Resolution** | Server gewinnt / Datei gewinnt | 📋 Planned | Phase 7 |
| **Play Count Sync** | Wiedergabezähler | 📋 Planned | Phase 7 |
| **Dry-Run Mode** | Preview vor Sync | 📋 Planned | Phase 7 |

---

## 🚀 Entwicklungsphasen

### Phase 1-5: Foundation & Core Features ✅

**Status:** Abgeschlossen (Wochen 1-18)

**Achievements:**
- Domain Layer mit Clean Architecture
- SQLAlchemy 2.0 + Alembic Migrations
- FastAPI REST API + Web UI
- Spotify OAuth PKCE Flow
- slskd Integration
- MusicBrainz Integration
- Worker-System für Async Jobs
- Basic Caching Layer
- Jinja2 + HTMX + Tailwind UI

---

### Phase 6: Production Readiness (Priority: HIGH) 🔄

**Zeitrahmen:** Q1 2025 (2-3 Wochen)  
**Status:** ~60% Complete  
**Ziel:** Transform to production-ready system with proper observability and deployment automation.

#### 6.1 Observability & Monitoring 🔍

| Task | Status | Complexity |
|------|--------|-----------|
| Structured Logging (JSON, Correlation IDs) | ✅ Done | LOW |
| Request/Response Logging Middleware | ✅ Done | LOW |
| Enhanced Health Checks (Liveness, Readiness) | ✅ Done | LOW |
| Dependency Health Checks (DB, APIs) | ✅ Done | MEDIUM |
| Prometheus Metrics Endpoint | 📋 Planned | MEDIUM |
| Key Performance Indicators (Response Time, Queue) | 📋 Planned | MEDIUM |
| Business Metrics (Downloads, Imports) | 📋 Planned | LOW |
| OpenTelemetry Integration | 📋 Planned | HIGH |
| Distributed Tracing | 📋 Planned | HIGH |
| Circuit Breaker Patterns | 📋 Planned | MEDIUM |

#### 6.2 CI/CD Pipeline 🚀

| Task | Status | Complexity |
|------|--------|-----------|
| GitHub Actions Setup | ✅ Done | MEDIUM |
| Automated Testing (Unit, Integration) | ✅ Done | MEDIUM |
| Code Quality Checks (ruff, mypy, bandit) | ✅ Done | LOW |
| Test Coverage Reporting | ✅ Done | LOW |
| Security Scanning | ✅ Done | LOW |
| Automated Release Process | ✅ Done | MEDIUM |
| Semantic Versioning (SemVer) | ✅ Done | LOW |
| Changelog Generation | ✅ Done | LOW |
| Docker Image Building | ✅ Done | MEDIUM |
| GitHub Releases | ✅ Done | LOW |
| Deployment Automation (Dev, Staging, Prod) | 📋 Planned | HIGH |

#### 6.3 Docker & Deployment 🐳

| Task | Status | Complexity |
|------|--------|-----------|
| Production Dockerfile (Multi-stage, Security) | ✅ Done | MEDIUM |
| Docker Compose Configuration | ✅ Done | MEDIUM |
| Docker Entrypoint Script | ✅ Done | LOW |
| Directory Validation | ✅ Done | LOW |
| PUID/PGID Support | ✅ Done | LOW |
| UMASK Configuration | ✅ Done | LOW |
| Docker Documentation | ✅ Done | LOW |
| Production Profile (PostgreSQL, Redis, nginx) | 📋 Planned | HIGH |
| Kubernetes Manifests | 📋 Planned | VERY HIGH |

#### 6.4 Security Hardening 🔒

| Task | Status | Complexity |
|------|--------|-----------|
| OWASP Top 10 Compliance Check | 📋 Planned | MEDIUM |
| Input Validation Hardening | 📋 Planned | MEDIUM |
| Secrets Management (Environment-based) | 📋 Planned | MEDIUM |
| Rate Limiting for Auth Endpoints | 📋 Planned | LOW |
| Brute Force Protection | 📋 Planned | MEDIUM |
| Session Timeout Configuration | 📋 Planned | LOW |

#### 6.5 Performance Optimization ⚡

| Task | Status | Complexity |
|------|--------|-----------|
| Database Query Optimization | 📋 Planned | MEDIUM |
| Missing Index Analysis | 📋 Planned | LOW |
| Connection Pool Tuning | 📋 Planned | MEDIUM |
| Redis Integration (Distributed Cache) | 📋 Planned | HIGH |
| Response Compression | 📋 Planned | LOW |
| Pagination for Large Results | 📋 Planned | LOW |
| Query Batching | 📋 Planned | MEDIUM |
| Async Heavy Operations | 📋 Planned | MEDIUM |

#### 6.6 Operations Documentation 📚

| Task | Status | Complexity |
|------|--------|-----------|
| Docker Setup Guide | ✅ Done | LOW |
| Troubleshooting Guide | ✅ Done | LOW |
| Operations Runbook | 📋 Planned | MEDIUM |
| Backup & Recovery Procedures | 📋 Planned | MEDIUM |
| Rollback Procedures | 📋 Planned | LOW |
| API Documentation Enhancements | 📋 Planned | LOW |

#### Acceptance Criteria

- ✅ Docker Compose setup complete
- ✅ Auto music import service implemented
- ✅ Docker documentation complete
- [ ] All tests pass in CI/CD pipeline
- [ ] Docker images under 500MB
- [ ] API response time p95 < 200ms
- [ ] Zero high-severity security vulnerabilities
- [ ] Comprehensive monitoring dashboard

---

### Phase 7: Feature Enhancements (Priority: MEDIUM) 📋

**Zeitrahmen:** Q2 2025 (3-4 Wochen)  
**Ziel:** Expand functionality with user-requested features and quality-of-life improvements.

#### 7.1 Download Management Enhancements ⬇️

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Priority-based Queue** | MEDIUM | HIGH |
| - Drag & drop priority | LOW | HIGH |
| - Priority field per job | LOW | HIGH |
| **Download Scheduling** | MEDIUM | MEDIUM |
| - CRON-based scheduling | MEDIUM | MEDIUM |
| - Night mode (off-peak downloads) | LOW | MEDIUM |
| - Bandwidth throttling | MEDIUM | LOW |
| **Concurrent Download Limits** | LOW | HIGH |
| - Configurable parallel downloads (1-3) | LOW | HIGH |
| **Pause/Resume** | MEDIUM | HIGH |
| - Individual download control | MEDIUM | HIGH |
| - Global pause/resume | LOW | HIGH |
| **Retry Logic** | MEDIUM | HIGH |
| - Exponential backoff (1s, 2s, 4s) | LOW | HIGH |
| - Alternative source discovery | MEDIUM | MEDIUM |
| - Quality fallback | MEDIUM | MEDIUM |
| - Resume after restart | MEDIUM | HIGH |
| **Batch Operations** | MEDIUM | HIGH |
| - Bulk track downloads | LOW | HIGH |
| - Playlist download | LOW | HIGH |
| - Album download | LOW | HIGH |
| - CSV/JSON/M3U import | MEDIUM | HIGH |
| - Spotify export integration | LOW | HIGH |
| **Download History** | LOW | MEDIUM |
| - Persistent history | LOW | MEDIUM |
| - Audit log | LOW | MEDIUM |
| - Legal opt-in tracking | LOW | HIGH |

#### 7.2 Metadata Management 📊

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Manual Metadata Editing** | LOW | HIGH |
| - Edit track info | LOW | HIGH |
| - Edit artist info | LOW | MEDIUM |
| - Edit album info | LOW | HIGH |
| **Conflict Resolution** | MEDIUM | HIGH |
| - UI for resolving conflicts | MEDIUM | HIGH |
| - Source preference settings | LOW | HIGH |
| - Metadata versioning | MEDIUM | LOW |
| **Authority Hierarchy** | MEDIUM | HIGH |
| - Manual > MusicBrainz > Discogs > Spotify | LOW | HIGH |
| - Field-wise priority | MEDIUM | MEDIUM |
| **Additional Sources** | MEDIUM | MEDIUM |
| - Discogs integration | MEDIUM | MEDIUM |
| - Last.fm integration | MEDIUM | MEDIUM |
| - Lyrics (LRClib, Musixmatch, Genius) | MEDIUM | MEDIUM |
| - Fanart.tv artwork | LOW | LOW |
| **Advanced Tagging** | MEDIUM | HIGH |
| - Multi-source merge logic | MEDIUM | HIGH |
| - Batch tag fixer UI (Dry-Run + Commit) | MEDIUM | HIGH |
| - SQLite metadata cache | LOW | HIGH |
| - Multiple artwork resolutions | LOW | MEDIUM |
| - Tag normalization (feat./ft.) | LOW | HIGH |

#### 7.3 File Organization & Quality 🗂️

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **File Organization Templates** | MEDIUM | HIGH |
| - Customizable folder structures | MEDIUM | HIGH |
| - Filename templates with variables | MEDIUM | HIGH |
| - Advanced organization rules | MEDIUM | MEDIUM |
| **Quality Management** | MEDIUM | HIGH |
| - Min-bitrate filter | LOW | HIGH |
| - Format filters (FLAC/MP3) | LOW | HIGH |
| - Exclusion keywords (Live/Remix) | LOW | HIGH |
| - Quality reporting | LOW | MEDIUM |
| **Duplicate Detection** | HIGH | HIGH |
| - Hash-based detection (MD5/SHA1) | MEDIUM | HIGH |
| - Audio fingerprint (AcoustID) | HIGH | MEDIUM |
| - Smart Unify (keep best version) | HIGH | HIGH |
| - Cleanup tools | LOW | HIGH |
| **Library Scanning** | HIGH | HIGH |
| - Full library scan (hash/tags/structure) | MEDIUM | HIGH |
| - Broken file detection | MEDIUM | HIGH |
| - Album completeness check | MEDIUM | HIGH |
| - Auto re-download corrupted files | MEDIUM | HIGH |
| - Fix library (tags, cover, structure) | HIGH | HIGH |

#### 7.4 Playlist Management 🎵

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Manual Playlist Management** | LOW | HIGH |
| - Create playlists | LOW | HIGH |
| - Add/remove tracks | LOW | HIGH |
| - Reorder tracks | LOW | HIGH |
| **Playlist Synchronization** | MEDIUM | HIGH |
| - Auto-sync with Spotify | MEDIUM | HIGH |
| - Sync frequency config | LOW | MEDIUM |
| - Conflict resolution | MEDIUM | MEDIUM |
| - Cross-provider sync (Spotify↔Plex↔Navidrome) | HIGH | MEDIUM |
| - Versioning/snapshots/rollback | MEDIUM | MEDIUM |
| **Playlist Export/Import** | LOW | HIGH |
| - M3U, PLS export | LOW | HIGH |
| - CSV/JSON export | LOW | HIGH |
| - Playlist rebuilder with matching | MEDIUM | MEDIUM |
| **Missing Song Discovery** | MEDIUM | HIGH |
| - Compare playlist vs. local library | MEDIUM | HIGH |
| - Report missing tracks | LOW | HIGH |
| - CSV/JSON export of missing | LOW | HIGH |

#### 7.5 Search & Discovery 🔍

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Advanced Search** | MEDIUM | HIGH |
| - Cross-entity search (tracks, artists, albums) | MEDIUM | HIGH |
| - Filters and facets | MEDIUM | HIGH |
| - Autocomplete suggestions | LOW | HIGH |
| - Combined Spotify + Soulseek search | MEDIUM | HIGH |
| - Smart matching score | MEDIUM | HIGH |
| **Discovery Features** | MEDIUM | MEDIUM |
| - Similar tracks/artists | MEDIUM | MEDIUM |
| - Genre-based browsing | LOW | MEDIUM |
| - Trending downloads | LOW | LOW |
| - Discography discovery | MEDIUM | MEDIUM |
| - "Download entire discography" | MEDIUM | MEDIUM |
| **History & Recommendations** | LOW | LOW |
| - Recent searches | LOW | LOW |
| - Frequently downloaded | LOW | LOW |
| - Personalized recommendations | HIGH | LOW |

#### 7.6 Automation & Watchlists 🤖

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Automated Workflow** | HIGH | HIGH |
| - Detect→Search→Match→Download→Tag→Sort | HIGH | HIGH |
| - Dry-run testing | LOW | HIGH |
| - Whitelist/Blacklist config | MEDIUM | HIGH |
| **Watchlist Functionality** | HIGH | MEDIUM |
| - Artist watchlists | MEDIUM | MEDIUM |
| - Label watchlists | MEDIUM | LOW |
| - Genre watchlists | MEDIUM | LOW |
| - Auto-download new releases | HIGH | MEDIUM |
| **Library Monitoring** | MEDIUM | HIGH |
| - Detect missing albums | MEDIUM | HIGH |
| - Auto-complete partial albums | MEDIUM | HIGH |
| - Quality upgrade detection | MEDIUM | MEDIUM |

#### 7.7 Ratings & User Signals ⭐

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Ratings Synchronization** | MEDIUM | MEDIUM |
| - Plex ratings sync | MEDIUM | MEDIUM |
| - Jellyfin ratings sync | MEDIUM | MEDIUM |
| - Navidrome ratings sync | MEDIUM | LOW |
| - Bidirectional sync | MEDIUM | MEDIUM |
| - Conflict resolution | MEDIUM | MEDIUM |
| **User Signals** | LOW | LOW |
| - Play count tracking | LOW | LOW |
| - Skip tracking | LOW | LOW |
| - Like/dislike signals | LOW | LOW |
| - Auto-playlist generation | MEDIUM | LOW |

#### 7.8 Post-Processing Pipeline 🔄

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Automated Steps** | HIGH | HIGH |
| - Temp download → Auto-tagging | MEDIUM | HIGH |
| - Artwork → Lyrics → Audio analysis | MEDIUM | MEDIUM |
| - Rename → Move → Rescan trigger | MEDIUM | HIGH |
| - Comprehensive logging | LOW | HIGH |
| **Optional Processing** | MEDIUM | LOW |
| - Format conversion (Archive↔Mobile) | MEDIUM | LOW |
| - Auto-cleanup temp files | LOW | HIGH |
| - Audiofingerprint generation | HIGH | LOW |

---

### Phase 8: Advanced Features (Priority: LOW) 📋

**Zeitrahmen:** Q2-Q3 2025 (4-6 Wochen)  
**Ziel:** Advanced integrations, mobile app, analytics.

#### 8.1 Mobile Application 📱

| Feature | Complexity | Priority |
|---------|-----------|----------|
| React Native / Flutter app | VERY HIGH | LOW |
| Push notifications | MEDIUM | LOW |
| Mobile-optimized UI | MEDIUM | LOW |
| Offline mode | HIGH | LOW |

#### 8.2 Advanced Integrations 🔌

| Integration | Complexity | Priority |
|------------|-----------|----------|
| **Music Sources** | | |
| - SoundCloud integration | MEDIUM | LOW |
| - Bandcamp integration | MEDIUM | LOW |
| - YouTube Music integration | HIGH | LOW |
| **Media Servers** | | |
| - Plex (rescan, ratings) | MEDIUM | MEDIUM |
| - Jellyfin (rescan, ratings) | MEDIUM | MEDIUM |
| - Navidrome (rescan, mapping) | MEDIUM | LOW |
| - Subsonic API | MEDIUM | LOW |
| **Notifications** | | |
| - Discord webhooks | LOW | MEDIUM |
| - Telegram bot | LOW | MEDIUM |
| - Email (SMTP) | LOW | LOW |
| - Smart home integration | MEDIUM | LOW |
| **Last.fm** | | |
| - Scrobbling support | MEDIUM | LOW |
| - Metadata enrichment | LOW | LOW |
| - User statistics | LOW | LOW |

#### 8.3 Analytics & Insights 📈

| Feature | Complexity | Priority |
|---------|-----------|----------|
| Download statistics dashboard | MEDIUM | LOW |
| Library growth tracking | LOW | LOW |
| Genre and artist analytics | MEDIUM | LOW |
| Export reports | LOW | LOW |

#### 8.4 Automation & Workflows 🤖

| Feature | Complexity | Priority |
|---------|-----------|----------|
| Automated playlist imports | LOW | MEDIUM |
| Scheduled synchronization | LOW | MEDIUM |
| Custom automation scripts | MEDIUM | LOW |
| CLI for headless operation | MEDIUM | MEDIUM |
| Webhook triggers | MEDIUM | MEDIUM |

#### 8.5 AI & Machine Learning 🧠

*(VERY HIGH Complexity, Needs Discussion)*

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **AI-Based Matching** | | |
| - Audio fingerprint matching | VERY HIGH | LOW |
| - ML-based track matching | VERY HIGH | LOW |
| - Similarity detection | VERY HIGH | LOW |
| **AI-Powered Tagging** | | |
| - Genre classification | VERY HIGH | LOW |
| - Mood detection | VERY HIGH | LOW |
| - Language detection | MEDIUM | LOW |
| - Tag repair/enrichment | HIGH | LOW |
| **Adaptive Automation** | | |
| - Learn from user decisions | VERY HIGH | LOW |
| - Predictive quality preferences | HIGH | LOW |
| - Personalized matching | HIGH | LOW |
| **Future AI Features** | | |
| - Forecast new releases | VERY HIGH | LOW |
| - Audio repair | VERY HIGH | LOW |
| - Anomaly detection | HIGH | LOW |

#### 8.6 Extended UI Features 🎨

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Browser Extension** | | |
| - "Add to SoulSpot" button | MEDIUM | LOW |
| - Quick playlist import | MEDIUM | LOW |
| - Track search from any page | MEDIUM | LOW |
| **System Tray Integration** | | |
| - Minimal interface | MEDIUM | LOW |
| - Quick access functions | LOW | LOW |
| - Download progress in tray | LOW | LOW |
| **Terminal/Minimal View** | | |
| - Text-based UI | MEDIUM | LOW |
| - Headless operation | LOW | MEDIUM |
| **Enhanced Visualizations** | | |
| - Timeline view for operations | MEDIUM | LOW |
| - Automation center dashboard | MEDIUM | LOW |
| - Metadata manager interface | MEDIUM | LOW |
| - Rating sync interface | LOW | LOW |

---

### Phase 9: Enterprise & Extended Features (Priority: VERY LOW) 📋

**Zeitrahmen:** Q3-Q4 2025 (4-6+ Wochen)  
**Ziel:** Long-term features for advanced users and enterprise deployments.

#### 9.1 Multi-User & Security 👥

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Advanced Authentication** | | |
| - Multi-user support (RBAC) | HIGH | LOW |
| - Admin vs. Read-only roles | MEDIUM | LOW |
| - OAuth/API Key auth | MEDIUM | LOW |
| - IP restriction (optional) | LOW | LOW |
| - Comprehensive audit logs | MEDIUM | LOW |
| **User-specific Features** | | |
| - Per-user download quotas | MEDIUM | LOW |
| - User-specific playlists/libraries | HIGH | LOW |
| - Individual preferences | MEDIUM | LOW |
| **Legal Compliance** | | |
| - Legal mode (restricted features) | MEDIUM | MEDIUM |
| - Opt-in legal notice | LOW | MEDIUM |
| - Compliance tracking | MEDIUM | LOW |

#### 9.2 Plugin System & Extensibility 🔌

*(VERY HIGH Complexity, Security Critical)*

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Plugin Architecture** | | |
| - Plugin SDK/API | VERY HIGH | LOW |
| - Dynamic plugin loading | HIGH | LOW |
| - Plugin marketplace/registry | VERY HIGH | LOW |
| **Extensibility Points** | | |
| - Custom music sources | HIGH | LOW |
| - Custom tagging engines | HIGH | LOW |
| - Custom automation rules | MEDIUM | LOW |
| - Custom post-processing steps | MEDIUM | LOW |
| **Plugin Management** | | |
| - Install/uninstall plugins | MEDIUM | LOW |
| - Plugin versioning | MEDIUM | LOW |
| - Plugin configuration UI | MEDIUM | LOW |

#### 9.3 Multi-Library & Advanced Storage 💾

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Multi-Library Support** | | |
| - Multiple locations (NAS, local, cloud) | HIGH | LOW |
| - Per-library configuration | HIGH | LOW |
| - Library synchronization | VERY HIGH | LOW |
| **Preferred Version Management** | | |
| - Mark preferred versions | MEDIUM | LOW |
| - Quality-based preference | MEDIUM | LOW |
| - Automatic version upgrade | HIGH | LOW |
| **Advanced Storage** | | |
| - Deduplication across libraries | HIGH | LOW |
| - Storage quota management | MEDIUM | LOW |
| - Archive vs. active separation | MEDIUM | LOW |

#### 9.4 Advanced Configuration ⚙️

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Configuration Management** | | |
| - YAML/JSON config files | LOW | LOW |
| - Config versioning | MEDIUM | LOW |
| - Import/export config | LOW | LOW |
| - Config validation | LOW | LOW |
| **Policy Framework** | | |
| - Download policies | MEDIUM | LOW |
| - Automation policies | MEDIUM | LOW |
| - Retention policies | MEDIUM | LOW |
| - Rate limiting policies | LOW | LOW |
| **Multi-Device Sync** | | |
| - Config sync across devices | HIGH | LOW |
| - Queue sync | HIGH | LOW |
| - Shared libraries | VERY HIGH | LOW |

#### 9.5 Experimental Features 🧪

*(Complexity Varies, Needs Evaluation)*

| Feature | Complexity | Priority |
|---------|-----------|----------|
| **Audio Analysis** | | |
| - BPM detection | MEDIUM | LOW |
| - Key detection | MEDIUM | LOW |
| - Loudness normalization | MEDIUM | LOW |
| - Quality assessment | HIGH | LOW |
| **Smart Playlists** | | |
| - Auto-generated mood/genre | HIGH | LOW |
| - Dynamic playlists (listening habits) | HIGH | LOW |
| - Similarity-based auto-playlists | HIGH | LOW |
| **Download Budgeting** | | |
| - Bandwidth budgets | LOW | LOW |
| - Storage budgets | LOW | LOW |
| - Time-based windows | LOW | LOW |
| **Advanced UI** | | |
| - PWA support | MEDIUM | LOW |
| - Offline-first architecture | HIGH | LOW |
| - Real-time collaboration | VERY HIGH | LOW |

---

## 🔄 Continuous Improvements

### Technical Debt

| Item | Priority | Phase |
|------|----------|-------|
| Refactor large use case classes | MEDIUM | Ongoing |
| Improve test coverage to 90%+ | HIGH | Phase 7 |
| Add integration tests for all endpoints | HIGH | Phase 7 |
| Performance profiling & optimization | MEDIUM | Phase 6-7 |
| MusicBrainz rate-limit handling | HIGH | Phase 7 |
| Circuit breaker for external services | MEDIUM | Phase 6-7 |
| Safe atomic file operations | HIGH | Phase 7 |

### Code Quality

| Item | Priority | Phase |
|------|----------|-------|
| Regular dependency updates | HIGH | Ongoing |
| Security vulnerability patching | CRITICAL | Ongoing |
| Code review process improvements | MEDIUM | Ongoing |
| Architecture decision records (ADRs) | LOW | Phase 7+ |

### User Experience

| Item | Priority | Phase |
|------|----------|-------|
| Accessibility (WCAG AAA) | MEDIUM | Phase 8 |
| Internationalization (i18n) | LOW | Phase 8-9 |
| Dark mode refinements | LOW | Phase 7 |
| Responsive design improvements | MEDIUM | Phase 7 |
| Progressive enhancement | LOW | Ongoing |

### Metrics & Monitoring

| Metric | Purpose | Phase |
|--------|---------|-------|
| Job throughput | Performance tracking | Phase 6 |
| Average enrichment time | Optimization | Phase 7 |
| Cache hit rate | Efficiency | Phase 7 |
| External API calls/sec | Rate limiting | Phase 6-7 |
| Failed job ratio | Reliability | Phase 6 |
| Download success rate | Quality | Phase 7 |
| User engagement | Product | Phase 8 |
| Library growth | Analytics | Phase 8 |

---

## 📊 Prioritäts-Matrix

| Phase | Priority | Effort | Impact | Risk | Timeframe |
|-------|----------|--------|--------|------|-----------|
| **Phase 6: Production Readiness** | 🔴 HIGH | HIGH | HIGH | MEDIUM | Q1 2025 |
| **Phase 7: Feature Enhancements** | 🟡 MEDIUM | MEDIUM | HIGH | LOW | Q2 2025 |
| **Phase 8: Advanced Features** | 🟢 LOW | HIGH | MEDIUM | MEDIUM | Q2-Q3 2025 |
| **Phase 9: Enterprise Features** | ⚪ VERY LOW | VERY HIGH | LOW | HIGH | Q3-Q4 2025 |

### Complexity Legend

- **LOW:** 1-3 days development
- **MEDIUM:** 1-2 weeks development
- **HIGH:** 2-4 weeks development
- **VERY HIGH:** Multiple months, significant complexity

---

## 📊 Feature-Kategorien

### Nach Quelle

| Kategorie | Quelle | Status |
|-----------|--------|--------|
| Core Production Features | Original Roadmap | ✅ Mostly Complete |
| Enhanced Download Management | SoulSpot Ideas + Roadmap | 📋 Phase 7 |
| Comprehensive Metadata | SoulSpot Ideas | 📋 Phase 7 |
| Post-Processing Pipeline | SoulSpot Ideas | 🔄 Phase 6-7 |
| Automation & Watchlists | SoulSpot Ideas | 📋 Phase 7 |
| Ratings Sync | SoulSpot Ideas | 📋 Phase 7-8 |
| Advanced Search/Matching | SoulSpot Ideas | 📋 Phase 7 |
| Library Self-Healing | SoulSpot Ideas | 📋 Phase 7 |
| Plugin System | SoulSpot Ideas | 📋 Phase 9 |
| Multi-Library Support | SoulSpot Ideas | 📋 Phase 9 |
| AI/ML Features | SoulSpot Ideas | 🔬 Phase 9+ (Research) |
| Extended UI | SoulSpot Ideas | 📋 Phase 8 |
| Media Server Integrations | Original Roadmap | 📋 Phase 8 |

### Nach Priorität

#### 🔴 Critical (Phase 6)

- CI/CD Pipeline
- Security Hardening
- Performance Optimization
- Production Deployment

#### 🟡 High (Phase 7)

- Priority-based Queue
- Retry Logic Enhancements
- Metadata Conflict Resolution
- Duplicate Detection
- Library Scanning
- Missing Song Discovery
- Playlist Management

#### 🟢 Medium (Phase 7-8)

- Additional Metadata Sources (Discogs, Last.fm)
- Media Server Integrations (Plex, Jellyfin)
- Ratings Synchronization
- Automation & Watchlists
- Advanced Search

#### ⚪ Low (Phase 8-9)

- Mobile Application
- AI/ML Features
- Plugin System
- Multi-Library Support
- Browser Extension

---

## 📅 Release-Plan

### Release Schedule

| Version | Target Date | Focus | Key Features |
|---------|-------------|-------|--------------|
| **0.1.0** | ✅ 2025-11-08 | Alpha Release | Web UI, Basic Features |
| **0.2.0** | Q1 2025 | Beta Release | Production Ready, Docker, Observability |
| **1.0.0** | Q2 2025 | Stable Release | Phase 6-7 Complete |
| **1.1.0** | Q2 2025 | Feature Enhancements | Automation, Ratings, Advanced Search |
| **1.5.0** | Q3 2025 | Advanced Features | Phase 8 Complete |
| **2.0.0** | Q3-Q4 2025 | Major Release | Mobile, AI Features (if viable) |
| **2.5.0** | Q4 2025+ | Enterprise Features | Phase 9 (Multi-user, Plugins) |

### Versioning Strategy

Folgt **[Semantic Versioning (SemVer)](https://semver.org/)**:

- **MAJOR (X.0.0):** Breaking changes, major feature sets
- **MINOR (0.X.0):** New features, backward compatible
- **PATCH (0.0.X):** Bug fixes, security patches

### Release Checklist

Vor jedem Release:

- [ ] Alle Tests bestehen (unit, integration, e2e)
- [ ] Security Scan clean (keine high/critical vulnerabilities)
- [ ] Dokumentation aktualisiert (CHANGELOG, README, API docs)
- [ ] Git Tag erstellt (vX.Y.Z)
- [ ] Docker Images gebaut und published
- [ ] Release Notes geschrieben
- [ ] Rollback-Plan dokumentiert
- [ ] Breaking Changes klar kommuniziert

---

## 📋 Default Policies & Configuration

### Rate Limiting & External APIs

| Service | Rate Limit | Policy |
|---------|-----------|--------|
| **MusicBrainz** | 1 req/sec | Strict, worker queue |
| **Spotify API** | Variable | Exponential backoff |
| **slskd API** | 2-3 concurrent | Configurable |

### Metadata Merge Priority

**Empfohlene Hierarchie:**

```
1. Manual User Edits      (Höchste Priorität)
2. MusicBrainz           (Canonical Data)
3. Discogs               (Release Details)
4. Spotify               (Popularity, Modern Names)
5. Last.fm               (Fallback)
6. File Tags             (Niedrigste Priorität)
```

**Offene Frage:** Should Spotify be prioritized higher for certain fields like popularity or user-facing names?

### Download Policies

| Parameter | Default | Range |
|-----------|---------|-------|
| **Parallel Downloads** | 2 | 1-5 |
| **Retry Policy** | 3 attempts | Exponential backoff (1s, 2s, 4s) |
| **Min Quality** | 128kbps | Configurable |
| **Format Preference** | FLAC > 320 MP3 > 256 > 192 | Configurable |

### Legal & Compliance

- **Legal Opt-in:** Required before automated downloads
- **Audit Logging:** All downloads logged (timestamp, source, user)
- **Legal Mode:** Optional restricted mode

### Storage & Organization

**Empfohlene Ordnerstruktur:**

```
/music-library/
  /downloads/          # Temporary download location
  /sorting/            # Post-processing staging area
  /new-artists/        # Recently added artists
  /unknown-album/      # Files without album metadata
  /library/            # Final organized library
    /Artist Name/
      /Album Name (Year)/
        01 - Track.flac
        cover.jpg
```

---

## 🤝 Contributing

### Wie man beiträgt

1. **Lies den [Contributing Guide](contributing.md)**
2. **Check [GitHub Issues](https://github.com/bozzfozz/soulspot-bridge/issues)**
3. **Erstelle ein neues Issue** mit [Feature Request Template](../.github/ISSUE_TEMPLATE/feature_request.md)
4. **Diskutiere in Roadmap-Diskussionen**
5. **Submit Pull Requests** für Features die du implementieren möchtest

### Good First Issues

#### Phase 6-7 Quick Wins (LOW Complexity)

| Task | Complexity | Phase |
|------|-----------|-------|
| **spotify-oauth-enhancements** | LOW | Phase 6 |
| - Improve OAuth PKCE documentation | | |
| - Add manual testing guide | | |
| - Enhance error messages | | |
| **queue-basic-improvements** | LOW | Phase 7 |
| - Add pagination to job list endpoint | | |
| - Improve job status filtering | | |
| - Add job statistics endpoint | | |
| **safe-tag-writes** | LOW | Phase 7 |
| - Implement atomic temp-write + replace | | |
| - Add error handling | | |
| - Add rollback on failure | | |
| **cover-download-multi-source** | LOW-MEDIUM | Phase 7 |
| - Extend cover download multi-source | | |
| - Add CoverArtArchive integration | | |
| - Support multiple resolutions | | |

### Help Wanted Tasks (MEDIUM Complexity)

| Task | Complexity | Phase |
|------|-----------|-------|
| **batch-download-csv-import** | MEDIUM | Phase 7 |
| - Implement CSV/JSON batch import UI | | |
| - Add validation and preview | | |
| - Support M3U playlist import | | |
| **download-scheduler** | MEDIUM | Phase 7 |
| - Implement CRON scheduling | | |
| - Add "night mode" | | |
| - UI for schedule configuration | | |
| **musicbrainz-enrichment-advanced** | MEDIUM | Phase 7 |
| - Advanced MusicBrainz with caching | | |
| - Rate-limit handling with worker | | |
| - Comprehensive unit tests | | |
| **retry-resume-enhanced** | MEDIUM | Phase 7 |
| - Sophisticated retry logic | | |
| - Resume after restart | | |
| - Alternative source discovery | | |
| **ratings-sync-connector** | MEDIUM | Phase 7-8 |
| - Plex API connector for ratings | | |
| - Dry-run mode | | |
| - Conflict resolution UI | | |

### Advanced Tasks (HIGH Complexity)

| Task | Complexity | Phase |
|------|-----------|-------|
| **smart-matching-heuristics** | MEDIUM-HIGH | Phase 7 |
| - Fuzzy matching for tracks | | |
| - Score-based algorithm | | |
| - Configurable thresholds | | |
| **metadata-merge-logic** | HIGH | Phase 7 |
| - Multi-source metadata merging | | |
| - Authority hierarchy | | |
| - Tag normalization | | |
| - Batch tag fixer UI | | |
| **missing-song-discovery** | MEDIUM | Phase 7 |
| - Library scanner (playlist vs. local) | | |
| - Missing track reporting | | |
| - CSV/JSON export | | |

---

## ❓ Offene Fragen & Decision Points

### Technische Entscheidungen

#### 1. Ratings Sync Strategy

**Frage:** One-way (Plex→SoulSpot) oder bidirektional?

- **Konfliktbehandlung:** Welches System gewinnt?
- **Rating Scale:** 5-star vs 10-point als kanonisch?
- **Empfehlung:** Start with one-way, evolve to bidirectional after testing

#### 2. Audio Fingerprinting Timeline

**Frage:** Phase 7 oder Phase 8/9?

- **Komplexität:** Significant complexity and performance impact
- **Empfehlung:** Phase 8 (Advanced Features) mit opt-in flag

#### 3. Metadata Priority für Specific Fields

**Frage:** Spotify für Popularity, moderne Artist-Namen priorisieren?

- **Canonical vs. User-friendly:** MusicBrainz canonical vs. Spotify user-facing
- **Empfehlung:** Configurable per-field priority, with sensible defaults

#### 4. Legal Mode Restrictions

**Frage:** Welche Features in Legal Mode einschränken?

- **Automation:** Wie strikt?
- **Empfehlung:** Clear boundaries, extensive documentation, explicit opt-in

#### 5. Plugin System Scope

**Frage:** Phase 8 oder Phase 9?

- **Security:** Implications of arbitrary plugins
- **Empfehlung:** Phase 9, with careful security review

#### 6. Multi-User Implementation

**Frage:** Simple RBAC oder full multi-tenancy?

- **Libraries:** Shared vs. private?
- **Empfehlung:** Start with simple RBAC (admin/user), evolve based on demand

### Community Input Needed

Diese Features sollten mit Users/Contributors diskutiert werden:

- [ ] Preferred default quality settings
- [ ] Folder structure preferences
- [ ] Rating sync behavior expectations
- [ ] Automation aggressiveness
- [ ] Privacy expectations for metadata caching
- [ ] Acceptable external service dependencies

---

## 📝 Changelog

### 2025-11-10: Major Roadmap Redesign

**Durchgeführt von:** Copilot Agent

**Änderungen:**

- ✅ **Komplett neue Struktur** – Roadmap von Grund auf neu organisiert
- ✅ **Vision & Gesamtziel** als dedizierter Abschnitt
- ✅ **Kernkonzepte & Architektur** mit thematischen Tabellen:
  - Musik-Quellen, Metadaten-Quellen, Media-Server, Benachrichtigungen
  - Suche & Matching-Engine
  - Download-System & Queue-Management
  - Post-Processing Pipeline (Flowchart)
  - Metadata-Engine & Authority System
  - Library-Management & Self-Healing
  - Automation & Watchlists ("arr"-Style)
  - Ratings & Playcount Sync
- ✅ **Entwicklungsphasen** detailliert ausgearbeitet:
  - Phase 6-9 vollständig strukturiert mit Tabellen
  - Jede Task mit Status, Komplexität, Priorität
- ✅ **Feature-Kategorien** nach Quelle und Priorität
- ✅ **Prioritäts-Matrix** übersichtlich dargestellt
- ✅ **Release-Plan** mit Zeitachse und Checklist
- ✅ **Default Policies & Configuration** als eigener Bereich
- ✅ **Contributing** mit Good First Issues und Help Wanted
- ✅ **Offene Fragen** strukturiert dokumentiert
- ✅ **Inhaltsverzeichnis** mit Sprunglinks
- ✅ **Markdown-Struktur** durchgehend konsistent
- ✅ **Ideensammlung-Block entfernt** – Inhalt vollständig integriert

**Impact:**

- Roadmap ist jetzt professionell, übersichtlich und contributor-freundlich
- Vision und Architektur klar dokumentiert
- Features logisch gruppiert und priorisiert
- Klare Zeitachsen und Meilensteine
- Offene Fragen transparent dokumentiert
- Ready for contributors!

**Vorher:** 1293 Zeilen (Block-Integration)  
**Nachher:** ~1800 Zeilen (strukturiert, professional)

---

**Ende des Roadmap-Dokuments**
