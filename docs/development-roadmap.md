# SoulSpot Bridge – Development Roadmap

> **Letzte Aktualisierung:** 2025-11-11  
> **Version:** 0.1.0 (Alpha)  
> **Status:** Phase 6 In Progress - Production Readiness + v2.0 Planning Complete + v3.0 Roadmap Defined

---

## 📑 Inhaltsverzeichnis

1. [Vision & Gesamtziel](#-vision--gesamtziel)
2. [Aktueller Status](#-aktueller-status)
3. [Kernkonzepte & Architektur](#-kernkonzepte--architektur)
4. [Entwicklungsphasen](#-entwicklungsphasen)
5. [v3.0 — Production Hardening & Enterprise Deployment](#-version-30--production-hardening--enterprise-deployment-geplant)
6. [v2.0 — Dynamic Views & Widget-Palette](#-v20--dynamic-views--widget-palette-geplant)
7. [Feature-Kategorien](#-feature-kategorien)
8. [Prioritäts-Matrix](#-prioritäts-matrix)
9. [Release-Plan](#-release-plan)
10. [Contributing](#-contributing)
11. [Offene Fragen](#-offene-fragen)

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

**Fortschritt:** ~80% (8/10 Hauptkomponenten abgeschlossen)

**Abgeschlossen:**
- ✅ Structured Logging (JSON, Correlation IDs)
- ✅ Enhanced Health Checks (Liveness, Readiness, Dependencies)
- ✅ Docker Production Setup (Multi-stage Build, Security Hardening)
- ✅ Docker Compose Configuration (slskd Integration, Volume Management)
- ✅ Docker Entrypoint Script (Directory Validation, PUID/PGID)
- ✅ Auto Music Import Service (Background File Moving)
- ✅ CI/CD Pipeline (GitHub Actions)
- ✅ Automated Release Process
- ✅ Deployment Automation (Dev, Staging, Prod)

**In Arbeit:**
- 🔄 Performance Optimization
- 🔄 Operations Documentation

**Nächste Schritte:** [Phase 6 Details](#phase-6-production-readiness-priority-high)

> **Note:** Advanced features originally planned for Phase 6 (v3.0 features such as Production Profile with PostgreSQL/Redis/nginx, Kubernetes, OWASP security hardening) have been moved to the dedicated [Version 3.0 section](#-version-30--production-hardening--enterprise-deployment-geplant) to keep Phase 6 focused and achievable.

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
| Circuit Breaker Patterns | ✅ Done | MEDIUM |

> **Note:** Advanced monitoring features (Prometheus Metrics Endpoint, OpenTelemetry Integration, Distributed Tracing, KPI/Business Metrics) were removed from v2.0 scope as they have not been implemented. These may be reconsidered for future versions if needed.

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
| Deployment Automation (Dev, Staging, Prod) | ✅ Done | HIGH |

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

> **Note:** Advanced deployment features (Production Profile with PostgreSQL/Redis/nginx, Kubernetes Manifests) have been moved to v3.0 scope as they are not required for current production readiness. See [Version 3.0 section](#-version-30--production-hardening--enterprise-deployment-geplant) for details.

#### 6.4 Security Hardening 🔒

> **Note:** Advanced security features (OWASP Top 10 Compliance, Input Validation Hardening, Secrets Management, Rate Limiting, Brute Force Protection, Session Timeout) have been moved to v3.0 scope. Basic security measures are implemented in Phase 6. See [Version 3.0 section](#-version-30--production-hardening--enterprise-deployment-geplant) for enterprise-grade security features.

#### 6.5 Performance Optimization ⚡

| Task | Status | Complexity |
|------|--------|-----------|
| Database Query Optimization | 📋 Planned | MEDIUM |
| Missing Index Analysis | 📋 Planned | LOW |
| Connection Pool Tuning | 📋 Planned | MEDIUM |
| Response Compression | 📋 Planned | LOW |
| Pagination for Large Results | 📋 Planned | LOW |
| Query Batching | 📋 Planned | MEDIUM |
| Async Heavy Operations | 📋 Planned | MEDIUM |

> **Note:** Advanced performance features (Redis Integration for Distributed Cache) have been moved to v3.0 scope. See [Version 3.0 section](#-version-30--production-hardening--enterprise-deployment-geplant) for details.

#### 6.6 Operations Documentation 📚

| Task | Status | Complexity |
|------|--------|-----------|
| Docker Setup Guide | ✅ Done | LOW |
| Troubleshooting Guide | ✅ Done | LOW |
| Operations Runbook | 📋 Planned | MEDIUM |
| API Documentation Enhancements | 📋 Planned | LOW |

> **Note:** Advanced operational features (Backup & Recovery Procedures, Rollback Procedures) have been moved to v3.0 scope. See [Version 3.0 section](#-version-30--production-hardening--enterprise-deployment-geplant) for enterprise operational excellence features.

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

## 🔒 Version 3.0 — Production Hardening & Enterprise Deployment (Geplant)

**Status:** 🔮 Planned for Version 3.0  
**Zeitrahmen:** 2026+ (nach Phase 9 und v2.x)  
**Priorität:** 🔴 HIGH (Next Major Production Release)  
**Gesamtaufwand:** ~15-20 Dev Days

### 🎯 Vision & Ziele

**Version 3.0 Production Hardening & Enterprise Deployment** transformiert SoulSpot Bridge von einer funktionalen Anwendung zu einer hochverfügbaren, produktionsreifen Enterprise-Lösung mit vollständiger Sicherheitshärtung, skalierbarer Infrastruktur und operationeller Exzellenz.

**Kernprinzipien:**
- 🔒 **Security-First:** OWASP Top 10 Compliance, Input Validation, Secrets Management
- 🚀 **Production-Ready:** PostgreSQL, Redis, nginx für skalierbaren Betrieb
- ☸️ **Cloud-Native:** Kubernetes-Support für Container-Orchestrierung
- 🔄 **Operational Excellence:** Backup/Recovery, Rollback-Procedures
- 📊 **Enterprise-Grade:** Rate Limiting, Brute Force Protection, Session Management

### 📋 Feature-Übersicht

#### 3.1 Production Profile (PostgreSQL, Redis, nginx) 🐘

**Beschreibung:** Vollständiges Production-Deployment-Profil mit skalierbarer Infrastruktur.

**Komponenten:**

| Komponente | Zweck | Complexity |
|------------|-------|-----------|
| **PostgreSQL Integration** | Production-ready relational database | HIGH |
| - Database connection pooling | Efficient connection management | MEDIUM |
| - Migration strategy from SQLite | Data migration tools | HIGH |
| - Backup & restore procedures | Data protection | MEDIUM |
| **Redis Integration** | Distributed caching & session storage | HIGH |
| - Session management | Centralized session store | MEDIUM |
| - Cache layer | Performance optimization | MEDIUM |
| - Queue management | Distributed job processing | HIGH |
| **nginx Reverse Proxy** | Production web server | MEDIUM |
| - SSL/TLS termination | Secure connections | MEDIUM |
| - Load balancing | Traffic distribution | HIGH |
| - Rate limiting | DDoS protection | MEDIUM |
| - Static file serving | Performance optimization | LOW |

**Status:** 🔮 v3.0  
**Aufwand:** 5-7 days

---

#### 3.2 Kubernetes Manifests ☸️

**Beschreibung:** Container-Orchestrierung für Cloud-Native Deployments.

**Features:**

| Feature | Beschreibung | Complexity |
|---------|--------------|-----------|
| **Deployment Manifests** | | |
| - Application deployment | StatefulSet/Deployment configs | HIGH |
| - Database StatefulSet | Persistent PostgreSQL | HIGH |
| - Redis StatefulSet | Distributed cache | MEDIUM |
| - ConfigMaps & Secrets | Configuration management | MEDIUM |
| **Service & Networking** | | |
| - Service definitions | Internal/external services | MEDIUM |
| - Ingress configuration | External access & routing | MEDIUM |
| - Network policies | Security & isolation | MEDIUM |
| **Persistence & Storage** | | |
| - PersistentVolumeClaims | Storage provisioning | MEDIUM |
| - StorageClass definitions | Storage tiers | LOW |
| - Backup volumes | Data protection | MEDIUM |
| **Scaling & Monitoring** | | |
| - HorizontalPodAutoscaler | Auto-scaling rules | HIGH |
| - Resource limits & requests | Resource management | MEDIUM |
| - Liveness & readiness probes | Health monitoring | LOW |
| **Helm Charts** | | |
| - Chart structure | Package management | HIGH |
| - Values files | Environment configs | MEDIUM |
| - Release management | Version control | MEDIUM |

**Status:** 🔮 v3.0  
**Aufwand:** 6-8 days

---

#### 3.3 Security Hardening 🔒

**Beschreibung:** Umfassende Sicherheitshärtung nach OWASP Best Practices.

**Features:**

| Feature | Beschreibung | Complexity |
|---------|--------------|-----------|
| **OWASP Top 10 Compliance Check** | | |
| - Injection prevention | SQL/Command/Code injection | MEDIUM |
| - Broken authentication | Auth mechanism review | MEDIUM |
| - Sensitive data exposure | Data protection audit | MEDIUM |
| - XML external entities (XXE) | XML parsing security | LOW |
| - Broken access control | Authorization review | MEDIUM |
| - Security misconfiguration | Config hardening | LOW |
| - Cross-site scripting (XSS) | Input sanitization | MEDIUM |
| - Insecure deserialization | Data validation | MEDIUM |
| - Using components with known vulnerabilities | Dependency scanning | LOW |
| - Insufficient logging & monitoring | Audit logging | LOW |
| **Input Validation Hardening** | | |
| - Request validation middleware | Schema validation | MEDIUM |
| - Sanitization layer | XSS/Injection prevention | MEDIUM |
| - File upload validation | Safe file handling | MEDIUM |
| - Path traversal protection | Directory access control | LOW |
| **Secrets Management** | | |
| - Environment-based secrets | Config externalization | MEDIUM |
| - Vault integration (optional) | Secure secret storage | HIGH |
| - Secret rotation | Key management | MEDIUM |
| - Encrypted storage | Data protection | MEDIUM |
| **Rate Limiting for Auth Endpoints** | | |
| - Login rate limiting | Brute force prevention | LOW |
| - Token refresh limits | Token abuse prevention | LOW |
| - API key rate limits | Usage control | LOW |
| **Brute Force Protection** | | |
| - Account lockout | Failed login limits | MEDIUM |
| - CAPTCHA integration | Bot prevention | MEDIUM |
| - IP-based throttling | Distributed attack prevention | MEDIUM |
| **Session Timeout Configuration** | | |
| - Idle timeout | Automatic logout | LOW |
| - Absolute timeout | Max session duration | LOW |
| - Concurrent session limits | Multi-login control | LOW |

**Status:** 🔮 v3.0  
**Aufwand:** 4-5 days

---

#### 3.4 Operational Excellence 🔄

**Beschreibung:** Best Practices für Betrieb und Wartung.

**Features:**

| Feature | Beschreibung | Complexity |
|---------|--------------|-----------|
| **Backup & Recovery Procedures** | | |
| - Automated database backups | Scheduled backup jobs | MEDIUM |
| - File system backups | User data protection | MEDIUM |
| - Point-in-time recovery | Restore to specific moment | HIGH |
| - Backup validation | Ensure backup integrity | LOW |
| - Disaster recovery plan | Full system recovery | MEDIUM |
| **Rollback Procedures** | | |
| - Database rollback scripts | Schema version control | LOW |
| - Application version rollback | Container rollback | LOW |
| - Configuration rollback | Config version control | LOW |
| - Automated rollback triggers | Failure detection | MEDIUM |

**Status:** 🔮 v3.0  
**Aufwand:** 2-3 days

---

### 🧪 Acceptance Criteria (Version 3.0)

#### Funktionale Anforderungen

- [ ] **Production Profile:** PostgreSQL + Redis + nginx vollständig konfiguriert und getestet
- [ ] **Kubernetes:** Alle Manifests funktionieren in Minikube und produktiven Clustern
- [ ] **Security:** OWASP Top 10 Compliance erreicht (Security Audit bestanden)
- [ ] **Rate Limiting:** Auth-Endpoints sind geschützt (max 5 requests/minute)
- [ ] **Brute Force:** Account-Lockout nach 5 fehlgeschlagenen Versuchen
- [ ] **Session Management:** Idle/Absolute Timeouts konfigurierbar
- [ ] **Backup/Recovery:** Automatische Backups funktionieren, Recovery getestet
- [ ] **Rollback:** Zero-downtime Rollback für App und DB

#### Non-Funktionale Anforderungen

- [ ] **Performance:** PostgreSQL + Redis < 50ms p95 Latency
- [ ] **Scalability:** Horizontal Scaling auf 3+ Replicas getestet
- [ ] **Availability:** 99.9% Uptime in Testumgebung über 1 Woche
- [ ] **Security:** Zero Critical/High Vulnerabilities (Bandit, Safety, OWASP ZAP)
- [ ] **Documentation:** Vollständige Deployment-Docs, Runbooks, Security-Guidelines
- [ ] **Compliance:** OWASP Top 10 Compliance nachgewiesen

#### Definition of Done

- [ ] Production Profile vollständig implementiert und dokumentiert
- [ ] Kubernetes Manifests + Helm Charts erstellt und getestet
- [ ] OWASP Top 10 Compliance erreicht (Audit-Report)
- [ ] Input Validation & Secrets Management implementiert
- [ ] Rate Limiting & Brute Force Protection aktiv
- [ ] Session Timeout konfigurierbar
- [ ] Backup/Recovery-Procedures dokumentiert und getestet
- [ ] Rollback-Procedures dokumentiert und getestet
- [ ] Unit-Tests für alle Security-Features (Coverage > 90%)
- [ ] Integration-Tests für Production Profile
- [ ] E2E-Tests für kritische Security-Flows
- [ ] Security-Review abgeschlossen (Penetration-Test empfohlen)
- [ ] Operations-Runbook vollständig
- [ ] Migration-Guide von v2.x zu v3.0 erstellt

---

### 🗓️ Zeitplan & Sprint-Aufteilung

**Gesamtaufwand:** ~15-20 Dev Days

#### Sprint 1: Infrastructure (1 Woche / 5 Arbeitstage)
- **Production Profile:** PostgreSQL + Redis + nginx (5-7 days)
  - PostgreSQL Integration (2 days)
  - Redis Integration (2 days)
  - nginx Configuration (1-2 days)
  - Migration Scripts (1 day)
- **Deliverables:** Funktionierendes Production Profile

#### Sprint 2: Cloud-Native (1-2 Wochen / 6-8 Arbeitstage)
- **Kubernetes Manifests:** (6-8 days)
  - Deployment Manifests (2 days)
  - Service & Networking (1 day)
  - Persistence & Storage (1 day)
  - Scaling & Monitoring (1 day)
  - Helm Charts (2-3 days)
- **Deliverables:** Funktionierendes K8s Deployment

#### Sprint 3: Security Hardening (1 Woche / 4-5 Arbeitstage)
- **Security Features:** (4-5 days)
  - OWASP Compliance (2 days)
  - Input Validation & Secrets (1 day)
  - Rate Limiting & Brute Force (1 day)
  - Session Management (0.5 day)
  - Security Testing (0.5 day)
- **Deliverables:** OWASP-compliant Application

#### Sprint 4: Operations & Polish (1 Woche / 2-3 Arbeitstage)
- **Operational Excellence:** (2-3 days)
  - Backup & Recovery (1.5 days)
  - Rollback Procedures (0.5 day)
  - Documentation & Runbooks (1 day)
  - Final Testing & Validation (1 day)
- **Deliverables:** Production-Ready v3.0

**Total Timeline:** 3-4 Sprints (je 1 Woche) = ~3-4 Wochen

---

### 📈 Release-Integration

**Breaking Changes (3.0.0):**
- Neue Production Profile Requirements (PostgreSQL, Redis)
- Geänderte Deployment-Architektur (Kubernetes-native)
- Erweiterte Security-Anforderungen (OWASP-konform)
- Neue Environment-Variables für Secrets Management

**Migration Path von 2.x zu 3.0:**
- SQLite → PostgreSQL Migration-Tool
- Simple Profile → Production Profile Upgrade-Guide
- Session-Storage Migration zu Redis
- Security-Settings Review & Update

---

### 🎯 Success Metrics

**Production Metrics:**
- [ ] PostgreSQL Uptime > 99.9%
- [ ] Redis Cache Hit Rate > 80%
- [ ] nginx Request Latency < 10ms p95
- [ ] Kubernetes Pod Startup Time < 30s
- [ ] Auto-Scaling funktioniert (Load-Test bestanden)

**Security Metrics:**
- [ ] OWASP Top 10 Compliance: 10/10
- [ ] Zero Critical/High Vulnerabilities
- [ ] Rate Limiting: 100% Auth-Endpoint-Abdeckung
- [ ] Brute Force Prevention: 0 erfolgreiche Angriffe im Test
- [ ] Session Timeout: 100% konfigurierbar

**Operational Metrics:**
- [ ] Backup Success Rate: 100%
- [ ] Recovery Time Objective (RTO): < 15 minutes
- [ ] Recovery Point Objective (RPO): < 5 minutes
- [ ] Rollback Success Rate: 100%

---

## 🎨 v2.0 — Dynamic Views & Widget-Palette (Geplant)

**Status:** 📋 Planned  
**Zeitrahmen:** Q3-Q4 2025 (nach Phase 9)  
**Priorität:** 🔵 STRATEGIC (Next Major Release)  
**Gesamtaufwand:** ~20-26 Dev Days (aufteilbar in 3-5 Sprints)

### 🎯 Vision & Ziele

**v2.0 Dynamic Views & Widget-Palette** transformiert SoulSpot Bridge von einem funktionalen Tool zu einer flexiblen, personalisierbaren Arbeitsumgebung. Nutzer können ihre Arbeitsoberfläche individuell gestalten, relevante Widgets per Drag & Drop anordnen, konfigurieren und als wiederverwendbare Views speichern.

**Kernprinzipien:**
- 🎨 **User-Centric Design:** Nutzer definieren ihre optimale Arbeitsumgebung
- 🧩 **Modularität:** Widgets sind unabhängige, konfigurierbare Komponenten
- 🔄 **Wiederverwendbarkeit:** Views können gespeichert, geteilt und exportiert werden
- 🚫 **Keine Telemetrie:** Kein Tracking, keine Performance-Metriken, keine Datensammlung
- 🔒 **Security-First:** Alle Aktionen serverseitig validiert und autorisiert

### 🎯 MVP-Scope & Abgrenzungen

**✅ Im Scope (MVP):**
- Grid-basiertes Canvas für Widget-Platzierung (Drag & Drop)
- Widget-Palette mit vorkonfigurierten Standard-Widgets
- Widget-Konfiguration via Settings-Modal (settingsSchema)
- Speichern/Laden von Views (pro User, DB-persistiert)
- Composite Widgets (Parent mit children, selection-sync)
- Berechtigungsprüfung für destruktive Widget-Aktionen
- 5 Core Widgets (Active Jobs, Spotify Search, Missing Tracks, Quick Actions, Metadata Manager)

**❌ Explizit NICHT im Scope:**
- ❌ Performance-Metriken, Telemetrie oder Analytics
- ❌ Widget-in-Browser-Extension oder Mobile-App
- ❌ Echtzeit-Kollaboration (Team-Views)
- ❌ Automatisches Widget-Layout-Optimization
- ❌ AI-basierte Widget-Recommendations
- ❌ Widget-Marketplace oder Plugin-System (siehe Phase 9)

### 📋 Meilensteine & Phasen

| Phase | Ziel | Aufwand | Dependencies |
|-------|------|---------|--------------|
| **A: Design & Architektur** | Wireframes, Widget-Registry-Schema, Settings-Schema | 1-2 days | Design-System v1.0 |
| **B: Infrastructure MVP** | Grid Canvas, Widget Palette, Drag & Drop, Save/Load Views | 5 days | Phase A complete |
| **C: Widgets MVP** | 5 Core Widgets (Active Jobs, Spotify Search, Missing Tracks, Quick Actions, Metadata Manager) | 7-10 days | Phase B complete |
| **D: Composite Widgets & Permissions** | Widget-in-widget, Role checks, Server-side validation | 4-6 days | Phase C complete |
| **E: Polish & Docs** | Settings-Schemas, Examples, Usage Docs, Testing | 2-3 days | Phase D complete |
| **F: Optional Extensions** | Sharing/Team-Views, Templates, Export/Import (optional) | 3-5 days | Phase E complete |

**Kritischer Pfad:** A → B → C → D → E (Minimal: ~19 days)  
**Mit Optional Features:** A → B → C → D → E → F (~24 days)

---

### 🏗️ Architektur & Technische Konzepte

#### Widget-Registry (Serverseitig)

Die **Widget-Registry** ist die zentrale Verwaltung aller verfügbaren Widgets. Sie definiert:
- Widget-ID und Metadaten (Name, Beschreibung, Kategorie, Icon)
- Settings-Schema (JSON Schema) für Konfiguration
- Verfügbare Actions mit Required Permissions
- Standard-Größe und Layout-Constraints

**Beispiel Widget-Definition:**

```json
{
  "id": "active-jobs-widget",
  "name": "Active Jobs",
  "description": "Zeigt laufende Download- und Processing-Jobs",
  "category": "monitoring",
  "icon": "activity",
  "defaultSize": { "w": 4, "h": 3 },
  "minSize": { "w": 2, "h": 2 },
  "maxSize": { "w": 12, "h": 6 },
  "settingsSchema": {
    "type": "object",
    "properties": {
      "showCompleted": { "type": "boolean", "default": false },
      "maxItems": { "type": "integer", "default": 10, "minimum": 5, "maximum": 50 },
      "refreshInterval": { "type": "integer", "default": 5, "minimum": 1, "maximum": 60 }
    }
  },
  "actions": [
    { "id": "pause", "label": "Pause Job", "permission": "jobs:write" },
    { "id": "cancel", "label": "Cancel Job", "permission": "jobs:write" },
    { "id": "retry", "label": "Retry Job", "permission": "jobs:write" }
  ],
  "supportedEvents": ["job.created", "job.updated", "job.completed"]
}
```

#### Saved View (Persistierung)

Ein **Saved View** ist die persistierte Konfiguration einer User-View:

```json
{
  "id": "view_123",
  "userId": "user_456",
  "name": "My Dashboard",
  "description": "Custom dashboard for music management",
  "isDefault": false,
  "createdAt": "2025-11-11T12:00:00Z",
  "updatedAt": "2025-11-11T14:30:00Z",
  "layout": {
    "gridColumns": 12,
    "gridRows": "auto",
    "gap": 16
  },
  "widgets": [
    {
      "instanceId": "widget_inst_001",
      "widgetId": "active-jobs-widget",
      "position": { "x": 0, "y": 0, "w": 6, "h": 3 },
      "settings": {
        "showCompleted": true,
        "maxItems": 20,
        "refreshInterval": 10
      }
    },
    {
      "instanceId": "widget_inst_002",
      "widgetId": "spotify-search-widget",
      "position": { "x": 6, "y": 0, "w": 6, "h": 3 },
      "settings": {
        "searchMode": "tracks",
        "autoDownload": false
      }
    },
    {
      "instanceId": "widget_inst_003",
      "widgetId": "composite-dashboard-widget",
      "position": { "x": 0, "y": 3, "w": 12, "h": 4 },
      "settings": {
        "title": "Library Overview"
      },
      "children": [
        {
          "instanceId": "widget_inst_004",
          "widgetId": "missing-tracks-widget",
          "position": { "x": 0, "y": 0, "w": 6, "h": 4 },
          "settings": { "playlistId": "playlist_789" }
        },
        {
          "instanceId": "widget_inst_005",
          "widgetId": "metadata-manager-widget",
          "position": { "x": 6, "y": 0, "w": 6, "h": 4 },
          "settings": { "scope": "untagged" }
        }
      ]
    }
  ]
}
```

#### Composite Widgets

**Composite Widgets** sind Container-Widgets, die andere Widgets (children) enthalten können:

- **Parent Widget:** Verwaltet Layout und Kontext für Children
- **Children:** Normale Widgets, die im Parent-Kontext laufen
- **Selection-Sync:** Wenn ein Child eine Auswahl trifft, können andere Children darauf reagieren
- **Event-Propagation:** Parent kann Events an Children weiterleiten

**Beispiel: Composite Dashboard Widget**
```
┌─────────────────────────────────────────────────────┐
│ Composite: Library Overview                         │
├────────────────────┬────────────────────────────────┤
│ Missing Tracks     │ Metadata Manager               │
│ - Track A (Album)  │ - Untagged Files: 45           │
│ - Track B (Album)  │ - Missing Artwork: 12          │
│ - Track C (Single) │ - Conflicts: 3                 │
│                    │                                │
│ [Select All]       │ [Fix Selected]                 │
└────────────────────┴────────────────────────────────┘
```

Wenn User im "Missing Tracks" Widget einen Track auswählt, kann "Metadata Manager" automatisch die Metadaten dieses Tracks laden.

---

### 🔌 API-Contracts & Endpoints

#### 1. Widget Registry

**GET /api/widgets**

Liefert alle verfügbaren Widgets mit Schemas:

```http
GET /api/widgets HTTP/1.1
Authorization: Bearer <token>
```

**Response:**
```json
{
  "widgets": [
    {
      "id": "active-jobs-widget",
      "name": "Active Jobs",
      "description": "...",
      "category": "monitoring",
      "icon": "activity",
      "defaultSize": { "w": 4, "h": 3 },
      "settingsSchema": { ... },
      "actions": [ ... ]
    },
    { ... }
  ]
}
```

**Status Codes:**
- `200 OK` – Registry erfolgreich geladen
- `401 Unauthorized` – Fehlende/ungültige Authentifizierung
- `403 Forbidden` – User hat keine Berechtigung

---

#### 2. Views Management

**GET /api/views**

Listet alle gespeicherten Views des aktuellen Users:

```http
GET /api/views HTTP/1.1
Authorization: Bearer <token>
```

**Response:**
```json
{
  "views": [
    {
      "id": "view_123",
      "name": "My Dashboard",
      "description": "Custom dashboard",
      "isDefault": true,
      "createdAt": "2025-11-11T12:00:00Z",
      "updatedAt": "2025-11-11T14:30:00Z",
      "widgetCount": 5
    },
    { ... }
  ]
}
```

---

**GET /api/views/:id**

Lädt eine spezifische View mit vollständiger Konfiguration:

```http
GET /api/views/view_123 HTTP/1.1
Authorization: Bearer <token>
```

**Response:** Vollständiges View-JSON (siehe "Saved View" oben)

**Status Codes:**
- `200 OK` – View erfolgreich geladen
- `404 Not Found` – View existiert nicht oder User hat keine Berechtigung
- `401 Unauthorized` – Fehlende Authentifizierung

---

**POST /api/views**

Erstellt oder aktualisiert eine View:

```http
POST /api/views HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "id": "view_123",  // Optional: wenn vorhanden, wird Update durchgeführt
  "name": "My Dashboard",
  "description": "Custom dashboard for music management",
  "isDefault": false,
  "layout": { ... },
  "widgets": [ ... ]
}
```

**Response:**
```json
{
  "id": "view_123",
  "name": "My Dashboard",
  "createdAt": "2025-11-11T12:00:00Z",
  "updatedAt": "2025-11-11T14:35:00Z"
}
```

**Validierung (Serverseitig):**
- Widget-IDs müssen in Registry existieren
- Settings müssen gegen settingsSchema validiert werden
- Position-Constraints (minSize, maxSize) prüfen
- User darf nur eigene Views erstellen/ändern (oder Admin-Rolle)

**Status Codes:**
- `200 OK` – View erfolgreich aktualisiert
- `201 Created` – View erfolgreich erstellt
- `400 Bad Request` – Validierungsfehler (ungültiges Schema, fehlende Felder)
- `403 Forbidden` – User darf View nicht ändern
- `401 Unauthorized` – Fehlende Authentifizierung

---

**DELETE /api/views/:id**

Löscht eine View:

```http
DELETE /api/views/view_123 HTTP/1.1
Authorization: Bearer <token>
```

**Status Codes:**
- `204 No Content` – View erfolgreich gelöscht
- `404 Not Found` – View existiert nicht
- `403 Forbidden` – User darf View nicht löschen
- `401 Unauthorized` – Fehlende Authentifizierung

---

#### 3. Widget Actions

**POST /api/widgets/:instanceId/action**

Führt eine Widget-Action aus (z. B. "Pause Job", "Download Track"):

```http
POST /api/widgets/widget_inst_001/action HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "actionId": "pause",
  "payload": {
    "jobId": "job_789"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Job paused successfully",
  "result": {
    "jobId": "job_789",
    "status": "paused"
  }
}
```

**Validierung (Serverseitig):**
- Widget-Instance muss existieren und User gehören
- Action muss für Widget-Type verfügbar sein
- User muss erforderliche Permission haben (z. B. `jobs:write`)
- Payload muss gültiges Format haben

**Status Codes:**
- `200 OK` – Action erfolgreich ausgeführt
- `400 Bad Request` – Ungültige Action oder Payload
- `403 Forbidden` – Fehlende Permission für Action
- `404 Not Found` – Widget-Instance existiert nicht
- `401 Unauthorized` – Fehlende Authentifizierung

---

#### 4. Real-Time Events (WebSocket)

**WebSocket /ws/events**

Subscribe zu Events (Job-Updates, Download-Progress, etc.):

```javascript
// Client-Side
const ws = new WebSocket('ws://localhost:8765/ws/events?token=<auth_token>');

ws.onopen = () => {
  // Subscribe zu spezifischen Events
  ws.send(JSON.stringify({
    type: 'subscribe',
    events: ['job.created', 'job.updated', 'job.completed']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event received:', data);
  
  // Beispiel Event:
  // {
  //   "type": "job.updated",
  //   "payload": {
  //     "jobId": "job_789",
  //     "status": "downloading",
  //     "progress": 45
  //   },
  //   "timestamp": "2025-11-11T14:45:00Z"
  // }
};
```

**Unterstützte Events:**
- `job.created` – Neuer Job erstellt
- `job.updated` – Job-Status geändert (Progress, Status)
- `job.completed` – Job abgeschlossen
- `job.failed` – Job fehlgeschlagen
- `library.updated` – Bibliothek aktualisiert (neue Tracks)
- `metadata.updated` – Metadaten aktualisiert

---

### 🔒 Security & Governance

#### Role Model

**Rollen:**
- `admin` – Volle Kontrolle, kann alle Views/Widgets verwalten
- `curator` – Kann eigene Views verwalten, Read-Access auf shared Views
- `user` – Kann eigene Views verwalten, Read-Access auf shared Views
- `readOnly` – Nur Lesezugriff, keine Änderungen

**Permissions:**
- `views:read` – Views lesen (eigene + shared)
- `views:write` – Views erstellen/ändern (nur eigene, außer admin)
- `views:delete` – Views löschen (nur eigene, außer admin)
- `views:share` – Views teilen (Phase F optional)
- `jobs:read` – Jobs lesen
- `jobs:write` – Jobs steuern (pause, cancel, retry)
- `library:read` – Bibliothek lesen
- `library:write` – Bibliothek ändern (Metadaten, Dateien)
- `settings:read` – Einstellungen lesen
- `settings:write` – Einstellungen ändern (nur admin)

#### Berechtigungsprüfung (Server-Side)

**Alle destruktiven Widget-Actions MÜSSEN serverseitig validiert werden:**

```python
# Beispiel: Pseudo-Code für Action-Validierung
def execute_widget_action(user: User, widget_instance_id: str, action_id: str, payload: dict):
    # 1. Widget-Instance laden und User-Zugehörigkeit prüfen
    widget_instance = get_widget_instance(widget_instance_id)
    if widget_instance.user_id != user.id and not user.is_admin:
        raise PermissionDenied("Widget instance does not belong to user")
    
    # 2. Action-Definition aus Registry laden
    widget_def = get_widget_definition(widget_instance.widget_id)
    action = next((a for a in widget_def.actions if a.id == action_id), None)
    if not action:
        raise InvalidAction("Action not found")
    
    # 3. Permission prüfen
    if not user.has_permission(action.permission):
        raise PermissionDenied(f"Missing permission: {action.permission}")
    
    # 4. Payload validieren
    validate_action_payload(action, payload)
    
    # 5. Action ausführen
    result = execute_action(widget_instance, action, payload)
    
    return result
```

#### Keine Telemetrie/Performance-Metriken

**Explizit NICHT erlaubt:**
- ❌ Tracking von User-Interaktionen (Clicks, Widget-Usage)
- ❌ Performance-Metriken (Load-Times, Response-Times) in DB speichern
- ❌ Analytics-Integration (Google Analytics, Mixpanel, etc.)
- ❌ Automatisches Fehler-Reporting (Sentry, etc.) mit User-Context

**Erlaubt:**
- ✅ Server-seitige Logs für Debugging (strukturiertes Logging, Correlation IDs)
- ✅ Health Checks und System-Metriken (ohne User-Context)
- ✅ Audit-Logs für Security-Vorfälle (explizit, opt-in)

#### Sharing & Team-Views (Optional Phase F)

**Default:** Views sind privat (nur User hat Zugriff)

**Optional (Phase F):**
- Read-only Share Links (zeitlich begrenzt, revocable)
- Team-Views (mehrere Users mit Read/Write-Access)
- View-Templates (Admin erstellt, User können klonen)

**Keine automatische Synchronisation** zwischen Users (kein "Real-Time Collaboration").

---

### 📊 5 Core Widgets (MVP)

#### 1. Active Jobs Widget

**Beschreibung:** Zeigt laufende Download- und Processing-Jobs in Echtzeit.

**Features:**
- Liste aller aktiven Jobs (Download, Processing, Metadata Enrichment)
- Progress Bar mit Percentage
- Status-Badges (Downloading, Processing, Completed, Failed)
- Actions: Pause, Cancel, Retry
- Auto-Refresh via WebSocket (job.updated events)

**Settings:**
- `showCompleted`: Abgeschlossene Jobs anzeigen (bool, default: false)
- `maxItems`: Max. Anzahl Jobs (int, default: 10, min: 5, max: 50)
- `refreshInterval`: Refresh-Interval in Sekunden (int, default: 5, min: 1, max: 60)

**Actions:**
- `pause` (Permission: `jobs:write`)
- `cancel` (Permission: `jobs:write`)
- `retry` (Permission: `jobs:write`)

---

#### 2. Spotify Search Widget

**Beschreibung:** Direkter Spotify-Search mit Download-Integration.

**Features:**
- Suchfeld für Tracks, Albums, Artists
- Ergebnisliste mit Preview (Cover, Name, Artist, Duration)
- Quick-Download Button (fügt zu Queue hinzu)
- Integration mit Job-Queue

**Settings:**
- `searchMode`: Suchtyp (enum: "tracks", "albums", "artists", default: "tracks")
- `autoDownload`: Automatischer Download bei Click (bool, default: false)
- `maxResults`: Max. Anzahl Ergebnisse (int, default: 10, min: 5, max: 50)

**Actions:**
- `download` (Permission: `jobs:write`)
- `addToPlaylist` (Permission: `library:write`)

---

#### 3. Missing Tracks Widget

**Beschreibung:** Zeigt fehlende Tracks aus Spotify-Playlists.

**Features:**
- Dropdown zur Playlist-Auswahl
- Liste fehlender Tracks (in Spotify, aber nicht lokal)
- Bulk-Download Button
- Export als CSV/JSON

**Settings:**
- `playlistId`: Spotify-Playlist ID (string, optional)
- `autoDetect`: Automatische Erkennung fehlender Tracks (bool, default: true)
- `showFoundTracks`: Gefundene Tracks auch anzeigen (bool, default: false)

**Actions:**
- `downloadMissing` (Permission: `jobs:write`)
- `exportCSV` (Permission: `library:read`)

---

#### 4. Quick Actions Widget

**Beschreibung:** Schnellzugriff auf häufige Aktionen.

**Features:**
- Konfigurierbares Button-Grid
- Vordefinierte Actions:
  - Scan Library
  - Import Playlist
  - Fix Metadata
  - Rescan Media Server
  - Clear Cache

**Settings:**
- `actions`: Array von Action-IDs (array of strings, default: ["scan", "import", "fix"])
- `layout`: Layout-Typ (enum: "grid", "list", default: "grid")

**Actions:**
- `execute` (Permission: abhängig von Action)

---

#### 5. Metadata Manager Widget

**Beschreibung:** Verwaltet Metadaten-Konflikte und fehlende Tags.

**Features:**
- Liste von Tracks mit Metadaten-Problemen:
  - Fehlende Artwork
  - Fehlende Tags (Artist, Album, etc.)
  - Konflikte (mehrere Quellen, unterschiedliche Daten)
- Quick-Fix Buttons
- Batch-Operations

**Settings:**
- `scope`: Filter-Scope (enum: "all", "untagged", "conflicts", default: "all")
- `autoFix`: Automatisches Fix bei eindeutigen Problemen (bool, default: false)
- `maxItems`: Max. Anzahl Items (int, default: 20, min: 5, max: 100)

**Actions:**
- `fixMetadata` (Permission: `library:write`)
- `downloadArtwork` (Permission: `library:write`)
- `resolveConflict` (Permission: `library:write`)

---

### 🧪 Acceptance Criteria (Epic v2.0)

#### Funktionale Anforderungen

- [ ] **Grid Canvas:** Nutzer kann leere View erstellen und Widgets aus Palette per Drag & Drop platzieren
- [ ] **Widget-Konfiguration:** Nutzer kann Widget-Settings via Modal ändern (validiert gegen settingsSchema)
- [ ] **Save/Load:** Views werden in DB persistiert und können geladen/gespeichert werden
- [ ] **User-Isolation:** Jeder User sieht nur eigene Views (außer Admin oder Shared Views)
- [ ] **5 Core Widgets:** Active Jobs, Spotify Search, Missing Tracks, Quick Actions, Metadata Manager funktionieren vollständig
- [ ] **Widget Actions:** Alle Actions (Pause, Cancel, Download, etc.) funktionieren und sind serverseitig validiert
- [ ] **Composite Widgets:** Parent-Widgets können Children enthalten und Selection-Sync funktioniert
- [ ] **Permissions:** Destruktive Aktionen werden serverseitig gegen User-Permissions geprüft
- [ ] **WebSocket Events:** Real-Time Updates für Jobs und Library-Changes funktionieren

#### Non-Funktionale Anforderungen

- [ ] **Performance:** View-Load < 1s, Widget-Render < 500ms
- [ ] **Accessibility:** WCAG AA konform (Keyboard-Navigation, Screen-Reader)
- [ ] **Responsive:** Mobile-First, funktioniert auf Tablet und Desktop
- [ ] **Security:** Alle API-Endpoints sind authentifiziert und autorisiert
- [ ] **No Telemetry:** Keine Performance-Metriken, keine User-Tracking-Daten in DB/Logs
- [ ] **Documentation:** Vollständige API-Docs, Widget-Schema-Examples, Quickstart-Guide

#### Definition of Done

- [ ] Alle 5 Core Widgets implementiert und getestet
- [ ] Grid Canvas mit Drag & Drop funktioniert
- [ ] Save/Load Persistence funktioniert
- [ ] Permissions & Security vollständig implementiert
- [ ] Unit-Tests für alle API-Endpoints (Coverage > 80%)
- [ ] Integration-Tests für Widget-Actions
- [ ] E2E-Tests für kritische User-Flows (Create View, Add Widget, Save)
- [ ] API-Dokumentation vollständig (OpenAPI/Swagger)
- [ ] User-Documentation (README, Quickstart, Widget-Schema-Examples)
- [ ] Code-Review abgeschlossen
- [ ] Security-Review abgeschlossen (keine High/Critical Vulnerabilities)

---

### 📋 Issue-Templates & Tasks

#### Epic: v2.0 Dynamic Views & Widget-Palette

**Epic Description:**
Implementiere Dynamic Views & Widget-Palette als neue Hauptfunktionalität für SoulSpot v2.0. Ermöglicht Nutzern, personalisierte Dashboards mit konfigurierbaren Widgets zu erstellen.

**Labels:** `epic`, `v2.0`, `feature`, `ui`, `api`

---

#### Phase A: Design & Architektur (1-2 days)

**Issue: `v2.0/design: Wireframes & Widget-Registry Schema`**

**Beschreibung:**
Erstelle Wireframes für Grid-Canvas UI und definiere Widget-Registry Schema.

**Acceptance Criteria:**
- [ ] Wireframes für Grid Canvas (Empty State, mit Widgets, Edit Mode)
- [ ] Widget-Palette Design (Kategorie-Filter, Search)
- [ ] Settings-Modal Design (verschiedene Field-Types)
- [ ] Widget-Registry Schema (JSON Schema Definition)
- [ ] Saved View Schema (JSON Structure)
- [ ] Design-Review mit Maintainer

**Definition of Done:**
- [ ] Wireframes in `docs/design/v2.0-wireframes.md` dokumentiert
- [ ] JSON-Schemas in `docs/api/v2.0-schemas.json` dokumentiert
- [ ] Design-System-Tokens erweitert (neue Farben, Spacing für Grid)

**Estimated Effort:** 1-2 days  
**Priority:** CRITICAL (Blocker für Phase B)

---

#### Phase B: Infrastructure MVP (5 days)

**Issue: `v2.0/infra: Grid Canvas + Widget-Palette (MVP infra)`**

**Beschreibung:**
Implementiere Grid-Canvas UI mit Drag & Drop und Widget-Palette Backend/Frontend.

**Scope:**
- Grid-Canvas Component (HTML/CSS/JS)
- Drag & Drop Integration (mit Collision Detection)
- Widget-Palette Component (Backend: GET /api/widgets)
- Save/Load Views (Backend: GET/POST /api/views, Frontend-Integration)

**API Contracts:**
- `GET /api/widgets` – Widget-Registry laden
- `GET /api/views` – User-Views laden
- `GET /api/views/:id` – View laden
- `POST /api/views` – View speichern/aktualisieren
- `DELETE /api/views/:id` – View löschen

**Acceptance Criteria:**
- [ ] Grid-Canvas rendert korrekt (12-column Grid)
- [ ] Widgets können per Drag & Drop platziert werden
- [ ] Widget-Palette zeigt alle verfügbaren Widgets
- [ ] View kann gespeichert und geladen werden (DB-Persistierung)
- [ ] Grid-Layout ist responsive (Tablet/Desktop)

**Definition of Done:**
- [ ] Backend-Endpoints implementiert und getestet (Unit + Integration)
- [ ] Frontend-Components implementiert
- [ ] DB-Schema für Views erstellt (Alembic Migration)
- [ ] API-Dokumentation aktualisiert (OpenAPI)
- [ ] E2E-Test: Create View, Add Widget, Save, Load

**Estimated Effort:** 5 days  
**Priority:** CRITICAL (Blocker für Phase C)  
**Dependencies:** Phase A complete

---

#### Phase C: Widgets MVP (7-10 days)

**Issue: `v2.0/widgets: Implement Active Jobs widget (MVP)`**

**Beschreibung:**
Implementiere Active Jobs Widget mit Real-Time Job-Monitoring.

**Scope:**
- Frontend Widget Component (HTML/CSS/JS)
- Settings Modal Integration
- WebSocket Integration für Real-Time Updates
- Widget Actions (Pause, Cancel, Retry)

**API Contracts:**
- WebSocket `/ws/events` – Subscribe to `job.*` events
- `POST /api/widgets/:instanceId/action` – Execute actions

**Acceptance Criteria:**
- [ ] Widget zeigt laufende Jobs in Echtzeit
- [ ] Progress Bars aktualisieren sich automatisch
- [ ] Actions (Pause, Cancel, Retry) funktionieren
- [ ] Settings-Modal kann konfigurieren (showCompleted, maxItems, refreshInterval)
- [ ] Widget ist responsive

**Definition of Done:**
- [ ] Widget Component vollständig implementiert
- [ ] WebSocket-Integration funktioniert
- [ ] Actions serverseitig validiert (Permission: `jobs:write`)
- [ ] Unit-Tests für Widget-Actions
- [ ] E2E-Test für Widget-Usage

**Estimated Effort:** 2 days  
**Priority:** HIGH  
**Dependencies:** Phase B complete

---

**Issue: `v2.0/widgets: Implement Spotify Search widget (MVP)`**

**Beschreibung:**
Implementiere Spotify Search Widget mit Download-Integration.

**Scope:**
- Frontend Widget Component
- Spotify API Integration (Search Proxy)
- Download Button Integration (Queue)

**API Contracts:**
- `GET /api/spotify/search` – Proxy zu Spotify API
- `POST /api/widgets/:instanceId/action` – Execute `download` action

**Acceptance Criteria:**
- [ ] Suchfeld funktioniert (Tracks, Albums, Artists)
- [ ] Ergebnisliste mit Preview (Cover, Name, Artist)
- [ ] Download Button fügt zu Queue hinzu
- [ ] Settings-Modal funktioniert (searchMode, autoDownload, maxResults)

**Definition of Done:**
- [ ] Widget Component implementiert
- [ ] Spotify Search Proxy implementiert (Backend)
- [ ] Download-Integration funktioniert
- [ ] Unit-Tests + E2E-Test

**Estimated Effort:** 2 days  
**Priority:** HIGH  
**Dependencies:** Phase B complete

---

**Issue: `v2.0/widgets: Missing Tracks widget (MVP)`**

**Beschreibung:**
Implementiere Missing Tracks Widget für Playlist-Sync.

**Scope:**
- Frontend Widget Component
- Backend: Missing Tracks Detection (Spotify Playlist vs. Local Library)
- Bulk-Download Integration
- CSV/JSON Export

**API Contracts:**
- `GET /api/playlists/:id/missing` – Get missing tracks
- `POST /api/widgets/:instanceId/action` – Execute `downloadMissing` action

**Acceptance Criteria:**
- [ ] Dropdown zur Playlist-Auswahl
- [ ] Liste fehlender Tracks
- [ ] Bulk-Download funktioniert
- [ ] CSV/JSON Export funktioniert

**Definition of Done:**
- [ ] Widget Component implementiert
- [ ] Backend Missing-Tracks-Detection implementiert
- [ ] Bulk-Download funktioniert
- [ ] Unit-Tests + E2E-Test

**Estimated Effort:** 2-3 days  
**Priority:** HIGH  
**Dependencies:** Phase B complete

---

**Issue: `v2.0/widgets: Quick Actions widget (MVP)`**

**Beschreibung:**
Implementiere Quick Actions Widget für Schnellzugriff.

**Scope:**
- Frontend Widget Component
- Konfigurierbares Button-Grid
- Integration mit bestehenden Use-Cases (Scan Library, Import Playlist, etc.)

**Acceptance Criteria:**
- [ ] Button-Grid rendert korrekt
- [ ] Actions sind konfigurierbar (Settings-Modal)
- [ ] Actions funktionieren (Scan, Import, Fix, etc.)

**Definition of Done:**
- [ ] Widget Component implementiert
- [ ] Actions serverseitig validiert
- [ ] Unit-Tests + E2E-Test

**Estimated Effort:** 1-2 days  
**Priority:** MEDIUM  
**Dependencies:** Phase B complete

---

**Issue: `v2.0/widgets: Metadata Manager widget (MVP)`**

**Beschreibung:**
Implementiere Metadata Manager Widget für Metadaten-Probleme.

**Scope:**
- Frontend Widget Component
- Backend: Metadaten-Problem-Detection (Missing Artwork, Tags, Conflicts)
- Quick-Fix Actions
- Batch-Operations

**API Contracts:**
- `GET /api/library/metadata-issues` – Get metadata issues
- `POST /api/widgets/:instanceId/action` – Execute fix actions

**Acceptance Criteria:**
- [ ] Liste von Metadaten-Problemen
- [ ] Filter-Scope funktioniert (all, untagged, conflicts)
- [ ] Quick-Fix Actions funktionieren
- [ ] Batch-Operations funktionieren

**Definition of Done:**
- [ ] Widget Component implementiert
- [ ] Backend Metadata-Issues-Detection implementiert
- [ ] Fix-Actions serverseitig validiert
- [ ] Unit-Tests + E2E-Test

**Estimated Effort:** 2-3 days  
**Priority:** HIGH  
**Dependencies:** Phase B complete

---

#### Phase D: Composite Widgets & Permissions (4-6 days)

**Issue: `v2.0/composite: Composite Widgets support (widget-in-widget)`**

**Beschreibung:**
Implementiere Composite-Widget-Support (Parent mit children).

**Scope:**
- Backend: Widget-Registry erweitern (supportChildren flag)
- Frontend: Composite Widget Component
- Selection-Sync zwischen Children
- Event-Propagation

**Acceptance Criteria:**
- [ ] Composite Widget kann Children enthalten
- [ ] Children können im Parent-Kontext laufen
- [ ] Selection-Sync funktioniert (Child A auswählen → Child B reagiert)
- [ ] Event-Propagation funktioniert

**Definition of Done:**
- [ ] Backend Composite-Support implementiert
- [ ] Frontend Composite Component implementiert
- [ ] Example Composite Widget (Library Overview) implementiert
- [ ] Unit-Tests + E2E-Test

**Estimated Effort:** 3-4 days  
**Priority:** MEDIUM  
**Dependencies:** Phase C complete

---

**Issue: `v2.0/security: Permissions & role checks for widget actions`**

**Beschreibung:**
Implementiere vollständige Permission-Prüfung für alle Widget-Actions.

**Scope:**
- Role Model definieren (admin, curator, user, readOnly)
- Permission-System erweitern
- Serverseitige Validierung für alle Actions
- Frontend: Permission-basiertes UI (Buttons disablen)

**Acceptance Criteria:**
- [ ] Role Model dokumentiert und implementiert
- [ ] Alle Widget-Actions prüfen Permissions
- [ ] Frontend zeigt nur erlaubte Actions
- [ ] Audit-Log für Permission-Denied-Fälle

**Definition of Done:**
- [ ] Permission-System vollständig implementiert
- [ ] Unit-Tests für Permission-Checks (alle Actions)
- [ ] Security-Review abgeschlossen
- [ ] Dokumentation aktualisiert

**Estimated Effort:** 2-3 days  
**Priority:** CRITICAL  
**Dependencies:** Phase C complete

---

#### Phase E: Polish & Docs (2-3 days)

**Issue: `v2.0/docs: Roadmap docs, widget JSON schemas & examples`**

**Beschreibung:**
Vollständige Dokumentation für v2.0 Dynamic Views & Widget-Palette.

**Scope:**
- API-Dokumentation (OpenAPI/Swagger)
- Widget-Schema-Examples (für alle 5 Core Widgets)
- Quickstart-Guide für User
- Developer-Guide für neue Widgets

**Deliverables:**
- [ ] `docs/api/v2.0-api.md` – Vollständige API-Dokumentation
- [ ] `docs/widgets/` – Widget-Schema-Examples
- [ ] `docs/quickstart-v2.0.md` – User-Quickstart
- [ ] `docs/dev/widget-development.md` – Developer-Guide

**Definition of Done:**
- [ ] Alle Dokumente erstellt und reviewed
- [ ] Examples für alle Widgets
- [ ] Quickstart getestet (User kann View erstellen)

**Estimated Effort:** 2-3 days  
**Priority:** HIGH  
**Dependencies:** Phase D complete

---

#### Phase F: Optional Extensions (3-5 days)

**Issue: `v2.0/sharing: View sharing & templates (optional)`**

**Beschreibung:**
Implementiere optionale View-Sharing-Features.

**Scope:**
- Read-only Share Links (zeitlich begrenzt, revocable)
- View-Templates (Admin erstellt, User klonen)
- Export/Import Views (JSON)

**Acceptance Criteria:**
- [ ] Share Links funktionieren (Read-only, zeitlich begrenzt)
- [ ] Templates können erstellt und geklont werden
- [ ] Export/Import funktioniert (JSON)

**Definition of Done:**
- [ ] Share-Link-System implementiert
- [ ] Template-System implementiert
- [ ] Export/Import funktioniert
- [ ] Unit-Tests + E2E-Test

**Estimated Effort:** 3-5 days  
**Priority:** LOW  
**Dependencies:** Phase E complete

---

### 🗓️ Zeitplan & Sprint-Aufteilung

**Gesamtaufwand:** ~20-26 Dev Days (ohne Phase F: ~19 days)

#### Sprint 1: Foundation (1 Woche / 5 Arbeitstage)
- **Phase A:** Design & Architektur (1-2 days)
- **Phase B:** Infrastructure MVP (5 days, parallel zu Phase A Ende)
- **Deliverables:** Grid Canvas, Widget Palette, Save/Load Views

#### Sprint 2: Core Widgets (2 Wochen / 10 Arbeitstage)
- **Phase C:** Widgets MVP (7-10 days)
  - Active Jobs Widget (2 days)
  - Spotify Search Widget (2 days)
  - Missing Tracks Widget (2-3 days)
  - Quick Actions Widget (1-2 days)
  - Metadata Manager Widget (2-3 days)
- **Deliverables:** 5 funktionsfähige Widgets

#### Sprint 3: Advanced Features (1 Woche / 5 Arbeitstage)
- **Phase D:** Composite Widgets & Permissions (4-6 days)
  - Composite Widget Support (3-4 days)
  - Permission-System (2-3 days, parallel)
- **Deliverables:** Composite Widgets, Security vollständig

#### Sprint 4: Polish & Docs (1 Woche / 5 Arbeitstage)
- **Phase E:** Polish & Docs (2-3 days)
- **Buffer:** Testing, Bug-Fixing, Performance-Optimization (2-3 days)
- **Deliverables:** Vollständige Dokumentation, Release-Ready

#### Optional Sprint 5: Extensions (1 Woche / 5 Arbeitstage)
- **Phase F:** Sharing & Templates (3-5 days)
- **Deliverables:** Share Links, Templates, Export/Import

**Total Timeline:** 4-5 Sprints (je 1 Woche) = ~4-5 Wochen

---

### 📈 Release-Integration

**Update für Release-Plan (aus Haupt-Roadmap):**

| Version | Target Date | Focus | Key Features |
|---------|-------------|-------|--------------|
| **2.0.0** | Q3-Q4 2025 | **Dynamic Views & Widget-Palette** | **Grid Canvas, 5 Core Widgets, Composite Widgets, Permissions** |
| 2.1.0 | Q4 2025 | Widget Extensions | Additional Widgets (Charts, Reports) |
| 2.5.0 | Q4 2025+ | Enterprise Features | Phase 9 (Multi-user, Plugins) + Phase F (Sharing) |

**Breaking Changes (2.0.0):**
- Neue API-Endpoints: `/api/views`, `/api/widgets`
- WebSocket-API: `/ws/events`
- Neue Permissions: `views:read`, `views:write`, `jobs:write`, etc.
- Frontend: Neue Navigation (Views-Tab)

**Migration Path:**
- Bestehende Features bleiben unverändert
- Nutzer können optional zu Dynamic Views migrieren
- Legacy-UI bleibt verfügbar (Fallback)

---

### 🎯 Success Metrics (Definition)

**User-Focused Metrics (keine Telemetrie!):**
- [ ] User kann in < 5 Minuten erste View erstellen und speichern
- [ ] User kann in < 2 Minuten Widget hinzufügen und konfigurieren
- [ ] 80%+ der Power-User nutzen mindestens 3 Widgets
- [ ] Feedback: "Dynamic Views verbessern Workflow signifikant"

**Technical Metrics:**
- [ ] View-Load < 1s (p95)
- [ ] Widget-Render < 500ms (p95)
- [ ] API-Response < 200ms (p95)
- [ ] Zero Critical Security Vulnerabilities
- [ ] Test Coverage > 80%

**Documentation Quality:**
- [ ] User kann ohne Hilfe erste View erstellen (Quickstart)
- [ ] Developer kann ohne Hilfe neues Widget erstellen (Dev-Guide)
- [ ] Alle API-Endpoints dokumentiert (OpenAPI)

---

### ❓ Offene Fragen & Entscheidungen

#### 1. Widget-Interaktion: Direkt vs. Event-basiert?

**Frage:** Sollen Widgets direkt miteinander kommunizieren oder Event-basiert?

**Optionen:**
- **Direkt:** Widget A ruft Widget B direkt auf (einfacher, aber tight coupling)
- **Event-basiert:** Widget A sendet Event, Widget B subscribed (loosely coupled, komplexer)

**Empfehlung:** Event-basiert (Widget-Instance → Parent → Children), vereinfacht Testing und Erweiterbarkeit

---

#### 2. Grid-Layout: Feste Slots vs. Frei positionierbar?

**Frage:** Fixed Grid (12-column) oder Free Positioning?

**Optionen:**
- **Fixed Grid:** Widgets snappen zu Grid (einfacher, konsistenter)
- **Free Positioning:** Pixel-genaue Platzierung (flexibler, komplexer)

**Empfehlung:** Fixed Grid (12-column, ähnlich Bootstrap) für MVP, Free Positioning optional für v2.1

---

#### 3. WebSocket vs. Polling für Real-Time Updates?

**Frage:** WebSocket oder HTTP-Polling?

**Optionen:**
- **WebSocket:** Bidirektional, Real-Time (effizienter, aber Overhead)
- **HTTP-Polling:** Unidirektional, Intervall-basiert (einfacher, aber ineffizient)

**Empfehlung:** WebSocket für MVP (bessere UX, Standard für Real-Time)

---

#### 4. Composite Widget Depth: 1 Level oder nested?

**Frage:** Nur 1 Level (Parent → Children) oder beliebig nested (Parent → Child → GrandChild)?

**Optionen:**
- **1 Level:** Einfacher, vermeidet Komplexität
- **Nested:** Flexibler, aber deutlich komplexer

**Empfehlung:** 1 Level für MVP, Nested optional für v2.1

---

### 🚀 Nächste Schritte

1. **Maintainer Review:** Review dieser Roadmap-Planung
2. **Issue Creation:** Issues in GitHub erstellen (mit Labels `v2.0`, `epic`, etc.)
3. **Sprint Planning:** Sprint 1 planen (Phase A + B)
4. **Design Phase:** Wireframes und Schemas erstellen
5. **Implementation:** Sprint 1 starten

---

**🎉 v2.0 Dynamic Views & Widget-Palette ist eine strategische Feature-Erweiterung, die SoulSpot Bridge zu einer hochgradig personalisierbaren Plattform macht. Mit klarer Planung, Phasen-Aufteilung und Security-First-Approach ist das Feature in 4-5 Sprints umsetzbar.**

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
| **v2.0: Dynamic Views & Widget-Palette** | 🔵 STRATEGIC | HIGH | VERY HIGH | MEDIUM | Q3-Q4 2025 |
| **v3.0: Production Hardening & Enterprise Deployment** | 🔴 CRITICAL | HIGH | VERY HIGH | HIGH | 2026+ |

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
| **Dynamic Views & Widget-Palette** | **v2.0 Roadmap Plan** | **📋 Q3-Q4 2025** |
| **Production Hardening & Enterprise Deployment** | **v3.0 Roadmap Plan** | **🔮 2026+** |
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
| **2.0.0** | Q3-Q4 2025 | Major Release | **Dynamic Views & Widget-Palette (Grid Canvas, 5 Core Widgets, Composite Widgets, Permissions)** |
| **2.1.0** | Q4 2025 | Widget Extensions | Additional Widgets (Charts, Reports) |
| **2.5.0** | Q4 2025+ | Enterprise Features | Phase 9 (Multi-user, Plugins) + Sharing/Templates |
| **3.0.0** | 2026+ | Production Hardening | **Production Profile (PostgreSQL, Redis, nginx), Kubernetes, Security Hardening (OWASP, Input Validation, Secrets Management, Rate Limiting, Brute Force Protection, Session Timeout), Redis Integration, Backup & Recovery, Rollback Procedures** |

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

### 2025-11-11: v2.0 Dynamic Views & Widget-Palette Planning

**Durchgeführt von:** Copilot Agent

**Änderungen:**

- ✅ **v2.0 Section hinzugefügt** – Vollständige Planung für Dynamic Views & Widget-Palette
- ✅ **Vision & Ziele** definiert – User-centric Design, Modularität, Security-First
- ✅ **MVP-Scope & Abgrenzungen** klar formuliert – Was ist drin, was nicht
- ✅ **Meilensteine & Phasen** strukturiert (A-F) mit Aufwand und Dependencies
- ✅ **Architektur & Technische Konzepte** dokumentiert:
  - Widget-Registry Schema mit Settings-Schema und Actions
  - Saved View Persistierung (JSON-Model)
  - Composite Widgets (Parent mit children, selection-sync)
- ✅ **API-Contracts & Endpoints** vollständig spezifiziert:
  - GET /api/widgets – Widget-Registry
  - GET/POST/DELETE /api/views – Views Management
  - POST /api/widgets/:instanceId/action – Widget Actions
  - WebSocket /ws/events – Real-Time Events
- ✅ **5 Core Widgets** detailliert beschrieben (Active Jobs, Spotify Search, Missing Tracks, Quick Actions, Metadata Manager)
- ✅ **Security & Governance** vollständig definiert:
  - Role Model (admin, curator, user, readOnly)
  - Permission-System (views:*, jobs:*, library:*, settings:*)
  - Serverseitige Validierung für alle Actions
  - Explizit: Keine Telemetrie/Performance-Metriken
- ✅ **Acceptance Criteria & Definition of Done** formuliert
- ✅ **Issue-Templates & Tasks** erstellt für alle Phasen (A-F)
- ✅ **Zeitplan & Sprint-Aufteilung** definiert (~20-26 Dev Days, 4-5 Sprints)
- ✅ **Release-Integration** in Release-Plan aktualisiert (v2.0.0 Q3-Q4 2025)
- ✅ **Success Metrics** definiert (User-Focused, Technical, Documentation)
- ✅ **Offene Fragen** dokumentiert (Widget-Interaktion, Grid-Layout, WebSocket, Composite Depth)

**Impact:**

- v2.0 Dynamic Views & Widget-Palette vollständig geplant und spezifiziert
- Klare Roadmap für Implementation (keine Implementierung jetzt – nur Planung)
- Issue-Templates ready für GitHub
- API-Contracts definiert und dokumentiert
- Security-Anforderungen klar formuliert
- Sprint-Planung und Zeitschätzung verfügbar
- Ready für Maintainer-Review und Implementation-Start

**Struktur:**

- Neuer Top-Level-Section zwischen Phase 9 und Continuous Improvements
- Inhaltsverzeichnis aktualisiert
- Prioritäts-Matrix erweitert (🔵 STRATEGIC)
- Feature-Kategorien aktualisiert
- Release-Schedule angepasst (v2.0.0 Focus auf Dynamic Views)

**Zeilen:** ~1204 (vorher) → ~2364 (nachher) – +~1160 Zeilen für v2.0 Planning

---

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
