# SoulSpot – Vollständige, Detaillierte Ideensammlung (Konsolidiert aus allen Quellen und Chats)

## 1. Grundkonzept

**Beschreibung:**  
SoulSpot ist ein moderner Musikmanager, der Spotify, Soulseek (über slskd), lokale Bibliotheken und optionale Media-Server (Plex, Jellyfin, Navidrome) zu einem automatisierten System verbindet.

**Ziel:**  
Fehlende Songs aus Spotify-Playlists oder Artists automatisch über Soulseek finden, herunterladen, taggen, sortieren und mit vollständigen Metadaten in die lokale Bibliothek integrieren.

**Nutzen:**  
- Vollautomatische Ergänzung der Musikbibliothek  
- Konsistente Tags, Cover und Lyrics  
- Kein manuelles Suchen, Sortieren oder Taggen mehr  

---

## 2. Quellen & Integrationen

### Spotify
- Zugriff auf Playlists, Artists, Alben, Liked Songs, Saved Albums  
- Spotify als Metadatenquelle für Titel, Artist, Jahr, ISRC, Cover  
- OAuth2-Authentifizierung (z. B. mit Spotipy)  
- Nutzung der API für Suche, Track-Daten, Playlist-Inhalte  

**Nutzen:**  
Spotify liefert die präzisesten und vollständigsten Metadaten zur Zuordnung und Tagging-Referenz.

---

### Soulseek (slskd)
- REST-API-Nutzung: `/search`, `/download`, `/status`  
- Authentifizierung mit Benutzername/Passwort/API-Key  
- Download- und Queue-Management vollständig automatisiert  
- Kontrolle über parallele Downloads, Pause/Resume, Statusüberwachung  
- Logging jedes Transfers (Quelle, Größe, Zeit, User)  

**Nutzen:**  
Ermöglicht serverbasierten, skriptfähigen Zugriff auf Soulseek ohne GUI. Perfekt für Automation und Integration.

---

### Externe Metadatenquellen
- **MusicBrainz:** IDs, Labels, Releases, Disknummern, Positionen  
- **Discogs:** Veröffentlichungsjahr, Edition, Land, Label  
- **Last.fm:** Genre-Tags, Hörerzahlen, Stimmung, ähnliche Artists  
- **LRClib / Genius / Musixmatch:** Lyrics und LRC-Dateien  
- **Fanart.tv / Spotify / Discogs:** Cover-Art in verschiedenen Auflösungen

**Nutzen:**  
Kombinierte Metadaten aus mehreren Quellen erzeugen die vollständigsten, fehlerfreien Tags.

---

### Media-Server-Integrationen
- **Plex / Jellyfin / Navidrome:**  
  - Sync von Bibliotheken, Ratings, Play-Counts  
  - Trigger für automatischen Rescan nach Downloads  
- Pfad-Mapping zwischen SoulSpot und Server (z. B. NAS)

**Nutzen:**  
Einheitliche Verwaltung lokaler und Streaming-Musiksysteme.

---

## 3. Suche & Matching

**Beschreibung:**  
Zentrale Komponente, die Spotify-Titel mit Soulseek-Ergebnissen abgleicht.

**Mechanik:**
- Kombination von Spotify-Metadaten (Titel, Artist, Länge) mit Soulseek-Suchergebnissen
- Algorithmisches Matching (Scoring-System):  
  `Score = (Title_Similarity * 0.4) + (Artist_Match * 0.3) + (Duration_Match * 0.2) + (Bitrate_Score * 0.1)`
- Audiofingerprint-Option für präzisere Zuordnung
- UI zeigt „Best Match" + alternative Treffer

**Nutzen:**  
Reduziert Fehlzuordnungen, spart Zeit, verbessert Trefferqualität.

---

## 4. Missing Song Discovery

**Beschreibung:**  
Vergleicht Spotify-Playlists, Artists oder Alben mit der lokalen Library und erkennt fehlende Songs.

**Funktion:**
- Hash-Index aller lokalen Dateien
- Abgleich mit Spotify-Library
- Ausgabe: Liste der fehlenden Titel mit Download-Option
- Auto-Download-Job für alle fehlenden Songs einer Playlist

**Nutzen:**  
Automatische Vervollständigung von Playlists, Artists oder Diskografien.

---

## 5. Download-Queue & Batch-System

**Beschreibung:**  
Steuerung aller laufenden und geplanten Downloads.

**Komponenten:**
- Queue-Datenbank (SQLite) mit Job-Status (queued, running, done, failed)
- Batch-Jobs (TXT, CSV, JSON, M3U, Spotify-Exports)
- Fortschrittsanzeige (pro Job und global)
- Parallel-Downloads mit Limit
- Retry-Logik bei Fehlversuchen
- Scheduler (Zeitfenstersteuerung, z. B. Nachtmodus)

**Nutzen:**  
Kontrollierter, stabiler, automatisierter Downloadprozess ohne Eingriff.

---

## 6. Soulseek-Automatisierung (Soularr-Prinzip)

**Beschreibung:**  
Automatische Überwachung, Suche und Vervollständigung der Library (ähnlich Sonarr/Radarr).

**Ablauf:**
1. Library-Scan → Fehlende Songs erkennen  
2. Soulseek-Suche → passende Quellen finden  
3. Automatische Downloads → mit Qualitätsfiltern  
4. Post-Processing → Tagging, Cover, Sortierung  
5. Auto-Recheck → bis alles vollständig ist

**Parameter:**
- Mindestbitrate, bevorzugte Formate (FLAC, MP3 320)
- Blacklist bestimmter Nutzer oder Keywords (Remix, Live, Radio Edit)
- Retry-Intervalle für fehlgeschlagene Files

**Nutzen:**  
„Self-Healing"-Musiksystem, das automatisch vollständig bleibt.

---

## 7. Post-Processing Pipeline

**Beschreibung:**  
Verarbeitungsschritte nach Download.

**Ablauf:**
1. Auto-Tagging via Spotify + MusicBrainz + Discogs + Last.fm  
2. Cover-Art Download aus mehreren Quellen  
3. Lyrics-Laden (LRC und Text)  
4. File-Renaming nach Schema:  
   `Artist/Year - Album/01 - Title.flac`  
5. Sortieren in Zielordner (Artist / Album / Format)  
6. Audioanalyse (Lautstärke, BPM, Dynamik, Key, Mood)  
7. Auto-Sync mit Plex / Jellyfin / Navidrome  
8. Auto-Cleanup von temporären oder defekten Files

**Nutzen:**  
Saubere, einheitliche, perfekt getaggte Library.

---

## 8. Metadata Engine & Cache

**Beschreibung:**  
Zentrale Instanz für Tag-Verwaltung, Metadaten-Zusammenführung und Caching.

**Funktion:**
- Datenquellen priorisiert mergen (Authority System)
- Lokaler SQLite-Cache für API-Responses
- Feldweise Gewichtung (Genre → Last.fm, Label → Discogs)
- Änderungslog: Vorher/Nachher-Vergleich
- Periodischer Metadata-Refresh-Job

**Nutzen:**  
Wiederverwendbare, schnelle Metadatenverarbeitung mit lückenloser Nachvollziehbarkeit.

---

## 9. Ratings & Playcount Sync

**Beschreibung:**  
Bewertungen und Wiedergabezähler zwischen Server und Dateien synchronisieren.

**Mechanik:**
- Plex → ID3v2 POPM-Feld (1–5★ → 20–100 Punkte)
- Zwei-Wege-Option (Server ↔ File)
- Konfliktregeln (Server gewinnt / Datei gewinnt)
- Änderungslog und Dry-Run-Modus

**Nutzen:**  
Zentrale Bewertungssysteme funktionieren überall gleich (Plex, Player, Datei).

---

## 10. Library-Management & Self-Healing

**Beschreibung:**  
Überwachung, Organisation und Qualitätssicherung der gesamten Musikbibliothek.

**Funktion:**
- Hash-Index für Duplikaterkennung (MD5/SHA1 + AcoustID)
- Erkennung defekter Dateien
- Vollständigkeitsprüfung pro Album/Artist
- Smart-Unify (beste Version behalten, Rest löschen)
- Multi-Library-Support (NAS, extern, lokal)
- History-Log für alle Änderungen

**Nutzen:**  
Dauerhaft gepflegte, saubere, duplikatfreie Bibliothek.

---

## 11. File-Renaming & Strukturierung

**Beschreibung:**  
Automatisches Sortieren und Umbenennen aller Dateien nach Regeln.

**Mechanik:**
- Schema: `Artist/Year - Album/TrackNumber - Title.ext`
- Erkennung von Compilations (Various Artists)
- Konfliktbehandlung (gleichnamige Dateien)
- Move & Rename kombiniert

**Nutzen:**  
Ordnung, Einheitlichkeit und Kompatibilität mit allen Playern.

---

## 12. User Interface (UI / UX)

**Beschreibung:**  
Web-App als Steuerzentrale für alle Funktionen.

**Aufbau:**
- Tabs: Search, Playlists, Artists, Downloads, Library, Settings
- Dark-Mode im Spotify-Stil
- Fortschrittsbalken + Echtzeit-Status
- Automation-Center (Jobs, Logs, Schedules)
- Metadata Manager (fehlende/fehlerhafte Tags)
- Rating-Sync-Bereich
- Activity Feed / Timeline aller Aktionen

**Erweiterungen:**
- Browser-Extension „Add to SoulSpot"
- System-Tray-App mit Schnellzugriff
- Mobile-optimierte Ansicht

**Nutzen:**  
Transparente Kontrolle, klare Übersicht, einfache Bedienung.

---

## 13. Automation & Job Scheduler

**Beschreibung:**  
Automatische Prozesse für alle wiederkehrenden Aufgaben.

**Funktion:**
- Geplante Jobs (CRON oder Zeitplan)
- Job-Typen: Scan, Download, Tagging, Metadata, Sync
- Webhooks an externe Systeme nach Abschluss
- Telegram-/Discord-Notifications mit Statusmeldung
- Prioritätssteuerung bei parallelen Prozessen

**Nutzen:**  
Nahezu wartungsfreie, autonome Software.

---

## 14. Playlist-Management & Cross-Sync

**Beschreibung:**  
Synchronisation von Playlists zwischen Spotify, Plex, Navidrome, Jellyfin.

**Funktion:**
- Vollständige oder teilweise Synchronisation
- Snapshot-/Backup-Funktion mit Wiederherstellung
- Playlist-Diff (Unterschiede zwischen Versionen)
- Automatische Rebuilder-Funktion aus lokaler Library
- Import-/Export (CSV, JSON, Markdown)
- Regelbasierte Syncs (z. B. nur bestimmte Genres oder Bewertungen)

**Nutzen:**  
Playlists bleiben über alle Dienste hinweg synchron und rekonstruierbar.

---

## 15. Sicherheit & Compliance

**Beschreibung:**  
Schutz der Benutzer und Einhaltung gesetzlicher Rahmenbedingungen.

**Funktion:**
- Legal-Opt-in für Download-Aktivierung
- Audit-Logs jeder Aktion (wer, wann, was)
- Sandbox-Ordner mit optionalem Virenscan
- Multi-User-Rollen (Admin, Read-only)
- IP-Restriktion (nur lokale/DE-Nutzung)
- Getrennte Config-Dateien:  
  - `paths.yml`  
  - `secrets.yml`  
  - `rules.yml`

**Nutzen:**  
Rechtssicherer, transparenter, datenschutzfreundlicher Betrieb.

---

## 16. REST-API & Erweiterbarkeit

**Beschreibung:**  
Offene Schnittstelle für externe Tools und Automationen.

**Funktion:**
- Endpunkte:  
  - `/api/search`  
  - `/api/download`  
  - `/api/library`  
  - `/api/metadata`
- Authentifizierung via API-Key oder OAuth2
- WebSocket-Live-Updates (Status, Logs, Events)
- CLI-Interface für Headless-Serverbetrieb
- Webhook-Auslösung bei bestimmten Ereignissen

**Nutzen:**  
Nahtlose Integration in Automationssysteme (z.B. Home Assistant, Bots, Tools).

---

## 17. Plugin-System

**Beschreibung:**  
Modulare Erweiterbarkeit ohne Kernänderung.

**Mechanik:**
- Plugins als Python-Module mit klar definiertem Interface
- Registrierung beim Start über Plugin-Manager
- Prioritätssystem bei Überschneidung (z.B. Tagging-Plugins)
- Beispielplugins: neue Quellen, Tag-Engines, Filtersysteme

**Nutzen:**  
Skalierbares, langfristig erweiterbares Framework.

---

## 18. KI-Integration & Intelligenz

**Beschreibung:**  
Einsatz künstlicher Intelligenz zur Verbesserung von Matching, Tagging und Automatisierung.

**Funktion:**
- KI-basiertes Audio-Matching (semantische Analyse von Wellenform & Frequenzen)
- KI-Genre-, Mood-, Sprach- und Instrument-Erkennung
- Adaptive Automation: System lernt aus Nutzerentscheidungen (z.B. welche Treffer bevorzugt werden)
- Forecast-Funktion: neue Releases bekannter Artists automatisch vorhersagen
- KI-gestützte Schreibweisenkorrektur und Tag-Normalisierung

**Nutzen:**  
Höhere Automatisierungsqualität und selbstlernendes Verhalten.

---

## 19. Komfortfunktionen

**Ideen:**
- Auto-Mix: kombiniert lokale und fehlende Songs zu dynamischen Playlists
- Mood-Playlists: automatisch generierte Stimmungskategorien (Chill, Happy, Focus, Dark)
- Track-Notes & Kommentare: Benutzeranmerkungen zu Songs
- Download-Budget: maximale Anzahl oder Datenmenge pro Zeitraum
- Multi-Device-Sync: PC ↔ NAS ↔ Laptop
- Audio-Analyzer: Lautstärke-, Frequenz-, Dynamikanalyse
- Auto-Backup (NAS/Cloud)
- Timeline aller Library-Aktivitäten

**Nutzen:**  
Komfortable Extras, die über Standardfunktionen hinausgehen.

---

## Gesamtziel

Ein vollständig automatisiertes, selbstheilendes Musikverwaltungssystem, das:
- Spotify & Soulseek intelligent verbindet,
- Musik automatisch findet, herunterlädt und sauber taggt,
- sich selbst organisiert,
- sich mit Media-Servern und Geräten synchronisiert,
- und langfristig lernfähig, KI-gestützt und modular bleibt.

---

# Development Roadmap

> **Last Updated:** 2025-11-10  
> **Current Status:** Phase 6 In Progress - Production Readiness  
> **Ideas Source:** Integrated from `docs/features/soulspot-ideas.md` (2025-11-10)

## 📍 Current Status

**Completed Phases:**
- ✅ Phase 1: Foundation (Domain Layer, Project Setup)
- ✅ Phase 2: Core Infrastructure (Settings, Database, FastAPI)
- ✅ Phase 3: External Integrations (slskd, Spotify, MusicBrainz)
- ✅ Phase 4: Application Layer (Use Cases, Workers, Caching)
- ✅ Phase 5: Web UI & API Integration

**Current Version:** 0.1.0 (Alpha)

**Recent Additions:**
- ✅ Docker Setup with Compose configuration
- ✅ Auto Music Import Service
- ✅ Production-ready Docker entrypoint with directory validation
- ✅ Comprehensive Docker documentation

---

## 🎯 Upcoming Development Phases

### Phase 6: Production Readiness (Priority: HIGH)
**Estimated Duration:** 2-3 weeks  
**Target Completion:** Q1 2025

#### Objectives
Transform the application from a development prototype to a production-ready system with proper observability, deployment automation, and operational tooling.

#### Tasks

**6.1 Observability & Monitoring** 🔍
- [x] Implement structured logging
  - [x] JSON log formatting for production
  - [x] Log levels per environment
  - [x] Request/response logging middleware
  - [x] Error tracking with stack traces
- [ ] Add application metrics
  - [ ] Prometheus metrics endpoint
  - [ ] Key performance indicators (API response times, queue lengths)
  - [ ] Business metrics (downloads, imports, API calls)
- [ ] Implement distributed tracing
  - [ ] OpenTelemetry integration
  - [x] Request correlation IDs
  - [ ] External API call tracing
- [x] Health check improvements
  - [x] Liveness and readiness probes
  - [x] Dependency health checks (database, external APIs)
  - [ ] Circuit breaker patterns for external services

**6.2 CI/CD Pipeline** 🚀
- [x] GitHub Actions workflow setup *(Complexity: MEDIUM, Source: roadmap)*
  - Automated testing on pull requests
  - Code quality checks (ruff, mypy, bandit)
  - Test coverage reporting
  - Security scanning
- [x] Automated release process *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - Semantic versioning (SemVer)
  - Automated changelog generation
  - Docker image building and publishing
  - GitHub releases with artifacts
  - Git tag creation (vX.Y.Z)
- [ ] Deployment automation *(Complexity: HIGH, Source: roadmap)*
  - Development environment deployment
  - Staging environment deployment
  - Production deployment with approval gates

**6.3 Docker & Deployment Configuration** 🐳
- [x] Production Dockerfile
  - [x] Multi-stage build for smaller images
  - [x] Security hardening
  - [x] Non-root user
  - [x] Health check support
- [x] Docker Compose configuration
  - [x] SoulSpot Bridge service
  - [x] slskd integration
  - [x] Bind mounts for downloads, music, and config
  - [x] Environment variable configuration
  - [x] Network configuration
- [x] Docker entrypoint script
  - [x] Directory validation (downloads, music must exist)
  - [x] Auto-create config directory
  - [x] PUID/PGID support for file permissions
  - [x] UMASK configuration
  - [x] Timezone support
- [x] Docker documentation
  - [x] Complete setup guide
  - [x] Environment variable reference
  - [x] Troubleshooting guide
  - [x] Production deployment checklist
- [ ] Docker Compose production profile (advanced)
  - [ ] PostgreSQL with persistence
  - [ ] Redis for caching and queue
  - [ ] nginx reverse proxy
  - [ ] SSL/TLS configuration
- [ ] Kubernetes manifests (optional)
  - [ ] Deployment configurations
  - [ ] Services and ingress
  - [ ] ConfigMaps and secrets
  - [ ] Horizontal Pod Autoscaling

**6.4 Security Hardening** 🔒
- [ ] Security audit and remediation
  - Dependency vulnerability scanning
  - OWASP Top 10 compliance check
  - API security best practices
  - Input validation hardening
- [ ] Secrets management
  - Environment-based secret injection
  - Integration with secret managers (AWS Secrets Manager, HashiCorp Vault)
  - Secret rotation procedures
- [ ] Authentication enhancements
  - Rate limiting for auth endpoints
  - Brute force protection
  - Session timeout configuration
  - Multi-factor authentication (future consideration)

**6.5 Performance Optimization** ⚡
- [ ] Database query optimization
  - Add missing indexes
  - Query profiling and optimization
  - Connection pool tuning
- [ ] Caching strategy enhancement
  - Redis integration for distributed caching
  - Cache warming strategies
  - Cache invalidation patterns
- [ ] API performance improvements
  - Response compression
  - Pagination for large result sets
  - Database query batching
  - Async processing for heavy operations

**6.6 Documentation for Operations** 📚
- [x] Deployment guide
  - [x] Docker setup guide with complete instructions
  - [x] System requirements
  - [x] Installation procedures
  - [x] Configuration options (environment variables)
  - [x] Directory structure requirements
  - [ ] Upgrade procedures
- [x] Troubleshooting guide
  - [x] Common Docker issues
  - [x] Permission problems
  - [x] Directory validation errors
  - [x] Auto-import troubleshooting
- [ ] Operations runbook *(Complexity: MEDIUM, Source: roadmap)*
  - [ ] Common operational tasks
  - [ ] Backup and recovery procedures
  - [ ] Monitoring and alerting setup
  - [ ] Rollback procedures *(Source: soulspot-ideas)*
- [ ] API documentation improvements *(Complexity: LOW, Source: roadmap + soulspot-ideas)*
  - [ ] Request/response examples
  - [ ] Error code documentation
  - [ ] Rate limit documentation
  - [ ] Authentication flow diagrams
  - [ ] REST API + WebSocket documentation *(Source: soulspot-ideas)*

**Acceptance Criteria:**
- [x] Docker Compose setup complete with all required services
- [x] Auto music import service implemented
- [x] Docker documentation complete
- [ ] All tests pass in CI/CD pipeline
- [ ] Docker images build successfully and are under 500MB
- [ ] API response time p95 < 200ms for non-download operations
- [ ] 100% of secrets loaded from environment or secret manager
- [ ] Comprehensive monitoring dashboard available
- [ ] Zero high-severity security vulnerabilities

---

### Phase 7: Feature Enhancements (Priority: MEDIUM)
**Estimated Duration:** 3-4 weeks  
**Target Completion:** Q2 2025

#### Objectives
Expand functionality with user-requested features and quality-of-life improvements.

**7.1 Download Management Enhancements** ⬇️
- [ ] Advanced download queue management *(Complexity: MEDIUM, Source: soulspot-ideas)*
  - Priority-based queuing (drag & drop, priority field)
  - Download scheduling (CRON, night mode)
  - Bandwidth throttling
  - Concurrent download limits (configurable, e.g., 1-3 parallel)
  - Pause/Resume functionality
- [ ] Download retry logic improvements *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - Configurable retry strategies (3 retries with exponential backoff)
  - Alternative source discovery
  - Automatic quality fallback
  - Resume after restart
- [ ] Batch download operations *(Complexity: MEDIUM, Source: soulspot-ideas)*
  - Bulk track downloads
  - Entire playlist download
  - Album-based downloads
  - Import from TXT/CSV/JSON/M3U formats
  - Spotify export integration
- [ ] Download history & audit log *(Complexity: LOW, Source: soulspot-ideas)*
  - Persistent download history
  - Audit log for all download operations
  - Legal opt-in tracking

**7.2 Metadata Management** 📊
- [ ] Manual metadata editing *(Complexity: LOW, Source: roadmap)*
  - Edit track information
  - Edit artist information
  - Edit album information
- [ ] Metadata conflict resolution *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - UI for resolving conflicting metadata
  - Preference settings for metadata sources
  - Metadata versioning
  - Authority hierarchy (manual > MusicBrainz > Discogs > Spotify > fallback) *(Source: soulspot-ideas)*
  - Tag merging and normalization (feat./ft. standardization) *(Source: soulspot-ideas)*
- [ ] Additional metadata sources *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - Discogs integration
  - Last.fm integration
  - Custom metadata providers
  - Lyrics integration (LRClib, Musixmatch, Genius) *(Source: soulspot-ideas)*
  - External artwork sources (CoverArtArchive, Fanart.tv) *(Source: soulspot-ideas)*
- [ ] Advanced tagging features *(Complexity: MEDIUM, Source: soulspot-ideas)*
  - Multi-source tagging with merge logic
  - Batch tag fixer UI (Dry-Run + Commit)
  - Metadata cache with SQLite
  - Multiple artwork resolutions (embed + cover.jpg)

**7.3 File Organization & Quality** 🗂️
- [x] Auto music import (completed in Phase 6)
  - [x] Automatic file moving after download
  - [x] Monitor downloads directory
  - [x] Move completed files to music library
  - [x] Preserve directory structure
  - [x] Support for multiple audio formats
  - [x] File completion detection
  - [x] Empty directory cleanup
- [ ] File organization templates *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - [ ] Customizable folder structures (Downloads, Sorting, New Artists, Unknown Album, Final Library) *(Source: soulspot-ideas)*
  - [ ] Filename templates with variables
  - [ ] Advanced organization rules
- [ ] Audio quality management *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - [ ] Quality filtering in search (min-bitrate, format filters FLAC/MP3) *(Source: soulspot-ideas)*
  - [ ] Format conversion (optional, Archival ↔ Mobile) *(Source: soulspot-ideas)*
  - [ ] Quality reporting and statistics
  - [ ] Exclusion keywords (Live/Remix) *(Source: soulspot-ideas)*
- [ ] Duplicate detection *(Complexity: HIGH, Source: roadmap + soulspot-ideas)*
  - [ ] Identify duplicate files (hash + fingerprint) *(Source: soulspot-ideas)*
  - [ ] Smart merging of metadata ("Smart-Unify") *(Source: soulspot-ideas)*
  - [ ] Cleanup tools
- [ ] Library scanning & self-healing *(Complexity: HIGH, Source: soulspot-ideas)*
  - [ ] Library scanner (hash/tag/structure scan, detect broken files)
  - [ ] Album completeness check
  - [ ] Auto-re-download for corrupted files
  - [ ] Fix library (tags, cover, structure)

**7.4 User Management (Multi-User Support)** 👥
- [ ] User accounts and profiles
  - User registration and login
  - Profile management
  - User-specific playlists and downloads
- [ ] Permissions and roles
  - Admin vs regular user roles
  - Shared playlists
  - Download quotas per user
- [ ] User preferences
  - Per-user configuration
  - Download preferences
  - UI customization

**7.5 Playlist Management Enhancements** 🎵
- [ ] Manual playlist creation and editing *(Complexity: LOW, Source: roadmap)*
  - Create playlists from scratch
  - Add/remove tracks manually
  - Reorder tracks
- [ ] Playlist synchronization *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - Auto-sync with Spotify changes
  - Sync frequency configuration
  - Sync conflict resolution
  - Cross-provider sync (Spotify ↔ Plex ↔ Navidrome ↔ Jellyfin) *(Source: soulspot-ideas)*
  - Playlist versioning/snapshots/rollback *(Source: soulspot-ideas)*
- [ ] Playlist export/import *(Complexity: LOW, Source: roadmap + soulspot-ideas)*
  - Export to M3U, PLS formats
  - Import from various formats
  - Cross-platform playlist sharing
  - CSV/JSON export *(Source: soulspot-ideas)*
  - Playlist rebuilder with matching *(Source: soulspot-ideas)*
- [ ] Missing song discovery *(Complexity: MEDIUM, Source: soulspot-ideas)*
  - Compare playlist entries vs. local library
  - Report missing tracks
  - Export missing songs (CSV/JSON)

**7.6 Search & Discovery** 🔍
- [ ] Advanced search capabilities *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - Search across all entities (tracks, artists, albums)
  - Filters and facets
  - Search suggestions and autocomplete
  - Combined search (Spotify + Soulseek) with source labels *(Source: soulspot-ideas)*
  - Smart matching score system (title/artist/duration/bitrate/size) *(Source: soulspot-ideas)*
- [ ] Discovery features *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - Similar tracks/artists
  - Genre-based browsing
  - Trending downloads
  - Discography discovery *(Source: soulspot-ideas)*
  - Similar-artist discovery *(Source: soulspot-ideas)*
  - "Download entire discography" feature *(Source: soulspot-ideas)*
- [ ] History and recommendations *(Complexity: LOW, Source: roadmap)*
  - Recent searches
  - Frequently downloaded
  - Personalized recommendations

**7.7 Automation & Watchlists ("arr"-Style)** 🤖  
*(Complexity: HIGH, Source: soulspot-ideas)*
- [ ] Automated workflow implementation
  - Detect → Search → Match → Download → Tag → Sort → Sync pipeline
  - Dry-run options for testing
  - Whitelist/Blacklist configuration
- [ ] Watchlist functionality
  - Artist watchlists (auto-download new releases)
  - Label watchlists
  - Genre-based watchlists
  - Auto-download when content becomes available
- [ ] Library monitoring
  - Detect missing albums in artist discographies
  - Auto-completion of partial albums
  - Quality upgrade detection

**7.8 Ratings & User Signals** ⭐  
*(Complexity: MEDIUM, Source: soulspot-ideas)*
- [ ] Ratings synchronization
  - Plex/Jellyfin/Navidrome ratings sync
  - Bidirectional sync with conflict resolution
  - Rating mapping between systems
- [ ] User signals tracking
  - Play count tracking
  - Skip tracking
  - Like/dislike signals
  - Use signals for auto-playlist generation
  - Priority-based download suggestions

**7.9 Post-Processing Pipeline** 🔄  
*(Complexity: HIGH, Source: soulspot-ideas)*
- [ ] Automated post-processing steps
  - Temp download → Auto-tagging → Artwork → Lyrics
  - Audio analysis (BPM, Loudness)
  - Rename according to templates
  - Move to final library location
  - Trigger media server rescan
  - Comprehensive logging
- [ ] Optional processing features
  - Auto-convert for different formats (Archive ↔ Mobile)
  - Auto-cleanup of temporary files
  - Audiofingerprint generation (AcoustID/Chromaprint) *(Needs discussion)*

---

### Phase 8: Advanced Features (Priority: LOW)
**Estimated Duration:** 4-6 weeks  
**Target Completion:** Q2-Q3 2025

**8.1 Mobile Application** 📱
- [ ] React Native or Flutter app
- [ ] Push notifications for download completion
- [ ] Mobile-optimized UI
- [ ] Offline mode support

**8.2 Advanced Integrations** 🔌
- [ ] Additional music sources *(Complexity: MEDIUM-HIGH, Source: roadmap + soulspot-ideas)*
  - SoundCloud integration
  - Bandcamp integration
  - YouTube Music integration
- [ ] Media server integrations *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - Plex integration (rescan, mapping, ratings sync)
  - Jellyfin integration (rescan, mapping, ratings sync)
  - Subsonic integration
  - Navidrome integration (rescan, mapping) *(Source: soulspot-ideas)*
- [ ] Notification services *(Complexity: LOW, Source: roadmap + soulspot-ideas)*
  - Discord webhooks
  - Telegram bot
  - Email notifications
  - Smart home integration *(Source: soulspot-ideas)*
- [ ] Last.fm features *(Complexity: MEDIUM, Source: soulspot-ideas)*
  - Scrobbling support
  - Last.fm metadata enrichment
  - User statistics integration

**8.3 Analytics & Insights** 📈
- [ ] Download statistics dashboard
- [ ] Library growth tracking
- [ ] Genre and artist analytics
- [ ] Export reports

**8.4 Automation & Workflows** 🤖
- [ ] Automated playlist imports *(Complexity: LOW, Source: roadmap)*
- [ ] Scheduled synchronization *(Complexity: LOW, Source: roadmap)*
- [ ] Webhook triggers *(Complexity: MEDIUM, Source: roadmap + soulspot-ideas)*
  - Event-based webhooks
  - Custom automation events
  - Integration with external systems
- [ ] Custom automation scripts *(Complexity: MEDIUM, Source: roadmap)*
- [ ] CLI for headless operation *(Complexity: MEDIUM, Source: soulspot-ideas)*
  - Full CLI interface for automation
  - Scriptable operations
  - Batch processing support

**8.5 AI & Machine Learning** 🧠  
*(Complexity: VERY HIGH, Source: soulspot-ideas, Needs discussion)*
- [ ] AI-based matching *(Deferred to future phase)*
  - Audio fingerprint matching (AcoustID/Chromaprint)
  - Machine learning-based track matching
  - Similarity detection using audio features
- [ ] AI-powered tagging
  - Automatic genre classification
  - Mood detection
  - Language detection
  - Tag repair and enrichment
- [ ] Adaptive automation
  - Learn from user decisions
  - Predictive quality preferences
  - Personalized matching strategies
- [ ] Future AI features *(Low priority)*
  - Forecast for new releases
  - Audio repair capabilities
  - Anomaly detection

**8.6 Extended UI Features** 🎨  
*(Complexity: MEDIUM, Source: soulspot-ideas)*
- [ ] Browser extension
  - "Add to SoulSpot" button for supported sites
  - Quick playlist import
  - Track search from any page
- [ ] System tray integration
  - Minimal interface
  - Quick access to common functions
  - Download progress in tray
- [ ] Terminal/Minimal view
  - Text-based UI option
  - Headless operation support
- [ ] Enhanced visualizations
  - Timeline view for operations
  - Automation center dashboard
  - Metadata manager interface
  - Rating sync interface

---

### Phase 9: Enterprise & Extended Features (Priority: LOW)
**Estimated Duration:** 4-6 weeks  
**Target Completion:** Q3-Q4 2025

#### Objectives
Long-term features for advanced users, enterprise deployments, and experimental functionality.

**9.1 Multi-User & Security** 👥  
*(Complexity: HIGH, Source: soulspot-ideas)*
- [ ] Advanced authentication
  - Multi-user support with role-based access
  - Admin vs. Read-only roles
  - OAuth/API Key authentication
  - IP restriction (optional)
  - Comprehensive audit logs
- [ ] User-specific features
  - Per-user download quotas
  - User-specific playlists and libraries
  - Individual preferences and settings
- [ ] Legal compliance features
  - Legal mode with restricted features
  - Opt-in legal notice before automated downloads
  - Compliance tracking and reporting

**9.2 Plugin System & Extensibility** 🔌  
*(Complexity: VERY HIGH, Source: soulspot-ideas)*
- [ ] Plugin architecture
  - Plugin SDK/API
  - Dynamic plugin loading
  - Plugin marketplace/registry
- [ ] Extensibility points
  - Custom music sources
  - Custom tagging engines
  - Custom automation rules
  - Custom post-processing steps
- [ ] Plugin management
  - Install/uninstall plugins
  - Plugin versioning
  - Plugin configuration UI

**9.3 Multi-Library & Advanced Storage** 💾  
*(Complexity: HIGH, Source: soulspot-ideas)*
- [ ] Multi-library support
  - Multiple music library locations (NAS, local, cloud)
  - Per-library configuration
  - Library synchronization
- [ ] Preferred version management
  - Mark preferred versions of tracks
  - Quality-based version preference
  - Automatic version upgrade
- [ ] Advanced storage features
  - Deduplication across libraries
  - Storage quota management
  - Archive vs. active library separation

**9.4 Advanced Configuration** ⚙️  
*(Complexity: MEDIUM, Source: soulspot-ideas)*
- [ ] Configuration management
  - YAML/JSON configuration files
  - Configuration versioning
  - Import/export configuration
  - Configuration validation
- [ ] Policy framework
  - Download policies (quality, format, size limits)
  - Automation policies (when to auto-download)
  - Retention policies (auto-cleanup rules)
  - Rate limiting policies (external API calls)
- [ ] Multi-device sync
  - Sync configuration across devices
  - Sync queue across devices
  - Shared libraries

**9.5 Experimental Features** 🧪  
*(Complexity: VARIES, Source: soulspot-ideas, Needs evaluation)*
- [ ] Audio analysis features
  - BPM detection
  - Key detection
  - Loudness normalization
  - Audio quality assessment
- [ ] Smart playlists
  - Auto-generated based on mood/genre
  - Dynamic playlists based on listening habits
  - Similarity-based auto-playlists
- [ ] Download budgeting
  - Bandwidth budgets
  - Storage budgets
  - Time-based download windows
- [ ] Advanced UI concepts
  - PWA (Progressive Web App) support
  - Offline-first architecture
  - Real-time collaboration features

---

## 🔄 Continuous Improvements

### Technical Debt
- [ ] Refactor large use case classes
- [ ] Improve test coverage to 90%+
- [ ] Add integration tests for all API endpoints
- [ ] Documentation updates as code evolves
- [ ] Performance profiling and optimization
- [ ] MusicBrainz rate-limit handling (1 req/sec) *(Source: soulspot-ideas)*
- [ ] Implement circuit breaker patterns for external services

### Code Quality
- [ ] Regular dependency updates
- [ ] Security vulnerability patching
- [ ] Code review process improvements
- [ ] Architecture decision records (ADRs)
- [ ] Safe atomic file operations (temp write + replace) *(Source: soulspot-ideas)*

### User Experience
- [ ] Accessibility improvements (WCAG AAA)
- [ ] Internationalization (i18n)
- [ ] Dark mode refinements
- [ ] Responsive design improvements
- [ ] Progressive enhancement for all UI features

### Metrics & Monitoring *(Source: soulspot-ideas)*
- [ ] Track key performance indicators
  - Job throughput and completion rate
  - Average enrichment time per track
  - Cache hit rate
  - External API calls per second
  - Failed job ratio
- [ ] Business metrics
  - Download success rate
  - User engagement metrics
  - Library growth statistics
  - Search-to-download conversion rate

---

## 📊 Priority Matrix

| Phase | Priority | Effort | Impact | Risk | Complexity |
|-------|----------|--------|--------|------|------------|
| Phase 6: Production Readiness | HIGH | HIGH | HIGH | MEDIUM | MEDIUM-HIGH |
| Phase 7: Feature Enhancements | MEDIUM | MEDIUM | HIGH | LOW | MEDIUM |
| Phase 8: Advanced Features | LOW | HIGH | MEDIUM | MEDIUM | HIGH |
| Phase 9: Enterprise & Extended | VERY LOW | VERY HIGH | LOW | HIGH | VERY HIGH |

**Complexity Legend:**
- **LOW (klein):** 1-3 days of development
- **MEDIUM (mittel):** 1-2 weeks of development
- **HIGH (groß):** 2-4 weeks of development
- **VERY HIGH:** Multiple months, significant complexity

---

## 📋 Default Policies & Configuration Recommendations

*(Source: soulspot-ideas.md - Section 4)*

### Rate Limiting & External API Policies
- **MusicBrainz:** 1 request/second (strict rate limiting, use worker queue)
- **Spotify API:** Respect rate limits, implement exponential backoff
- **slskd API:** Configurable concurrent requests (default: 2-3)

### Metadata Merge Priority
**Recommended hierarchy:**
1. Manual user edits (highest priority)
2. MusicBrainz (authoritative for classical metadata)
3. Discogs (good for release details)
4. Spotify (good for popularity and modern metadata)
5. Last.fm (fallback)
6. File tags (lowest priority)

**Open Question:** Should Spotify be prioritized higher for certain fields like popularity or user-facing names?

### Download Policies
- **Default parallel downloads:** 2 (configurable 1-5)
- **Retry policy:** 3 retries with exponential backoff (1s, 2s, 4s)
- **Default quality filter:** Minimum 128kbps (configurable)
- **Format preference:** FLAC > 320kbps MP3 > 256kbps > 192kbps

### Legal & Compliance
- **Legal opt-in:** Required before automated downloads
- **Audit logging:** All downloads logged with timestamp, source, user
- **Legal mode:** Optional restricted mode for compliance-focused deployments

### Storage & Organization
**Recommended folder structure:**
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

## ❓ Open Questions & Decision Points

*(Source: soulspot-ideas.md - Section 4)*

### Technical Decisions Needed

1. **Ratings Sync Strategy**
   - Should initial sync be one-way (Plex→SoulSpot) or bidirectional?
   - How to handle rating conflicts between systems?
   - Which rating scale to use as canonical (5-star vs 10-point)?
   - **Recommendation:** Start with one-way, evolve to bidirectional after testing

2. **Audio Fingerprinting Timeline**
   - Should AcoustID/Chromaprint be Phase 7 or Phase 8/9?
   - Significant complexity and performance impact
   - **Recommendation:** Phase 8 (Advanced Features) with opt-in flag

3. **Metadata Priority for Specific Fields**
   - Should Spotify be prioritized for popularity, modern artist names, or user-facing data?
   - How to handle conflicts between MusicBrainz canonical names vs. Spotify user-friendly names?
   - **Recommendation:** Configurable per-field priority, with sensible defaults

4. **Legal Mode Restrictions**
   - Which features should be restricted/disabled in legal mode?
   - How strict should automation be?
   - **Recommendation:** Define clear boundaries, document extensively, make opt-in explicit

5. **Plugin System Scope**
   - Full plugin system in Phase 8 or Phase 9?
   - Security implications of arbitrary plugins
   - **Recommendation:** Phase 9, with careful security review

6. **Multi-User Implementation**
   - Simple role-based access or full multi-tenancy?
   - Shared vs. private libraries?
   - **Recommendation:** Start with simple RBAC (admin/user), evolve based on demand

### Community Input Needed

These features should be discussed with users/contributors before implementation:
- [ ] Preferred default quality settings
- [ ] Folder structure preferences
- [ ] Rating sync behavior expectations
- [ ] Automation aggressiveness (how automatic should "auto" be?)
- [ ] Privacy expectations for metadata caching
- [ ] Acceptable external service dependencies

---

## 🎯 Quick Reference: Feature Sources

### From Existing Roadmap (Original)
- Core production readiness features
- Basic user management concepts
- Standard integrations (Plex, Jellyfin, Subsonic)

### From soulspot-ideas.md (Integrated 2025-11-10)
- Enhanced download queue management (priorities, scheduling, pause/resume)
- Comprehensive metadata management (multi-source, merge logic, lyrics)
- Post-processing pipeline (tagging, artwork, audio analysis)
- Automation & watchlists (arr-style features)
- Ratings synchronization
- Advanced search and matching (smart scoring, filters)
- Library scanning and self-healing
- Plugin system architecture
- Multi-library support
- AI/ML features (deferred to later phases)
- Extended UI features (browser extension, tray, terminal)
- Configuration policies and best practices

### Deferred or Needs Discussion
- Full AI-based matching and tagging (Phase 9 or later)
- Audio repair capabilities (experimental)
- Forecast for new releases (research needed)
- Adaptive automation learning (requires user data strategy)
- Smart home integration (needs use case validation)



### Phase 6 Success Criteria
- [ ] Zero critical security vulnerabilities
- [ ] 99.9% uptime in production
- [ ] API p95 response time < 200ms
- [ ] Automated deployment pipeline operational
- [ ] Monitoring and alerting configured

### Phase 7 Success Criteria
- [ ] User satisfaction score > 4.5/5
- [ ] Feature adoption rate > 60%
- [ ] Support ticket reduction by 30%
- [ ] API usage growth by 100%

### Phase 8 Success Criteria
- [ ] Mobile app with 1000+ active users
- [ ] 3+ successful third-party integrations
- [ ] Community contributions > 10 PRs
- [ ] Documentation viewed by 5000+ users

---

## 🤝 Contributing to the Roadmap

We welcome community input on the roadmap! If you have suggestions for features or improvements:

1. Check existing [GitHub Issues](https://github.com/bozzfozz/soulspot-bridge/issues) for similar ideas
2. Create a new issue using the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md)
3. Participate in roadmap discussions
4. Submit pull requests for features you'd like to implement

### Suggested "Good First Issue" Tasks

*(Source: soulspot-ideas.md - Section 5)*

These tasks are well-suited for new contributors:

**Phase 6-7 Quick Wins:**
1. **spotify-oauth-enhancements** *(Complexity: LOW)*
   - Improve OAuth PKCE flow documentation
   - Add manual testing guide
   - Enhance error messages

2. **queue-basic-improvements** *(Complexity: LOW)*
   - Add pagination to job list endpoint
   - Improve job status filtering
   - Add job statistics endpoint

3. **safe-tag-writes-enhancement** *(Complexity: LOW)*
   - Implement atomic temp-write + replace for all tag operations
   - Add comprehensive error handling
   - Add rollback on failure

4. **cover-download-multi-source** *(Complexity: LOW-MEDIUM)*
   - Extend cover download to support multiple sources
   - Add CoverArtArchive integration
   - Support multiple resolutions

5. **batch-download-csv-import** *(Complexity: MEDIUM)*
   - Implement CSV/JSON batch import UI
   - Add validation and preview
   - Support M3U playlist import

6. **download-scheduler** *(Complexity: MEDIUM)*
   - Implement CRON-based download scheduling
   - Add "night mode" for off-peak downloads
   - UI for schedule configuration

### Suggested "Help Wanted" Tasks

These tasks are suitable for contributors with more experience:

**Phase 7 Features:**
1. **musicbrainz-enrichment-advanced** *(Complexity: MEDIUM)*
   - Advanced MusicBrainz integration with caching
   - Rate-limit handling with worker queue
   - Comprehensive unit tests

2. **retry-resume-enhanced** *(Complexity: MEDIUM)*
   - Implement sophisticated retry logic
   - Resume after application restart
   - Alternative source discovery on failure

3. **ratings-sync-connector** *(Complexity: MEDIUM)*
   - Plex API connector for ratings sync
   - Dry-run mode for testing
   - Conflict resolution UI

4. **missing-song-discovery** *(Complexity: MEDIUM)*
   - Library scanner comparing playlists vs. local files
   - Missing track reporting
   - CSV/JSON export of missing tracks

5. **smart-matching-heuristics** *(Complexity: MEDIUM-HIGH)*
   - Fuzzy matching for track search
   - Score-based matching algorithm
   - Configurable matching thresholds

6. **metadata-merge-logic** *(Complexity: HIGH)*
   - Multi-source metadata merging
   - Authority hierarchy implementation
   - Tag normalization (feat./ft. etc.)
   - Batch tag fixer UI with dry-run



---

## 📅 Release Schedule

| Version | Target Date | Focus | Key Features |
|---------|-------------|-------|--------------|
| 0.1.0 | 2025-11-08 | ✅ Alpha Release | Web UI, Basic Features |
| 0.2.0 | Q1 2025 | Beta Release | Production Ready, Docker, Observability |
| 1.0.0 | Q2 2025 | Stable Release | Complete Phase 6-7 Features |
| 1.1.0 | Q2 2025 | Feature Enhancements | Automation, Ratings, Advanced Search |
| 1.5.0 | Q3 2025 | Advanced Features | Phase 8 Complete |
| 2.0.0 | Q3-Q4 2025 | Major Features | Mobile, AI Features (if viable) |
| 2.5.0 | Q4 2025+ | Enterprise Features | Phase 9 (Multi-user, Plugins) |

### Version Strategy

Following [Semantic Versioning (SemVer)](https://semver.org/):
- **MAJOR (X.0.0):** Breaking changes, major feature sets
- **MINOR (0.X.0):** New features, backward compatible
- **PATCH (0.0.X):** Bug fixes, security patches

### Release Checklist

Before each release:
- [ ] All tests pass (unit, integration, e2e)
- [ ] Security scan clean (no high/critical vulnerabilities)
- [ ] Documentation updated (CHANGELOG, README, API docs)
- [ ] Git tag created (vX.Y.Z)
- [ ] Docker images built and published
- [ ] Release notes written
- [ ] Rollback plan documented *(Source: soulspot-ideas)*
- [ ] Breaking changes clearly communicated

---

**Note:** This roadmap is subject to change based on user feedback, technical constraints, and project priorities. Dates are estimates and may be adjusted as development progresses.

---

## 📝 Roadmap Change Log

### 2025-11-10: Major Integration from soulspot-ideas.md
**Integrated by:** Copilot Agent  
**Changes:**
- Added detailed feature specifications from comprehensive ideas document
- Expanded Phase 7 (Feature Enhancements) with 4 new subsections:
  - 7.7 Automation & Watchlists ("arr"-Style)
  - 7.8 Ratings & User Signals
  - 7.9 Post-Processing Pipeline
- Enhanced Phase 8 (Advanced Features) with additional integrations and UI features
- Added new Phase 9 (Enterprise & Extended Features) for long-term goals:
  - Multi-user & security
  - Plugin system & extensibility
  - Multi-library support
  - Advanced configuration
  - Experimental features
- Added comprehensive sections:
  - Default Policies & Configuration Recommendations
  - Open Questions & Decision Points
  - Feature Sources Quick Reference
  - Enhanced Contributing section with "Good First Issue" and "Help Wanted" suggestions
- Added complexity indicators throughout (LOW/MEDIUM/HIGH/VERY HIGH)
- Added source attribution for all features (roadmap/soulspot-ideas/both)
- Updated Priority Matrix to include Phase 9
- Expanded Release Schedule with version strategy and checklist
- Added Metrics & Monitoring to Continuous Improvements
- Total new features added: ~100+ detailed tasks
- Features marked for discussion: ~10 (AI features, plugin security, legal mode details)
- Avoided duplicates by carefully mapping existing features

**Impact:**
- Roadmap now comprehensively covers short-term (Q1 2025) to long-term (Q4 2025+) goals
- Clear prioritization and complexity indicators for all features
- Better guidance for contributors with categorized tasks
- Explicit documentation of open questions and policy decisions needed
- Maintained consistency with existing roadmap structure and formatting
