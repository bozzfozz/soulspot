# 🎵 SoulSpot – Vollständige Entwicklungs-Roadmap

> **Version:** 1.0  
> **Erstellt:** 2025-11-26  
> **Autor:** SoulSpot Development Team  
> **Letzte Aktualisierung:** 2025-11-26  
> **Dokumenttyp:** Master-Roadmap (Von Null bis Produktion)

---

## 📋 Inhaltsverzeichnis

1. [Executive Summary](#1-executive-summary)
2. [Projektübersicht](#2-projektübersicht)
3. [Architektur-Vision](#3-architektur-vision)
4. [Technologie-Stack](#4-technologie-stack)
5. [Phase 0: Projektinitialisierung](#5-phase-0-projektinitialisierung-woche-1)
6. [Phase 1: Foundation](#6-phase-1-foundation-woche-2-3)
7. [Phase 2: Core Infrastructure](#7-phase-2-core-infrastructure-woche-4-6)
8. [Phase 3: External Integrations](#8-phase-3-external-integrations-woche-7-9)
9. [Phase 4: Application Layer](#9-phase-4-application-layer-woche-10-12)
10. [Phase 5: Web UI & API Integration](#10-phase-5-web-ui--api-integration-woche-13-16)
11. [Phase 6: Automation & Watchlists](#11-phase-6-automation--watchlists-woche-17-20)
12. [Phase 7: Performance & Scalability](#12-phase-7-performance--scalability-woche-21-23)
13. [Phase 8: Security Hardening](#13-phase-8-security-hardening-woche-24-26)
14. [Phase 9: Advanced Features](#14-phase-9-advanced-features-woche-27-32)
15. [Phase 10: Production Readiness](#15-phase-10-production-readiness-woche-33-36)
16. [Langfristige Vision (v2.0/v3.0)](#16-langfristige-vision-v20v30)
17. [Risiken und Mitigationsstrategien](#17-risiken-und-mitigationsstrategien)
18. [Erfolgskriterien und KPIs](#18-erfolgskriterien-und-kpis)
19. [Anhang](#19-anhang)

---

## 1. Executive Summary

### Was ist SoulSpot?

SoulSpot ist eine intelligente Musik-Download-Anwendung, die:
- **Spotify-Playlists** über OAuth importiert und synchronisiert
- **Soulseek (slskd)** als Download-Quelle nutzt
- **Metadaten** aus MusicBrainz, Last.fm und Spotify anreichert
- **Dateien organisiert** mit automatischem Tagging, Cover-Art und Umbenennung
- Eine **moderne Web-Oberfläche** für lokalen Single-User-Betrieb bietet

### Projektziele

| Ziel | Beschreibung | Priorität |
|------|--------------|-----------|
| **Automatisierung** | Vollautomatische Playlist-Synchronisation und Downloads | P0 |
| **Qualität** | Hochwertige Metadaten und Audio-Qualität | P0 |
| **Benutzerfreundlichkeit** | Intuitive Web-UI ohne technische Kenntnisse | P1 |
| **Erweiterbarkeit** | Modulare Architektur für zukünftige Features | P1 |
| **Zuverlässigkeit** | Robuste Fehlerbehandlung und Retry-Logik | P0 |

### Gesamtübersicht der Phasen

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SOULSPOT ENTWICKLUNGS-ROADMAP                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 0    Phase 1    Phase 2    Phase 3    Phase 4    Phase 5            │
│  ────────   ────────   ────────   ────────   ────────   ────────           │
│  Projekt-   Domain     Infra-     Externe    Application Web UI            │
│  Setup     Foundation  struktur   APIs       Layer      & API             │
│  [1 Wo]    [2 Wo]     [3 Wo]     [3 Wo]     [3 Wo]     [4 Wo]            │
│     │         │          │          │          │          │                │
│     ▼         ▼          ▼          ▼          ▼          ▼                │
│  ╔═══════════════════════════════════════════════════════════╗            │
│  ║              v0.1.0 ALPHA (Woche 16)                     ║            │
│  ╚═══════════════════════════════════════════════════════════╝            │
│                                                                             │
│  Phase 6    Phase 7    Phase 8    Phase 9    Phase 10                      │
│  ────────   ────────   ────────   ────────   ────────                      │
│  Automation Performance Security   Advanced   Production                   │
│  Watchlists Optimize   Hardening  Features   Readiness                    │
│  [4 Wo]    [3 Wo]     [3 Wo]     [6 Wo]     [4 Wo]                       │
│     │         │          │          │          │                           │
│     ▼         ▼          ▼          ▼          ▼                           │
│  ╔═══════════════════════════════════════════════════════════╗            │
│  ║              v1.0.0 STABLE (Woche 36)                    ║            │
│  ╚═══════════════════════════════════════════════════════════╝            │
│                                                                             │
│  Langfristig: v2.0 (Plugin-System) → v3.0 (Modulare Architektur)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Geschätzter Gesamtaufwand

| Metrik | Wert |
|--------|------|
| **Gesamtdauer** | ~36 Wochen (9 Monate) |
| **Entwickler** | 1-2 Full-Stack Entwickler |
| **Lines of Code (geschätzt)** | ~25.000 Python + ~5.000 HTML/JS/CSS |
| **Tests** | ~500+ Unit & Integration Tests |
| **API Endpoints** | 60+ REST Endpoints |

---

## 2. Projektübersicht

### 2.1 Projektvision

> *"SoulSpot – Die Brücke zwischen Streaming und persönlicher Musikbibliothek"*

SoulSpot löst das Problem, dass viele Nutzer ihre Spotify-Playlists lokal verfügbar haben möchten – für Offline-Nutzung, bessere Audio-Qualität oder Unabhängigkeit von Streaming-Diensten.

### 2.2 Kernfunktionen

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SOULSPOT FEATURE-ÜBERSICHT                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐ │
│  │  SPOTIFY SYNC     │     │   SOULSEEK DL     │     │   METADATA        │ │
│  │  ─────────────    │     │   ──────────      │     │   ────────        │ │
│  │  • OAuth Login    │────▶│  • Smart Search   │────▶│  • MusicBrainz    │ │
│  │  • Playlist Import│     │  • Quality Filter │     │  • Last.fm Tags   │ │
│  │  • Auto-Sync      │     │  • Retry Logic    │     │  • Cover Art      │ │
│  │  • Track Matching │     │  • Priority Queue │     │  • Lyrics         │ │
│  └───────────────────┘     └───────────────────┘     └───────────────────┘ │
│           │                         │                         │             │
│           ▼                         ▼                         ▼             │
│  ┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐ │
│  │  FILE MANAGEMENT  │     │   AUTOMATION      │     │   WEB UI          │ │
│  │  ───────────────  │     │   ──────────      │     │   ──────          │ │
│  │  • ID3 Tagging    │     │  • Artist Watch   │     │  • Dashboard      │ │
│  │  • File Renaming  │     │  • Quality Upgrade│     │  • Download Queue │ │
│  │  • Auto-Move      │     │  • Missing Tracks │     │  • Settings       │ │
│  │  • Library Scan   │     │  • Schedulers     │     │  • Real-time SSE  │ │
│  └───────────────────┘     └───────────────────┘     └───────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Nutzer-Personas

#### Primäre Persona: "Der Musik-Enthusiast"
- **Alter:** 25-45
- **Technisch:** Mittleres Level (kann Docker starten)
- **Bedürfnis:** Hochwertige lokale Musiksammlung
- **Frustration:** Streaming-Qualität, Offline-Verfügbarkeit

#### Sekundäre Persona: "Der Daten-Hoarder"
- **Alter:** 20-35
- **Technisch:** Fortgeschritten (Home-Server Betreiber)
- **Bedürfnis:** Vollständige Automatisierung
- **Frustration:** Manuelle Downloads, fehlende Metadaten

### 2.4 User Stories (Highlights)

| ID | Als... | möchte ich... | damit ich... |
|----|--------|---------------|--------------|
| US-001 | Nutzer | mich mit Spotify anmelden | meine Playlists importieren kann |
| US-002 | Nutzer | Playlists automatisch synchronisieren | immer aktuelle Songs habe |
| US-003 | Nutzer | Download-Fortschritt sehen | weiß was passiert |
| US-004 | Nutzer | Metadaten automatisch ergänzen | saubere Bibliothek habe |
| US-005 | Nutzer | Künstler beobachten | neue Releases nicht verpasse |
| US-006 | Nutzer | Duplikate erkennen | Speicherplatz spare |
| US-007 | Nutzer | fehlende Tracks finden | vollständige Alben habe |

---

## 3. Architektur-Vision

### 3.1 Architektur-Prinzipien

Die Architektur folgt bewährten Prinzipien für saubere, wartbare Software:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ARCHITEKTUR-PRINZIPIEN                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. LAYERED ARCHITECTURE (Schichten-Architektur)                           │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │                    PRESENTATION LAYER                            │    │
│     │         REST API (FastAPI) • Web UI (Jinja2 + HTMX)             │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │                    APPLICATION LAYER                             │    │
│     │         Use Cases • Commands • Queries • DTOs                    │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │                      DOMAIN LAYER                                │    │
│     │         Entities • Value Objects • Domain Services • Ports       │    │
│     ├─────────────────────────────────────────────────────────────────┤    │
│     │                   INFRASTRUCTURE LAYER                           │    │
│     │         Repositories • External APIs • Cache • Workers           │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  2. DEPENDENCY INVERSION                                                    │
│     • High-Level Module hängen von Abstraktionen ab                        │
│     • Infrastructure implementiert Domain-Ports                            │
│     • Konkrete Implementierungen via Dependency Injection                  │
│                                                                             │
│  3. DOMAIN-DRIVEN DESIGN (taktisch)                                        │
│     • Entities mit Identität und Invarianten                               │
│     • Value Objects ohne Identität                                         │
│     • Domain Services für komplexe Operationen                             │
│                                                                             │
│  4. SOLID-PRINZIPIEN                                                        │
│     • Single Responsibility: Eine Klasse = Eine Verantwortung              │
│     • Open/Closed: Erweiterung ohne Modifikation                           │
│     • Liskov Substitution: Austauschbare Implementierungen                 │
│     • Interface Segregation: Kleine, spezifische Interfaces                │
│     • Dependency Inversion: Abhängigkeiten auf Abstraktionen               │
│                                                                             │
│  5. ASYNC FIRST                                                             │
│     • Durchgängiges async/await Pattern                                    │
│     • Non-blocking I/O für externe APIs                                    │
│     • Effiziente Ressourcennutzung                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 System-Architektur

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM-ARCHITEKTUR                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌──────────────┐           ┌──────────────────────────────────────┐     │
│    │   Browser    │◀────────▶│         SoulSpot Application         │     │
│    │   (Web UI)   │           │                                      │     │
│    └──────────────┘           │  ┌────────────────────────────────┐  │     │
│                               │  │       FastAPI Server           │  │     │
│                               │  │  ┌──────────┐ ┌──────────────┐ │  │     │
│                               │  │  │ REST API │ │ Web Routes   │ │  │     │
│                               │  │  └────┬─────┘ └──────┬───────┘ │  │     │
│                               │  └───────┼──────────────┼─────────┘  │     │
│                               │          ▼              ▼            │     │
│                               │  ┌─────────────────────────────────┐ │     │
│                               │  │     Application Services        │ │     │
│                               │  │  ┌─────────┐ ┌────────────────┐ │ │     │
│                               │  │  │Use Cases│ │  Job Queue     │ │ │     │
│                               │  │  └────┬────┘ └───────┬────────┘ │ │     │
│    ┌──────────────┐           │  └───────┼──────────────┼──────────┘ │     │
│    │   Spotify    │◀──OAuth──▶│          ▼              ▼            │     │
│    │     API      │           │  ┌─────────────────────────────────┐ │     │
│    └──────────────┘           │  │      Domain Layer               │ │     │
│                               │  │  Entities • Services • Ports    │ │     │
│    ┌──────────────┐           │  └──────────────┬──────────────────┘ │     │
│    │  MusicBrainz │◀──HTTP───▶│                 ▼                    │     │
│    │     API      │           │  ┌─────────────────────────────────┐ │     │
│    └──────────────┘           │  │   Infrastructure Layer          │ │     │
│                               │  │  ┌──────────┐ ┌──────────────┐  │ │     │
│    ┌──────────────┐           │  │  │SQLite DB │ │ Repositories │  │ │     │
│    │   Last.fm    │◀──HTTP───▶│  │  └──────────┘ └──────────────┘  │ │     │
│    │     API      │           │  │  ┌──────────┐ ┌──────────────┐  │ │     │
│    └──────────────┘           │  │  │ Caches   │ │ Workers      │  │ │     │
│                               │  │  └──────────┘ └──────────────┘  │ │     │
│    ┌──────────────┐           │  └─────────────────────────────────┘ │     │
│    │    slskd     │◀──HTTP───▶│                                      │     │
│    │  (Soulseek)  │           └──────────────────────────────────────┘     │
│    └──────────────┘                                                         │
│          │                                                                  │
│          ▼                                                                  │
│    ┌──────────────┐                                                         │
│    │  File System │  ← Downloads & Music Library                           │
│    │  mnt/        │                                                         │
│    │  ├─downloads │                                                         │
│    │  └─music     │                                                         │
│    └──────────────┘                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Ordnerstruktur

```
soulspot/
├── pyproject.toml              # Poetry-Konfiguration & Dependencies
├── alembic.ini                 # Alembic (DB Migrations) Konfiguration
├── Makefile                    # Build-Befehle
├── docker/                     # Docker-Konfiguration
│   ├── docker-compose.yml      # Production Setup
│   └── Dockerfile              # Application Image
├── alembic/                    # Database Migrations
│   └── versions/               # Migration Scripts
├── src/soulspot/               # Haupt-Package
│   ├── __init__.py
│   ├── main.py                 # FastAPI Entry Point
│   │
│   ├── api/                    # Presentation Layer - REST API
│   │   └── routers/            # API Router Module
│   │       ├── auth.py         # OAuth Authentifizierung
│   │       ├── playlists.py    # Playlist-Operationen
│   │       ├── downloads.py    # Download-Management
│   │       ├── tracks.py       # Track-Verwaltung
│   │       ├── library.py      # Bibliotheks-Verwaltung
│   │       ├── metadata.py     # Metadaten-Anreicherung
│   │       ├── automation.py   # Automatisierungs-Features
│   │       ├── settings.py     # Einstellungen
│   │       └── ui.py           # Web UI Routes
│   │
│   ├── application/            # Application Layer
│   │   ├── use_cases/          # Business Use Cases
│   │   │   ├── import_spotify_playlist.py
│   │   │   ├── search_and_download_track.py
│   │   │   ├── enrich_metadata.py
│   │   │   └── ...
│   │   ├── services/           # Application Services
│   │   │   ├── token_manager.py
│   │   │   ├── session_store.py
│   │   │   ├── postprocessing/
│   │   │   └── ...
│   │   └── workers/            # Background Workers
│   │       ├── job_queue.py
│   │       ├── download_worker.py
│   │       ├── metadata_worker.py
│   │       └── automation_workers.py
│   │
│   ├── domain/                 # Domain Layer
│   │   ├── entities/           # Domain Entities
│   │   │   ├── artist.py
│   │   │   ├── album.py
│   │   │   ├── track.py
│   │   │   ├── playlist.py
│   │   │   ├── download.py
│   │   │   └── ...
│   │   ├── value_objects/      # Value Objects
│   │   │   ├── spotify_uri.py
│   │   │   ├── file_path.py
│   │   │   └── ...
│   │   ├── ports/              # Repository Interfaces
│   │   │   ├── artist_repository.py
│   │   │   ├── track_repository.py
│   │   │   └── ...
│   │   └── exceptions/         # Domain Exceptions
│   │       └── domain_errors.py
│   │
│   ├── infrastructure/         # Infrastructure Layer
│   │   ├── persistence/        # Database Layer
│   │   │   ├── models.py       # SQLAlchemy Models
│   │   │   ├── database.py     # DB Connection
│   │   │   └── repositories.py # Repository Implementations
│   │   └── integrations/       # External API Clients
│   │       ├── spotify_client.py
│   │       ├── slskd_client.py
│   │       ├── musicbrainz_client.py
│   │       └── lastfm_client.py
│   │
│   ├── config/                 # Configuration
│   │   └── settings.py         # Pydantic Settings
│   │
│   ├── templates/              # Jinja2 Templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   └── partials/
│   │
│   └── static/                 # Static Assets
│       ├── css/
│       └── js/
│
├── tests/                      # Test Suite
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
└── docs/                       # Documentation
    ├── api/
    ├── guides/
    └── project/
```

---

## 4. Technologie-Stack

### 4.1 Backend-Technologien

| Kategorie | Technologie | Version | Begründung |
|-----------|-------------|---------|------------|
| **Sprache** | Python | 3.12+ | Moderne Features, Async Support, große Ecosystem |
| **Web-Framework** | FastAPI | 0.115+ | Async, Type-Safe, Automatische Docs |
| **ASGI Server** | Uvicorn | 0.31+ | High-Performance, Async |
| **ORM** | SQLAlchemy | 2.0+ | Async Support, Moderne API |
| **Migrations** | Alembic | 1.14+ | Flexible Schema-Migrationen |
| **Datenbank** | SQLite | - | Embedded, Zero-Config, Ausreichend für Single-User |
| **Validation** | Pydantic | 2.9+ | Type-Safety, Settings, Serialization |
| **HTTP Client** | httpx | 0.28+ | Async, HTTP/2, Moderne API |
| **Audio-Metadata** | mutagen | 1.47+ | ID3 Tags, Alle Formate |
| **Image Processing** | Pillow | 11.0+ | Cover Art Optimization |
| **Fuzzy Search** | rapidfuzz | 3.14+ | Typo-Tolerante Suche |

### 4.2 Frontend-Technologien

| Kategorie | Technologie | Version | Begründung |
|-----------|-------------|---------|------------|
| **Template Engine** | Jinja2 | 3.1+ | Server-Side Rendering |
| **Interaktivität** | HTMX | 1.9+ | Minimales JS, Progressive Enhancement |
| **Styling** | Tailwind CSS | 3.x | Utility-First, Responsive |
| **Icons** | Heroicons/Lucide | - | Konsistente Icon-Bibliothek |

### 4.3 DevOps & Tooling

| Kategorie | Technologie | Version | Begründung |
|-----------|-------------|---------|------------|
| **Package Manager** | Poetry | - | Dependency Management, Reproducible Builds |
| **Linting** | Ruff | 0.7+ | Schnell, Black-Kompatibel |
| **Type Checking** | mypy | 1.13+ | Strict Mode, Pydantic Plugin |
| **Security Scan** | Bandit | 1.8+ | Security Linting |
| **Testing** | pytest | 8.3+ | Async Tests, Fixtures |
| **Coverage** | pytest-cov | 7.0+ | Coverage Reporting |
| **Containerization** | Docker | 20.10+ | Deployment, Development |
| **CI/CD** | GitHub Actions | - | Automated Testing, Releases |

### 4.4 Externe APIs

| Service | Zweck | Rate Limits |
|---------|-------|-------------|
| **Spotify Web API** | Playlists, OAuth, Metadaten | 100 req/min (Standard) |
| **slskd API** | Soulseek Downloads | Lokal, keine Limits |
| **MusicBrainz API** | Kanonische Metadaten | 1 req/sec |
| **Last.fm API** | Genres, Tags | 5 req/sec |
| **CoverArtArchive** | Album Artwork | 1 req/sec |

---

## 5. Phase 0: Projektinitialisierung (Woche 1)

### 5.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 1 Woche |
| **Ziel** | Projekt-Setup, Repository, Tooling |
| **Ergebnis** | Lauffähiges Projekt-Skeleton |
| **Version** | - (Interne Setup-Phase) |

### 5.2 Aufgaben

#### 5.2.1 Repository Setup

```bash
# Repository initialisieren
mkdir soulspot && cd soulspot
git init

# Poetry-Projekt erstellen
poetry init --name soulspot --python "^3.12"

# Haupt-Verzeichnisse anlegen
mkdir -p src/soulspot/{api,application,domain,infrastructure,config,templates,static}
mkdir -p tests/{unit,integration}
mkdir -p docs/{api,guides,project}
mkdir -p docker
mkdir -p alembic
```

#### 5.2.2 pyproject.toml Konfiguration

```toml
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "soulspot"
version = "0.0.1"
description = "Intelligente Musik-Download-Anwendung"
authors = ["SoulSpot Team"]
packages = [{include = "soulspot", from = "src"}]

[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.31.0"}
pydantic = "^2.9.0"
pydantic-settings = "^2.6.0"
sqlalchemy = {extras = ["asyncio"], version = "^2.0.0"}
alembic = "^1.14.0"
aiosqlite = "^0.20.0"
httpx = "^0.28.0"
jinja2 = "^3.1.0"
python-multipart = "^0.0.18"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
python-dotenv = "^1.0.0"
rapidfuzz = "^3.14.0"
mutagen = "^1.47.0"
pillow = "^11.0.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.0"
pytest-asyncio = "^0.24.0"
pytest-cov = "^7.0.0"
pytest-mock = "^3.14.0"
pytest-httpx = "^0.35.0"
ruff = "^0.7.0"
mypy = "^1.13.0"
bandit = "^1.8.0"
pre-commit = "^3.8.0"

[tool.ruff]
target-version = "py312"
line-length = 88
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
```

#### 5.2.3 Pre-Commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: Ruff Format
        entry: ruff format
        language: system
        types: [python]
      - id: ruff-check
        name: Ruff Check
        entry: ruff check --fix
        language: system
        types: [python]
      - id: mypy
        name: MyPy
        entry: mypy
        language: system
        types: [python]
```

#### 5.2.4 Docker Setup

```yaml
# docker/docker-compose.yml
version: "3.8"

services:
  soulspot:
    build: ..
    ports:
      - "8765:8765"
    environment:
      - APP_ENV=development
    volumes:
      - ../mnt/downloads:/app/downloads
      - ../mnt/music:/app/music
    depends_on:
      - slskd

  slskd:
    image: slskd/slskd:latest
    ports:
      - "5030:5030"
    volumes:
      - ../mnt/downloads:/downloads
      - ../mnt/music:/music
    environment:
      - SLSKD_SLSK_USERNAME=${SLSKD_USERNAME}
      - SLSKD_SLSK_PASSWORD=${SLSKD_PASSWORD}
```

#### 5.2.5 Makefile

```makefile
.PHONY: install test lint format security

install:
poetry install --with dev

test:
pytest tests/ -v --cov=src

lint:
ruff check .

format:
ruff format .

type-check:
mypy src/

security:
bandit -r src/

all-checks: format lint type-check security test
```

### 5.3 Akzeptanzkriterien Phase 0

- [ ] Poetry-Projekt initialisiert
- [ ] Verzeichnisstruktur angelegt
- [ ] Pre-Commit Hooks konfiguriert
- [ ] Docker Compose funktionsfähig
- [ ] CI Pipeline Grundgerüst (GitHub Actions)
- [ ] README.md mit Projektbeschreibung
- [ ] .env.example mit allen Variablen
- [ ] .gitignore konfiguriert

### 5.4 Checkliste Phase 0

| Task | Status | Verantwortlich |
|------|--------|----------------|
| Repository erstellen | ☐ | DevOps |
| Poetry Setup | ☐ | Backend |
| Verzeichnisstruktur | ☐ | Backend |
| Pre-Commit Hooks | ☐ | Backend |
| Docker Compose | ☐ | DevOps |
| GitHub Actions Skeleton | ☐ | DevOps |
| Dokumentation | ☐ | Alle |

---

## 6. Phase 1: Foundation (Woche 2-3)

### 6.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 2 Wochen |
| **Ziel** | Domain Layer komplett, Projekt-Grundlagen |
| **Ergebnis** | Stabile Domain-Modelle mit Tests |
| **Version** | v0.0.1 |

### 6.2 Domain Entities

#### 6.2.1 Artist Entity

```python
# src/soulspot/domain/entities/artist.py

"""
Hey future me - Das Artist Entity ist die Basis für alle Musikdaten.
Wichtig: spotify_id ist optional weil manche Artists nur aus MusicBrainz kommen.
Die genres Liste wird später von Last.fm gefüllt - hab ich erstmal als leere Liste.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..value_objects import ArtistId

@dataclass
class Artist:
    """Musikinterpret mit Metadaten aus verschiedenen Quellen."""
    
    id: ArtistId
    name: str
    spotify_id: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    image_url: Optional[str] = None
    genres: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def update_from_spotify(self, spotify_data: dict) -> None:
        """Aktualisiert Artist-Daten aus Spotify API Response."""
        self.spotify_id = spotify_data.get("id")
        if images := spotify_data.get("images"):
            self.image_url = images[0]["url"]
        self.updated_at = datetime.utcnow()
    
    def add_genres(self, genres: list[str]) -> None:
        """Fügt Genres hinzu (ohne Duplikate)."""
        for genre in genres:
            if genre.lower() not in [g.lower() for g in self.genres]:
                self.genres.append(genre)
        self.updated_at = datetime.utcnow()
```

#### 6.2.2 Album Entity

```python
# src/soulspot/domain/entities/album.py

"""
Hey future me - Albums können ohne Tracks existieren (beim Import).
Die artwork_url hat verschiedene Auflösungen - ich speicher erstmal die größte.
track_count kommt von Spotify und wird für Album-Completeness-Checks gebraucht.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..value_objects import AlbumId, ArtistId

@dataclass
class Album:
    """Musikalbum mit Artwork und Release-Informationen."""
    
    id: AlbumId
    title: str
    artist_id: ArtistId
    spotify_id: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    release_year: Optional[int] = None
    artwork_url: Optional[str] = None
    track_count: int = 0
    genres: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def update_artwork(self, url: str) -> None:
        """Setzt neues Artwork (nur wenn noch keins vorhanden)."""
        if not self.artwork_url:
            self.artwork_url = url
            self.updated_at = datetime.utcnow()
```

#### 6.2.3 Track Entity

```python
# src/soulspot/domain/entities/track.py

"""
Hey future me - Das Track Entity ist das komplexeste. Hier sammeln sich Daten
aus 4+ Quellen (Spotify, MusicBrainz, Last.fm, slskd). Die file_* Felder werden
erst nach erfolgreichem Download gesetzt. is_broken markiert korrupte Dateien.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..value_objects import TrackId, AlbumId, ArtistId

@dataclass
class Track:
    """Einzelner Musik-Track mit umfassenden Metadaten."""
    
    id: TrackId
    title: str
    artist_id: ArtistId
    album_id: Optional[AlbumId] = None
    
    # External IDs
    spotify_uri: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    isrc: Optional[str] = None
    
    # Track Metadata
    duration_ms: int = 0
    track_number: Optional[int] = None
    disc_number: int = 1
    explicit: bool = False
    
    # File Information (nach Download)
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    audio_format: Optional[str] = None
    audio_bitrate: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    
    # Status
    is_broken: bool = False
    last_scanned_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_downloaded(self) -> bool:
        """Prüft ob Track heruntergeladen wurde."""
        return self.file_path is not None and not self.is_broken
    
    def mark_as_broken(self) -> None:
        """Markiert Track als korrupt/unvollständig."""
        self.is_broken = True
        self.updated_at = datetime.utcnow()
```

#### 6.2.4 Playlist Entity

```python
# src/soulspot/domain/entities/playlist.py

"""
Hey future me - Playlists kommen immer von Spotify (aktuell).
Das source Feld ist für spätere Erweiterungen (Local, Apple Music, etc.).
Die tracks Liste ist die Reihenfolge - Position matters!
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from ..value_objects import PlaylistId, TrackId

class PlaylistSource(str, Enum):
    SPOTIFY = "spotify"
    LOCAL = "local"

@dataclass
class Playlist:
    """Playlist mit Track-Referenzen und Sync-Status."""
    
    id: PlaylistId
    name: str
    source: PlaylistSource
    spotify_id: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    owner_name: Optional[str] = None
    track_ids: list[TrackId] = field(default_factory=list)
    
    # Sync Status
    last_synced_at: Optional[datetime] = None
    is_syncing: bool = False
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def track_count(self) -> int:
        return len(self.track_ids)
    
    def add_track(self, track_id: TrackId, position: Optional[int] = None) -> None:
        """Fügt Track an Position ein (oder am Ende)."""
        if track_id in self.track_ids:
            return  # Duplikat verhindern
        if position is not None:
            self.track_ids.insert(position, track_id)
        else:
            self.track_ids.append(track_id)
        self.updated_at = datetime.utcnow()
```

#### 6.2.5 Download Entity

```python
# src/soulspot/domain/entities/download.py

"""
Hey future me - Downloads durchlaufen mehrere Status. Wichtig:
- PENDING → SEARCHING → DOWNLOADING → PROCESSING → COMPLETED
- Bei Fehlern: FAILED (mit error_message)
- retry_count für exponential backoff (max 3)
- priority höher = wird früher verarbeitet
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from ..value_objects import DownloadId, TrackId

class DownloadStatus(str, Enum):
    PENDING = "pending"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

@dataclass
class Download:
    """Download-Auftrag für einen Track."""
    
    id: DownloadId
    track_id: TrackId
    status: DownloadStatus = DownloadStatus.PENDING
    priority: int = 0  # Höher = wichtiger
    
    # Progress
    progress: float = 0.0
    speed_bytes_per_sec: Optional[int] = None
    eta_seconds: Optional[int] = None
    
    # Source Info (von slskd)
    source_user: Optional[str] = None
    source_filename: Optional[str] = None
    
    # Error Handling
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries
    
    def start(self) -> None:
        """Startet den Download."""
        self.status = DownloadStatus.SEARCHING
        self.started_at = datetime.utcnow()
    
    def fail(self, error: str) -> None:
        """Markiert Download als fehlgeschlagen."""
        self.status = DownloadStatus.FAILED
        self.error_message = error
        self.retry_count += 1
    
    def complete(self) -> None:
        """Markiert Download als abgeschlossen."""
        self.status = DownloadStatus.COMPLETED
        self.progress = 100.0
        self.completed_at = datetime.utcnow()
```

### 6.3 Value Objects

```python
# src/soulspot/domain/value_objects/__init__.py

"""
Hey future me - Value Objects sind immutable und definieren sich über ihre Werte.
IDs sind UUIDs als Strings. SpotifyUri parsed das Format "spotify:track:ABC123".
FilePath validiert dass der Pfad existieren könnte (nicht dass er existiert!).
"""

from dataclasses import dataclass
from uuid import uuid4
import re

@dataclass(frozen=True)
class ArtistId:
    value: str = ""
    def __post_init__(self):
        if not self.value:
            object.__setattr__(self, 'value', str(uuid4()))

@dataclass(frozen=True)
class AlbumId:
    value: str = ""
    def __post_init__(self):
        if not self.value:
            object.__setattr__(self, 'value', str(uuid4()))

@dataclass(frozen=True)
class TrackId:
    value: str = ""
    def __post_init__(self):
        if not self.value:
            object.__setattr__(self, 'value', str(uuid4()))

@dataclass(frozen=True)
class PlaylistId:
    value: str = ""
    def __post_init__(self):
        if not self.value:
            object.__setattr__(self, 'value', str(uuid4()))

@dataclass(frozen=True)
class DownloadId:
    value: str = ""
    def __post_init__(self):
        if not self.value:
            object.__setattr__(self, 'value', str(uuid4()))

@dataclass(frozen=True)
class SpotifyUri:
    """Spotify URI im Format spotify:type:id"""
    uri: str
    
    def __post_init__(self):
        pattern = r'^spotify:(track|album|artist|playlist):[\w\d]+$'
        if not re.match(pattern, self.uri):
            raise ValueError(f"Invalid Spotify URI: {self.uri}")
    
    @property
    def type(self) -> str:
        return self.uri.split(":")[1]
    
    @property
    def id(self) -> str:
        return self.uri.split(":")[2]
```

### 6.4 Domain Exceptions

```python
# src/soulspot/domain/exceptions/domain_errors.py

"""
Hey future me - Alle Domain-Fehler erben von DomainException.
Das macht Error-Handling im API Layer einfacher (ein Handler für alle).
Der error_code wird im JSON Response verwendet.
"""

class DomainException(Exception):
    """Basis-Exception für alle Domain-Fehler."""
    error_code: str = "DOMAIN_ERROR"
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class EntityNotFoundException(DomainException):
    """Entity wurde nicht gefunden."""
    error_code = "ENTITY_NOT_FOUND"

class ValidationException(DomainException):
    """Validierung fehlgeschlagen."""
    error_code = "VALIDATION_ERROR"

class InvalidStateException(DomainException):
    """Ungültiger Zustand für Operation."""
    error_code = "INVALID_STATE"

class DuplicateEntityException(DomainException):
    """Entity existiert bereits."""
    error_code = "DUPLICATE_ENTITY"

class ExternalServiceException(DomainException):
    """Fehler bei externer Service-Kommunikation."""
    error_code = "EXTERNAL_SERVICE_ERROR"
```

### 6.5 Repository Ports (Interfaces)

```python
# src/soulspot/domain/ports/track_repository.py

"""
Hey future me - Das Interface definiert WAS, nicht WIE.
Die Implementierung kommt in Infrastructure. Das ermöglicht
einfaches Testen mit Mock-Repositories.
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..entities import Track
from ..value_objects import TrackId, AlbumId, ArtistId

class ITrackRepository(ABC):
    """Interface für Track-Persistenz."""
    
    @abstractmethod
    async def add(self, track: Track) -> Track:
        """Speichert neuen Track."""
        pass
    
    @abstractmethod
    async def get_by_id(self, track_id: TrackId) -> Optional[Track]:
        """Holt Track nach ID."""
        pass
    
    @abstractmethod
    async def get_by_spotify_uri(self, uri: str) -> Optional[Track]:
        """Holt Track nach Spotify URI."""
        pass
    
    @abstractmethod
    async def get_by_album(self, album_id: AlbumId) -> list[Track]:
        """Holt alle Tracks eines Albums."""
        pass
    
    @abstractmethod
    async def update(self, track: Track) -> Track:
        """Aktualisiert Track."""
        pass
    
    @abstractmethod
    async def get_broken_tracks(self) -> list[Track]:
        """Holt alle als broken markierten Tracks."""
        pass
```

### 6.6 Unit Tests für Phase 1

```python
# tests/unit/domain/test_entities.py

"""
Hey future me - Diese Tests validieren die Domain-Logik isoliert.
Keine Datenbank, keine externen APIs - reine Business Logic Tests.
"""

import pytest
from datetime import datetime

from soulspot.domain.entities import Artist, Album, Track, Playlist, Download
from soulspot.domain.entities.download import DownloadStatus
from soulspot.domain.value_objects import ArtistId, AlbumId, TrackId, PlaylistId

class TestArtistEntity:
    def test_create_artist(self):
        artist = Artist(id=ArtistId(), name="The Beatles")
        assert artist.name == "The Beatles"
        assert artist.id.value is not None
    
    def test_update_from_spotify(self):
        artist = Artist(id=ArtistId(), name="Test")
        spotify_data = {
            "id": "spotify123",
            "images": [{"url": "https://example.com/image.jpg"}]
        }
        artist.update_from_spotify(spotify_data)
        assert artist.spotify_id == "spotify123"
        assert artist.image_url == "https://example.com/image.jpg"
    
    def test_add_genres_without_duplicates(self):
        artist = Artist(id=ArtistId(), name="Test", genres=["rock"])
        artist.add_genres(["Rock", "pop", "ROCK"])
        assert len(artist.genres) == 2  # rock, pop (keine Duplikate)


class TestDownloadEntity:
    def test_download_lifecycle(self):
        download = Download(id=DownloadId(), track_id=TrackId())
        
        assert download.status == DownloadStatus.PENDING
        
        download.start()
        assert download.status == DownloadStatus.SEARCHING
        assert download.started_at is not None
        
    def test_can_retry_logic(self):
        download = Download(id=DownloadId(), track_id=TrackId(), max_retries=3)
        
        assert download.can_retry == True
        
        download.fail("Error 1")
        download.fail("Error 2")
        download.fail("Error 3")
        
        assert download.can_retry == False
        assert download.retry_count == 3
```

### 6.7 Akzeptanzkriterien Phase 1

- [ ] Alle Domain Entities implementiert (Artist, Album, Track, Playlist, Download)
- [ ] Alle Value Objects implementiert (IDs, SpotifyUri, FilePath)
- [ ] Alle Domain Exceptions definiert
- [ ] Alle Repository Interfaces definiert
- [ ] 20+ Unit Tests für Domain Layer
- [ ] 100% Type Coverage mit mypy
- [ ] Ruff Linting bestanden
- [ ] Dokumentation für Domain Layer

### 6.8 Checkliste Phase 1

| Task | Effort | Status |
|------|--------|--------|
| Artist Entity | 2h | ☐ |
| Album Entity | 2h | ☐ |
| Track Entity | 3h | ☐ |
| Playlist Entity | 2h | ☐ |
| Download Entity | 3h | ☐ |
| Value Objects | 2h | ☐ |
| Domain Exceptions | 1h | ☐ |
| Repository Interfaces | 3h | ☐ |
| Unit Tests | 4h | ☐ |
| Documentation | 2h | ☐ |

---

## 7. Phase 2: Core Infrastructure (Woche 4-6)

### 7.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 3 Wochen |
| **Ziel** | Datenbank, Settings, FastAPI Grundgerüst |
| **Ergebnis** | Funktionierende Persistenz und API-Basis |
| **Version** | v0.0.2 |

### 7.2 Settings Management

#### 7.2.1 Pydantic Settings Klasse

```python
# src/soulspot/config/settings.py

"""
Hey future me - Settings werden aus Environment Variablen geladen.
Nested Delimiter "__" ermöglicht SPOTIFY__CLIENT_ID=xyz.
Validierung für Production (SECRET_KEY muss gesetzt sein).
model_config erlaubt .env File und extra Felder ignorieren.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Literal

class DatabaseSettings(BaseSettings):
    """Datenbank-Konfiguration."""
    url: str = "sqlite+aiosqlite:///./data/soulspot.db"
    echo: bool = False
    pool_size: int = 5
    pool_timeout: int = 30
    pool_recycle: int = 1800
    pool_pre_ping: bool = True

class SpotifySettings(BaseSettings):
    """Spotify API Konfiguration."""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8765/api/auth/callback"
    scopes: str = "playlist-read-private playlist-read-collaborative"

class SlskdSettings(BaseSettings):
    """slskd (Soulseek) Konfiguration."""
    base_url: str = "http://slskd:5030"
    api_key: str = ""
    username: str = ""
    password: str = ""

class MusicBrainzSettings(BaseSettings):
    """MusicBrainz API Konfiguration."""
    base_url: str = "https://musicbrainz.org/ws/2"
    user_agent: str = "SoulSpot/1.0 (contact@example.com)"
    rate_limit_per_second: float = 1.0

class StorageSettings(BaseSettings):
    """Speicher-Pfade Konfiguration."""
    downloads_dir: Path = Path("./mnt/downloads")
    music_dir: Path = Path("./mnt/music")
    temp_dir: Path = Path("./tmp")

class APISettings(BaseSettings):
    """API Server Konfiguration."""
    host: str = "0.0.0.0"
    port: int = 8765
    debug: bool = False
    secret_key: str = ""
    cors_origins: list[str] = ["http://localhost:8765"]

class Settings(BaseSettings):
    """Haupt-Konfiguration mit allen Sub-Settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )
    
    app_name: str = "SoulSpot"
    app_version: str = "0.1.0"
    environment: Literal["development", "production"] = "development"
    
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    spotify: SpotifySettings = Field(default_factory=SpotifySettings)
    slskd: SlskdSettings = Field(default_factory=SlskdSettings)
    musicbrainz: MusicBrainzSettings = Field(default_factory=MusicBrainzSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    api: APISettings = Field(default_factory=APISettings)
    
    @field_validator("api", mode="after")
    @classmethod
    def validate_production_secret(cls, v, info):
        if info.data.get("environment") == "production":
            if not v.secret_key or v.secret_key == "changeme":
                raise ValueError("SECRET_KEY must be set in production")
        return v

# Singleton-Pattern für globale Settings
_settings: Settings | None = None

def get_settings() -> Settings:
    """Cached Settings-Instanz."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

### 7.3 Database Layer

#### 7.3.1 SQLAlchemy Models

```python
# src/soulspot/infrastructure/persistence/models.py

"""
Hey future me - ORM Models sind unabhängig von Domain Entities.
Mappers konvertieren zwischen beiden. Das erlaubt DB-Schema
Änderungen ohne Domain zu ändern und umgekehrt.
"""

from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    """Basis-Klasse für alle SQLAlchemy Models."""
    pass

class ArtistModel(Base):
    __tablename__ = "artists"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    spotify_id: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    musicbrainz_id: Mapped[str | None] = mapped_column(String(36), unique=True, index=True)
    image_url: Mapped[str | None] = mapped_column(String(500))
    genres: Mapped[str | None] = mapped_column(Text)  # JSON-encoded list
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    albums: Mapped[list["AlbumModel"]] = relationship(back_populates="artist")
    tracks: Mapped[list["TrackModel"]] = relationship(back_populates="artist")

class AlbumModel(Base):
    __tablename__ = "albums"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[str] = mapped_column(ForeignKey("artists.id"), nullable=False, index=True)
    spotify_id: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    musicbrainz_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    release_year: Mapped[int | None] = mapped_column(Integer)
    artwork_url: Mapped[str | None] = mapped_column(String(500))
    track_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    artist: Mapped["ArtistModel"] = relationship(back_populates="albums")
    tracks: Mapped[list["TrackModel"]] = relationship(back_populates="album")

class TrackModel(Base):
    __tablename__ = "tracks"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[str] = mapped_column(ForeignKey("artists.id"), nullable=False, index=True)
    album_id: Mapped[str | None] = mapped_column(ForeignKey("albums.id"), index=True)
    
    # External IDs
    spotify_uri: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    musicbrainz_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    isrc: Mapped[str | None] = mapped_column(String(20), index=True)
    
    # Track Metadata
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    track_number: Mapped[int | None] = mapped_column(Integer)
    disc_number: Mapped[int] = mapped_column(Integer, default=1)
    explicit: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # File Information
    file_path: Mapped[str | None] = mapped_column(String(500), index=True)
    file_hash: Mapped[str | None] = mapped_column(String(64))  # SHA256
    file_size: Mapped[int | None] = mapped_column(Integer)
    audio_format: Mapped[str | None] = mapped_column(String(20))
    audio_bitrate: Mapped[int | None] = mapped_column(Integer)
    
    # Status
    is_broken: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    artist: Mapped["ArtistModel"] = relationship(back_populates="tracks")
    album: Mapped["AlbumModel"] = relationship(back_populates="tracks")

class PlaylistModel(Base):
    __tablename__ = "playlists"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    spotify_id: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="spotify")
    description: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(String(500))
    owner_name: Mapped[str | None] = mapped_column(String(100))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    track_associations: Mapped[list["PlaylistTrackModel"]] = relationship(back_populates="playlist")

class PlaylistTrackModel(Base):
    """Assoziationstabelle für Playlist-Track-Beziehung mit Position."""
    __tablename__ = "playlist_tracks"
    
    playlist_id: Mapped[str] = mapped_column(ForeignKey("playlists.id"), primary_key=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    playlist: Mapped["PlaylistModel"] = relationship(back_populates="track_associations")
    track: Mapped["TrackModel"] = relationship()

class DownloadModel(Base):
    __tablename__ = "downloads"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    source_user: Mapped[str | None] = mapped_column(String(100))
    source_filename: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    
    # Relationships
    track: Mapped["TrackModel"] = relationship()
```

#### 7.3.2 Database Connection

```python
# src/soulspot/infrastructure/persistence/database.py

"""
Hey future me - Async Database mit Context Manager.
Die engine ist ein Singleton, Session wird pro Request erstellt.
AsyncSessionLocal ist ein Factory für Sessions.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from ...config.settings import get_settings
from .models import Base

_engine = None
_session_factory = None

async def init_database() -> None:
    """Initialisiert Datenbank-Engine und erstellt Tabellen."""
    global _engine, _session_factory
    
    settings = get_settings()
    
    _engine = create_async_engine(
        settings.database.url,
        echo=settings.database.echo,
        pool_pre_ping=settings.database.pool_pre_ping,
    )
    
    _session_factory = async_sessionmaker(
        _engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    # Tabellen erstellen (nur für Development)
    if settings.environment == "development":
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

async def close_database() -> None:
    """Schließt Datenbank-Verbindungen."""
    global _engine
    if _engine:
        await _engine.dispose()

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context Manager für Database Sessions."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized")
    
    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

### 7.4 Repository Implementierungen

```python
# src/soulspot/infrastructure/persistence/repositories.py

"""
Hey future me - Repositories implementieren die Domain Ports.
Sie mappen zwischen ORM Models und Domain Entities.
Alle Methoden sind async für non-blocking DB Zugriffe.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ...domain.entities import Track
from ...domain.value_objects import TrackId, AlbumId, ArtistId
from ...domain.ports import ITrackRepository
from .models import TrackModel

class TrackRepository(ITrackRepository):
    """SQLAlchemy-Implementierung des Track Repository."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def add(self, track: Track) -> Track:
        model = self._to_model(track)
        self._session.add(model)
        await self._session.flush()
        return track
    
    async def get_by_id(self, track_id: TrackId) -> Optional[Track]:
        result = await self._session.execute(
            select(TrackModel).where(TrackModel.id == track_id.value)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def get_by_spotify_uri(self, uri: str) -> Optional[Track]:
        result = await self._session.execute(
            select(TrackModel).where(TrackModel.spotify_uri == uri)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def get_by_album(self, album_id: AlbumId) -> list[Track]:
        result = await self._session.execute(
            select(TrackModel)
            .where(TrackModel.album_id == album_id.value)
            .order_by(TrackModel.disc_number, TrackModel.track_number)
        )
        return [self._to_entity(m) for m in result.scalars().all()]
    
    async def update(self, track: Track) -> Track:
        result = await self._session.execute(
            select(TrackModel).where(TrackModel.id == track.id.value)
        )
        model = result.scalar_one()
        self._update_model(model, track)
        await self._session.flush()
        return track
    
    async def get_broken_tracks(self) -> list[Track]:
        result = await self._session.execute(
            select(TrackModel).where(TrackModel.is_broken == True)
        )
        return [self._to_entity(m) for m in result.scalars().all()]
    
    def _to_model(self, entity: Track) -> TrackModel:
        """Konvertiert Domain Entity zu ORM Model."""
        return TrackModel(
            id=entity.id.value,
            title=entity.title,
            artist_id=entity.artist_id.value,
            album_id=entity.album_id.value if entity.album_id else None,
            spotify_uri=entity.spotify_uri,
            musicbrainz_id=entity.musicbrainz_id,
            isrc=entity.isrc,
            duration_ms=entity.duration_ms,
            track_number=entity.track_number,
            disc_number=entity.disc_number,
            file_path=entity.file_path,
            is_broken=entity.is_broken,
        )
    
    def _to_entity(self, model: TrackModel) -> Track:
        """Konvertiert ORM Model zu Domain Entity."""
        return Track(
            id=TrackId(model.id),
            title=model.title,
            artist_id=ArtistId(model.artist_id),
            album_id=AlbumId(model.album_id) if model.album_id else None,
            spotify_uri=model.spotify_uri,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            duration_ms=model.duration_ms,
            track_number=model.track_number,
            disc_number=model.disc_number,
            file_path=model.file_path,
            is_broken=model.is_broken,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _update_model(self, model: TrackModel, entity: Track) -> None:
        """Aktualisiert ORM Model aus Entity."""
        model.title = entity.title
        model.file_path = entity.file_path
        model.is_broken = entity.is_broken
        # ... weitere Felder
```

### 7.5 FastAPI Application

```python
# src/soulspot/main.py

"""
Hey future me - Das ist der Entry Point der Anwendung.
Lifespan Context Manager handelt Startup/Shutdown.
Health Checks sind für Docker/Kubernetes wichtig.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import logging

from .config.settings import get_settings
from .infrastructure.persistence.database import init_database, close_database
from .api.routers import auth, playlists, downloads, tracks, ui

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle Management für die Anwendung."""
    # Startup
    logger.info("Starting SoulSpot application...")
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.exception("Failed to initialize database")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down SoulSpot application...")
    try:
        await close_database()
    except Exception:
        logger.exception("Error during database shutdown")

def create_app() -> FastAPI:
    """Factory Function für FastAPI Application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment == "development" else None,
    )
    
    # Static Files & Templates
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=static_path), name="static")
    
    # Routers
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])
    app.include_router(downloads.router, prefix="/api/downloads", tags=["downloads"])
    app.include_router(tracks.router, prefix="/api/tracks", tags=["tracks"])
    app.include_router(ui.router, tags=["ui"])
    
    # Health Checks
    @app.get("/health/live")
    async def liveness():
        return {"status": "ok"}
    
    @app.get("/health/ready")
    async def readiness():
        # Prüfe DB-Verbindung, externe Services
        return {"status": "ok", "database": "connected"}
    
    return app

# Für uvicorn: soulspot.main:app
app = create_app()

def main():
    """Entry Point für CLI."""
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "soulspot.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.environment == "development"
    )
```

### 7.6 Alembic Migrations

```python
# alembic/versions/001_initial_schema.py

"""
Initial database schema

Revision ID: 259d78cbdfef
Revises: 
Create Date: 2025-01-01
"""

from alembic import op
import sqlalchemy as sa

revision = '259d78cbdfef'
down_revision = None

def upgrade() -> None:
    # Artists Table
    op.create_table(
        'artists',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('spotify_id', sa.String(50), unique=True, index=True),
        sa.Column('musicbrainz_id', sa.String(36), unique=True),
        sa.Column('image_url', sa.String(500)),
        sa.Column('genres', sa.Text),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now()),
    )
    
    # Albums Table
    op.create_table(
        'albums',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('artist_id', sa.String(36), sa.ForeignKey('artists.id'), nullable=False),
        sa.Column('spotify_id', sa.String(50), unique=True, index=True),
        sa.Column('release_year', sa.Integer),
        sa.Column('artwork_url', sa.String(500)),
        sa.Column('track_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )
    
    # Tracks Table
    op.create_table(
        'tracks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('artist_id', sa.String(36), sa.ForeignKey('artists.id'), nullable=False),
        sa.Column('album_id', sa.String(36), sa.ForeignKey('albums.id')),
        sa.Column('spotify_uri', sa.String(100), unique=True, index=True),
        sa.Column('isrc', sa.String(20), index=True),
        sa.Column('duration_ms', sa.Integer, default=0),
        sa.Column('track_number', sa.Integer),
        sa.Column('file_path', sa.String(500)),
        sa.Column('is_broken', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )
    
    # Playlists Table
    op.create_table(
        'playlists',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('spotify_id', sa.String(50), unique=True, index=True),
        sa.Column('source', sa.String(20), default='spotify'),
        sa.Column('last_synced_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )
    
    # Playlist Tracks Association Table
    op.create_table(
        'playlist_tracks',
        sa.Column('playlist_id', sa.String(36), sa.ForeignKey('playlists.id'), primary_key=True),
        sa.Column('track_id', sa.String(36), sa.ForeignKey('tracks.id'), primary_key=True),
        sa.Column('position', sa.Integer, nullable=False),
        sa.Column('added_at', sa.DateTime),
    )
    
    # Downloads Table
    op.create_table(
        'downloads',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('track_id', sa.String(36), sa.ForeignKey('tracks.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('progress', sa.Float, default=0.0),
        sa.Column('error_message', sa.Text),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
    )
    
    # Create indexes
    op.create_index('ix_downloads_status_priority', 'downloads', ['status', 'priority'])
    op.create_index('ix_tracks_album_track_number', 'tracks', ['album_id', 'track_number'])

def downgrade() -> None:
    op.drop_table('downloads')
    op.drop_table('playlist_tracks')
    op.drop_table('playlists')
    op.drop_table('tracks')
    op.drop_table('albums')
    op.drop_table('artists')
```

### 7.7 Akzeptanzkriterien Phase 2

- [ ] Pydantic Settings vollständig konfiguriert
- [ ] SQLAlchemy Models für alle Entities
- [ ] Repository Implementierungen für alle Ports
- [ ] Alembic Migration lauffähig
- [ ] FastAPI Application startet
- [ ] Health Check Endpoints funktionieren
- [ ] 30+ Integration Tests für Repositories
- [ ] Docker Compose mit DB funktioniert

### 7.8 Checkliste Phase 2

| Task | Effort | Status |
|------|--------|--------|
| Settings Management | 4h | ☐ |
| Database Models | 6h | ☐ |
| Database Connection | 3h | ☐ |
| Artist Repository | 3h | ☐ |
| Album Repository | 3h | ☐ |
| Track Repository | 4h | ☐ |
| Playlist Repository | 4h | ☐ |
| Download Repository | 3h | ☐ |
| Alembic Setup | 2h | ☐ |
| Initial Migration | 2h | ☐ |
| FastAPI Application | 4h | ☐ |
| Health Checks | 2h | ☐ |
| Integration Tests | 8h | ☐ |
| Documentation | 3h | ☐ |

---

## 8. Phase 3: External Integrations (Woche 7-9)

### 8.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 3 Wochen |
| **Ziel** | Integration mit Spotify, slskd, MusicBrainz |
| **Ergebnis** | Funktionierende API-Clients für alle externen Services |
| **Version** | v0.0.3 |

### 8.2 Spotify Client

#### 8.2.1 OAuth 2.0 PKCE Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SPOTIFY OAUTH PKCE FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. User klickt "Mit Spotify verbinden"                                    │
│     │                                                                       │
│     ▼                                                                       │
│  2. Backend generiert:                                                      │
│     • code_verifier (zufälliger 128-Byte String)                           │
│     • code_challenge = BASE64URL(SHA256(code_verifier))                    │
│     • state (CSRF-Schutz)                                                  │
│     │                                                                       │
│     ▼                                                                       │
│  3. Redirect zu Spotify Authorization:                                      │
│     https://accounts.spotify.com/authorize?                                │
│       client_id=XXX                                                        │
│       response_type=code                                                   │
│       redirect_uri=http://localhost:8765/api/auth/callback                 │
│       code_challenge=YYY                                                   │
│       code_challenge_method=S256                                           │
│       scope=playlist-read-private                                          │
│       state=ZZZ                                                            │
│     │                                                                       │
│     ▼                                                                       │
│  4. User autorisiert App bei Spotify                                       │
│     │                                                                       │
│     ▼                                                                       │
│  5. Spotify redirected zurück mit ?code=ABC&state=ZZZ                      │
│     │                                                                       │
│     ▼                                                                       │
│  6. Backend tauscht Code gegen Tokens:                                      │
│     POST https://accounts.spotify.com/api/token                            │
│       grant_type=authorization_code                                        │
│       code=ABC                                                             │
│       redirect_uri=http://localhost:8765/api/auth/callback                 │
│       client_id=XXX                                                        │
│       code_verifier=ORIGINAL_VERIFIER                                      │
│     │                                                                       │
│     ▼                                                                       │
│  7. Spotify gibt zurück:                                                   │
│     {                                                                      │
│       "access_token": "...",                                              │
│       "refresh_token": "...",                                             │
│       "expires_in": 3600                                                   │
│     }                                                                      │
│     │                                                                       │
│     ▼                                                                       │
│  8. Tokens werden in Session gespeichert                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 8.2.2 Spotify Client Implementation

```python
# src/soulspot/infrastructure/integrations/spotify_client.py

"""
Hey future me - Der Spotify Client handled OAuth UND API Calls.
PKCE ist wichtiger weil es ohne Client Secret funktioniert (sicherer).
Token Refresh passiert automatisch wenn access_token abläuft.
Rate Limits: 100 req/min - ich hab exponential backoff eingebaut.
"""

import httpx
import hashlib
import base64
import secrets
from typing import Optional, Any
from datetime import datetime, timedelta
import logging

from ...domain.ports import ISpotifyClient
from ...config.settings import get_settings

logger = logging.getLogger(__name__)

class SpotifyClient(ISpotifyClient):
    """Async Spotify API Client mit OAuth PKCE."""
    
    AUTH_BASE_URL = "https://accounts.spotify.com"
    API_BASE_URL = "https://api.spotify.com/v1"
    
    def __init__(self):
        self._settings = get_settings().spotify
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Token Storage (per Instance - in Production: Session Store)
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        # PKCE State (pro Authorization Flow)
        self._code_verifier: Optional[str] = None
        self._state: Optional[str] = None
    
    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
    
    def get_authorization_url(self) -> tuple[str, str, str]:
        """
        Generiert Authorization URL mit PKCE.
        Returns: (auth_url, state, code_verifier)
        """
        # Code Verifier: Zufälliger String 43-128 Zeichen
        self._code_verifier = secrets.token_urlsafe(64)
        
        # Code Challenge: BASE64URL(SHA256(verifier))
        verifier_bytes = self._code_verifier.encode('ascii')
        challenge_hash = hashlib.sha256(verifier_bytes).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_hash).decode('ascii').rstrip('=')
        
        # State für CSRF-Schutz
        self._state = secrets.token_urlsafe(32)
        
        # Authorization URL zusammenbauen
        params = {
            "client_id": self._settings.client_id,
            "response_type": "code",
            "redirect_uri": self._settings.redirect_uri,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "state": self._state,
            "scope": self._settings.scopes,
        }
        
        auth_url = f"{self.AUTH_BASE_URL}/authorize?" + "&".join(
            f"{k}={v}" for k, v in params.items()
        )
        
        return auth_url, self._state, self._code_verifier
    
    async def exchange_code_for_tokens(
        self, 
        code: str, 
        code_verifier: str
    ) -> dict[str, Any]:
        """Tauscht Authorization Code gegen Access/Refresh Tokens."""
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._settings.redirect_uri,
            "client_id": self._settings.client_id,
            "code_verifier": code_verifier,
        }
        
        response = await self._http_client.post(
            f"{self.AUTH_BASE_URL}/api/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        
        token_data = response.json()
        self._store_tokens(token_data)
        
        logger.info("Successfully obtained Spotify tokens")
        return token_data
    
    async def refresh_access_token(self) -> dict[str, Any]:
        """Erneuert Access Token mit Refresh Token."""
        
        if not self._refresh_token:
            raise ValueError("No refresh token available")
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._settings.client_id,
        }
        
        response = await self._http_client.post(
            f"{self.AUTH_BASE_URL}/api/token",
            data=data,
        )
        response.raise_for_status()
        
        token_data = response.json()
        self._store_tokens(token_data)
        
        return token_data
    
    def _store_tokens(self, token_data: dict) -> None:
        """Speichert Tokens intern."""
        self._access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            self._refresh_token = token_data["refresh_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
    
    async def _ensure_valid_token(self) -> str:
        """Stellt sicher dass ein gültiger Token vorhanden ist."""
        if not self._access_token:
            raise ValueError("Not authenticated")
        
        if self._token_expires_at and datetime.utcnow() >= self._token_expires_at:
            await self.refresh_access_token()
        
        return self._access_token
    
    async def _api_request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> dict[str, Any]:
        """Führt authentifizierte API-Anfrage aus."""
        
        token = await self._ensure_valid_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            **kwargs.pop("headers", {})
        }
        
        url = f"{self.API_BASE_URL}{endpoint}"
        
        for attempt in range(3):
            response = await self._http_client.request(
                method, url, headers=headers, **kwargs
            )
            
            if response.status_code == 429:
                # Rate Limited - Retry nach Wartezeit
                retry_after = int(response.headers.get("Retry-After", 1))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                await asyncio.sleep(retry_after)
                continue
            
            response.raise_for_status()
            return response.json()
        
        raise Exception("Max retries exceeded for Spotify API")
    
    # ─────────────────────────────────────────────────────────────────
    # Public API Methods
    # ─────────────────────────────────────────────────────────────────
    
    async def get_current_user(self) -> dict[str, Any]:
        """Holt aktuellen Benutzer-Info."""
        return await self._api_request("GET", "/me")
    
    async def get_user_playlists(
        self, 
        limit: int = 50, 
        offset: int = 0
    ) -> dict[str, Any]:
        """Holt Playlists des aktuellen Benutzers."""
        return await self._api_request(
            "GET", "/me/playlists",
            params={"limit": limit, "offset": offset}
        )
    
    async def get_playlist(self, playlist_id: str) -> dict[str, Any]:
        """Holt Playlist Details."""
        return await self._api_request("GET", f"/playlists/{playlist_id}")
    
    async def get_playlist_tracks(
        self, 
        playlist_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> dict[str, Any]:
        """Holt Tracks einer Playlist."""
        return await self._api_request(
            "GET", f"/playlists/{playlist_id}/tracks",
            params={"limit": limit, "offset": offset}
        )
    
    async def get_track(self, track_id: str) -> dict[str, Any]:
        """Holt Track Details."""
        return await self._api_request("GET", f"/tracks/{track_id}")
    
    async def search(
        self, 
        query: str, 
        types: list[str] = ["track"],
        limit: int = 20
    ) -> dict[str, Any]:
        """Durchsucht Spotify-Katalog."""
        return await self._api_request(
            "GET", "/search",
            params={
                "q": query,
                "type": ",".join(types),
                "limit": limit
            }
        )
    
    async def get_artist_albums(
        self, 
        artist_id: str,
        include_groups: str = "album,single",
        limit: int = 50
    ) -> dict[str, Any]:
        """Holt Alben eines Künstlers."""
        return await self._api_request(
            "GET", f"/artists/{artist_id}/albums",
            params={"include_groups": include_groups, "limit": limit}
        )
```

### 8.3 slskd Client

```python
# src/soulspot/infrastructure/integrations/slskd_client.py

"""
Hey future me - slskd ist ein Soulseek Daemon mit REST API.
Der Client macht: Suchen → Download starten → Status überwachen.
Wichtig: slskd läuft lokal im Docker-Netzwerk, daher keine Auth nötig
(außer API Key wenn konfiguriert).
"""

import httpx
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class SlskdClient:
    """Async Client für slskd (Soulseek) API."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        headers = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        self._http_client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=60.0
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
    
    async def search(
        self, 
        query: str,
        timeout_seconds: int = 30
    ) -> list[dict[str, Any]]:
        """
        Sucht nach Dateien im Soulseek-Netzwerk.
        Returns: Liste von Search Results mit User und Dateien.
        """
        # Search starten
        response = await self._http_client.post(
            "/api/v0/searches",
            json={"searchText": query}
        )
        response.raise_for_status()
        search_data = response.json()
        search_id = search_data["id"]
        
        logger.info(f"Started search {search_id} for: {query}")
        
        # Warten auf Ergebnisse (Polling)
        import asyncio
        results = []
        for _ in range(timeout_seconds):
            await asyncio.sleep(1)
            
            status_response = await self._http_client.get(
                f"/api/v0/searches/{search_id}"
            )
            status = status_response.json()
            
            if status.get("state") == "Completed":
                results = status.get("responses", [])
                break
        
        # Search beenden
        await self._http_client.delete(f"/api/v0/searches/{search_id}")
        
        logger.info(f"Search completed with {len(results)} responses")
        return results
    
    async def start_download(
        self, 
        username: str, 
        filename: str
    ) -> dict[str, Any]:
        """Startet Download einer Datei von einem User."""
        
        response = await self._http_client.post(
            "/api/v0/transfers/downloads",
            json={
                "username": username,
                "filename": filename
            }
        )
        response.raise_for_status()
        
        logger.info(f"Started download: {filename} from {username}")
        return response.json()
    
    async def get_download_status(self, download_id: str) -> dict[str, Any]:
        """Holt Status eines Downloads."""
        response = await self._http_client.get(
            f"/api/v0/transfers/downloads/{download_id}"
        )
        response.raise_for_status()
        return response.json()
    
    async def get_all_downloads(self) -> list[dict[str, Any]]:
        """Holt alle aktiven Downloads."""
        response = await self._http_client.get("/api/v0/transfers/downloads")
        response.raise_for_status()
        return response.json()
    
    async def cancel_download(self, download_id: str) -> None:
        """Bricht Download ab."""
        await self._http_client.delete(
            f"/api/v0/transfers/downloads/{download_id}"
        )
        logger.info(f"Cancelled download: {download_id}")
    
    async def get_server_state(self) -> dict[str, Any]:
        """Holt Server-Status (für Health Checks)."""
        response = await self._http_client.get("/api/v0/server/state")
        response.raise_for_status()
        return response.json()
```

### 8.4 MusicBrainz Client

```python
# src/soulspot/infrastructure/integrations/musicbrainz_client.py

"""
Hey future me - MusicBrainz hat strenge Rate Limits: 1 req/sec.
Der Client hat einen eingebauten Rate Limiter.
ISRC-Lookup ist am zuverlässigsten für exakte Matches.
Bei fehlgeschlagenem ISRC: Fallback zu Artist+Title Suche.
"""

import httpx
import asyncio
from typing import Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MusicBrainzClient:
    """Async MusicBrainz API Client mit Rate Limiting."""
    
    BASE_URL = "https://musicbrainz.org/ws/2"
    
    def __init__(self, user_agent: str):
        self._user_agent = user_agent
        self._http_client: Optional[httpx.AsyncClient] = None
        self._last_request_time: Optional[datetime] = None
        self._min_request_interval = 1.0  # 1 second
    
    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "User-Agent": self._user_agent,
                "Accept": "application/json"
            },
            timeout=30.0
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
    
    async def _rate_limited_request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> dict[str, Any]:
        """Führt Rate-Limited Request aus."""
        
        # Rate Limiting
        if self._last_request_time:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - elapsed)
        
        self._last_request_time = datetime.utcnow()
        
        # Retry Logic
        for attempt in range(3):
            try:
                response = await self._http_client.request(
                    method, endpoint, **kwargs
                )
                
                if response.status_code == 503:
                    # Service Unavailable - längere Pause
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        
        raise Exception("Max retries exceeded")
    
    async def lookup_by_isrc(self, isrc: str) -> Optional[dict[str, Any]]:
        """Sucht Recording nach ISRC (International Standard Recording Code)."""
        
        try:
            result = await self._rate_limited_request(
                "GET", "/isrc/" + isrc,
                params={"inc": "artist-credits+releases"}
            )
            
            recordings = result.get("recordings", [])
            if recordings:
                logger.info(f"Found recording for ISRC {isrc}")
                return recordings[0]
            return None
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def search_recording(
        self, 
        title: str, 
        artist: str
    ) -> list[dict[str, Any]]:
        """Sucht Recordings nach Titel und Künstler."""
        
        query = f'recording:"{title}" AND artist:"{artist}"'
        
        result = await self._rate_limited_request(
            "GET", "/recording",
            params={
                "query": query,
                "limit": 5,
                "fmt": "json"
            }
        )
        
        return result.get("recordings", [])
    
    async def get_release(self, release_id: str) -> dict[str, Any]:
        """Holt Release (Album) Details."""
        
        return await self._rate_limited_request(
            "GET", f"/release/{release_id}",
            params={"inc": "artist-credits+recordings+release-groups"}
        )
    
    async def get_artist(self, artist_id: str) -> dict[str, Any]:
        """Holt Artist Details."""
        
        return await self._rate_limited_request(
            "GET", f"/artist/{artist_id}",
            params={"inc": "aliases+tags"}
        )
    
    async def get_cover_art(self, release_id: str) -> Optional[str]:
        """Holt Cover Art URL von CoverArtArchive."""
        
        try:
            # CoverArtArchive hat eigene URL
            url = f"https://coverartarchive.org/release/{release_id}"
            
            response = await self._http_client.get(url)
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            images = data.get("images", [])
            for img in images:
                if img.get("front"):
                    return img.get("image")
            
            return images[0].get("image") if images else None
            
        except Exception as e:
            logger.warning(f"Failed to get cover art: {e}")
            return None
```

### 8.5 Last.fm Client (Genres & Tags)

```python
# src/soulspot/infrastructure/integrations/lastfm_client.py

"""
Hey future me - Last.fm ist die beste Quelle für Genres und Tags.
API Key ist kostenlos (https://www.last.fm/api/account/create).
Rate Limit: 5 req/sec - großzügiger als MusicBrainz.
"""

import httpx
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class LastfmClient:
    """Async Last.fm API Client für Genres und Tags."""
    
    BASE_URL = "https://ws.audioscrobbler.com/2.0/"
    
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
    
    async def _request(
        self, 
        method_name: str, 
        **params
    ) -> dict[str, Any]:
        """Führt Last.fm API Request aus."""
        
        all_params = {
            "method": method_name,
            "api_key": self._api_key,
            "format": "json",
            **params
        }
        
        response = await self._http_client.get(
            self.BASE_URL, 
            params=all_params
        )
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            raise Exception(f"Last.fm error: {data['message']}")
        
        return data
    
    async def get_track_tags(
        self, 
        artist: str, 
        track: str
    ) -> list[str]:
        """Holt Top Tags für einen Track."""
        
        try:
            data = await self._request(
                "track.getTopTags",
                artist=artist,
                track=track
            )
            
            tags = data.get("toptags", {}).get("tag", [])
            return [t["name"] for t in tags[:10]]  # Top 10 Tags
            
        except Exception as e:
            logger.warning(f"Failed to get track tags: {e}")
            return []
    
    async def get_artist_tags(self, artist: str) -> list[str]:
        """Holt Top Tags für einen Artist."""
        
        try:
            data = await self._request(
                "artist.getTopTags",
                artist=artist
            )
            
            tags = data.get("toptags", {}).get("tag", [])
            return [t["name"] for t in tags[:10]]
            
        except Exception as e:
            logger.warning(f"Failed to get artist tags: {e}")
            return []
    
    async def get_similar_artists(
        self, 
        artist: str, 
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """Holt ähnliche Künstler."""
        
        data = await self._request(
            "artist.getSimilar",
            artist=artist,
            limit=limit
        )
        
        return data.get("similarartists", {}).get("artist", [])
```

### 8.6 Akzeptanzkriterien Phase 3

- [ ] Spotify OAuth PKCE Flow vollständig implementiert
- [ ] Spotify API: Playlists, Tracks, Search funktionieren
- [ ] slskd Client: Search und Download funktionieren
- [ ] MusicBrainz Client mit Rate Limiting
- [ ] Last.fm Client für Genres/Tags
- [ ] 90+ Unit Tests für alle Clients
- [ ] Mock-basierte Tests mit pytest-httpx
- [ ] Retry-Logik mit Exponential Backoff
- [ ] Dokumentation aller API-Methoden

### 8.7 Checkliste Phase 3

| Task | Effort | Status |
|------|--------|--------|
| Spotify OAuth PKCE | 8h | ☐ |
| Spotify API Methods | 6h | ☐ |
| Spotify Rate Limiting | 3h | ☐ |
| slskd Search | 4h | ☐ |
| slskd Download Management | 4h | ☐ |
| MusicBrainz ISRC Lookup | 4h | ☐ |
| MusicBrainz Search | 3h | ☐ |
| MusicBrainz Rate Limiter | 2h | ☐ |
| Last.fm Client | 4h | ☐ |
| Unit Tests (90+) | 12h | ☐ |
| Integration Tests | 6h | ☐ |
| Documentation | 4h | ☐ |

---

## 9. Phase 4: Application Layer (Woche 10-12)

### 9.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 3 Wochen |
| **Ziel** | Use Cases, Worker System, Caching, Token Management |
| **Ergebnis** | Vollständige Business-Logik-Schicht |
| **Version** | v0.0.4 |

### 9.2 Use Cases

#### 9.2.1 Import Spotify Playlist Use Case

```python
# src/soulspot/application/use_cases/import_spotify_playlist.py

"""
Hey future me - Dieser Use Case orchestriert den kompletten Playlist-Import:
1. Playlist-Metadaten von Spotify holen
2. Playlist Entity erstellen/updaten
3. Alle Tracks durchgehen und importieren
4. Artist/Album Entities erstellen wenn nötig
5. Track-Playlist Association erstellen

Das ist der komplexeste Use Case - er ruft mehrere Repositories und 
den Spotify Client auf. Fehler bei einzelnen Tracks stoppen nicht den ganzen Import.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from ...domain.entities import Playlist, Track, Artist, Album
from ...domain.value_objects import PlaylistId, TrackId, ArtistId, AlbumId
from ...domain.ports import (
    IPlaylistRepository, ITrackRepository, 
    IArtistRepository, IAlbumRepository
)
from ...infrastructure.integrations.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)

@dataclass
class ImportPlaylistRequest:
    """Request für Playlist-Import."""
    spotify_playlist_id: str
    access_token: str
    refresh_token: str

@dataclass
class ImportPlaylistResponse:
    """Response nach Playlist-Import."""
    playlist_id: str
    name: str
    tracks_imported: int
    tracks_failed: int
    new_artists: int
    new_albums: int

class ImportSpotifyPlaylistUseCase:
    """Use Case für Spotify Playlist Import."""
    
    def __init__(
        self,
        playlist_repo: IPlaylistRepository,
        track_repo: ITrackRepository,
        artist_repo: IArtistRepository,
        album_repo: IAlbumRepository,
    ):
        self._playlist_repo = playlist_repo
        self._track_repo = track_repo
        self._artist_repo = artist_repo
        self._album_repo = album_repo
    
    async def execute(self, request: ImportPlaylistRequest) -> ImportPlaylistResponse:
        """Führt Playlist-Import aus."""
        
        tracks_imported = 0
        tracks_failed = 0
        new_artists = 0
        new_albums = 0
        
        async with SpotifyClient() as spotify:
            # Tokens setzen
            spotify.set_tokens(request.access_token, request.refresh_token)
            
            # Playlist-Daten holen
            playlist_data = await spotify.get_playlist(request.spotify_playlist_id)
            
            # Playlist Entity erstellen/updaten
            existing = await self._playlist_repo.get_by_spotify_id(
                request.spotify_playlist_id
            )
            
            if existing:
                playlist = existing
                playlist.name = playlist_data["name"]
            else:
                playlist = Playlist(
                    id=PlaylistId(),
                    name=playlist_data["name"],
                    source="spotify",
                    spotify_id=playlist_data["id"],
                    description=playlist_data.get("description"),
                    cover_url=self._get_cover_url(playlist_data),
                    owner_name=playlist_data["owner"]["display_name"],
                )
                await self._playlist_repo.add(playlist)
            
            # Tracks importieren (paginiert)
            offset = 0
            while True:
                tracks_data = await spotify.get_playlist_tracks(
                    request.spotify_playlist_id,
                    offset=offset,
                    limit=100
                )
                
                for item in tracks_data["items"]:
                    try:
                        track_data = item["track"]
                        if not track_data:  # Kann None sein (gelöschte Tracks)
                            continue
                        
                        # Artist erstellen/holen
                        artist, is_new_artist = await self._get_or_create_artist(
                            track_data["artists"][0]
                        )
                        if is_new_artist:
                            new_artists += 1
                        
                        # Album erstellen/holen
                        album = None
                        if track_data.get("album"):
                            album, is_new_album = await self._get_or_create_album(
                                track_data["album"], artist.id
                            )
                            if is_new_album:
                                new_albums += 1
                        
                        # Track erstellen/holen
                        track = await self._get_or_create_track(
                            track_data, artist.id, album.id if album else None
                        )
                        
                        # Track zu Playlist hinzufügen
                        position = offset + tracks_data["items"].index(item)
                        await self._playlist_repo.add_track(
                            playlist.id, track.id, position
                        )
                        
                        tracks_imported += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to import track: {e}")
                        tracks_failed += 1
                
                # Nächste Seite
                if tracks_data["next"] is None:
                    break
                offset += 100
            
            # Sync Timestamp updaten
            playlist.mark_synced()
            await self._playlist_repo.update(playlist)
        
        return ImportPlaylistResponse(
            playlist_id=playlist.id.value,
            name=playlist.name,
            tracks_imported=tracks_imported,
            tracks_failed=tracks_failed,
            new_artists=new_artists,
            new_albums=new_albums,
        )
    
    async def _get_or_create_artist(
        self, 
        artist_data: dict
    ) -> tuple[Artist, bool]:
        """Holt oder erstellt Artist Entity."""
        
        existing = await self._artist_repo.get_by_spotify_id(artist_data["id"])
        if existing:
            return existing, False
        
        artist = Artist(
            id=ArtistId(),
            name=artist_data["name"],
            spotify_id=artist_data["id"],
        )
        await self._artist_repo.add(artist)
        return artist, True
    
    async def _get_or_create_album(
        self, 
        album_data: dict, 
        artist_id: ArtistId
    ) -> tuple[Album, bool]:
        """Holt oder erstellt Album Entity."""
        
        existing = await self._album_repo.get_by_spotify_id(album_data["id"])
        if existing:
            return existing, False
        
        album = Album(
            id=AlbumId(),
            title=album_data["name"],
            artist_id=artist_id,
            spotify_id=album_data["id"],
            release_year=self._parse_year(album_data.get("release_date")),
            artwork_url=self._get_cover_url(album_data),
            track_count=album_data.get("total_tracks", 0),
        )
        await self._album_repo.add(album)
        return album, True
    
    async def _get_or_create_track(
        self,
        track_data: dict,
        artist_id: ArtistId,
        album_id: Optional[AlbumId]
    ) -> Track:
        """Holt oder erstellt Track Entity."""
        
        spotify_uri = track_data["uri"]
        existing = await self._track_repo.get_by_spotify_uri(spotify_uri)
        if existing:
            return existing
        
        track = Track(
            id=TrackId(),
            title=track_data["name"],
            artist_id=artist_id,
            album_id=album_id,
            spotify_uri=spotify_uri,
            isrc=track_data.get("external_ids", {}).get("isrc"),
            duration_ms=track_data["duration_ms"],
            track_number=track_data.get("track_number"),
            disc_number=track_data.get("disc_number", 1),
            explicit=track_data.get("explicit", False),
        )
        await self._track_repo.add(track)
        return track
    
    @staticmethod
    def _get_cover_url(data: dict) -> Optional[str]:
        """Extrahiert Cover URL aus Spotify Daten."""
        images = data.get("images", [])
        return images[0]["url"] if images else None
    
    @staticmethod
    def _parse_year(release_date: Optional[str]) -> Optional[int]:
        """Parsed Release Year aus Datum-String."""
        if not release_date:
            return None
        try:
            return int(release_date[:4])
        except (ValueError, IndexError):
            return None
```

#### 9.2.2 Search and Download Track Use Case

```python
# src/soulspot/application/use_cases/search_and_download_track.py

"""
Hey future me - Dieser Use Case handelt das Suchen und Downloaden:
1. Track-Info aus DB holen
2. Search Query für slskd bauen (Artist + Title)
3. Beste Ergebnisse filtern (Format, Qualität, Blacklist)
4. Download starten
5. Download Entity erstellen

Die Qualitäts-Filter sind wichtig - wir wollen FLAC > 320kbps MP3 > Rest.
Blacklist verhindert Live-Versionen, Remixes etc.
"""

from dataclasses import dataclass
from typing import Optional
import logging
from rapidfuzz import fuzz

from ...domain.entities import Download, DownloadStatus
from ...domain.value_objects import DownloadId, TrackId
from ...domain.ports import IDownloadRepository, ITrackRepository
from ...infrastructure.integrations.slskd_client import SlskdClient

logger = logging.getLogger(__name__)

@dataclass
class SearchAndDownloadRequest:
    """Request für Track-Download."""
    track_id: str
    priority: int = 0
    min_bitrate: int = 256
    preferred_formats: list[str] = None
    exclusion_keywords: list[str] = None
    
    def __post_init__(self):
        if self.preferred_formats is None:
            self.preferred_formats = ["flac", "mp3", "m4a", "ogg"]
        if self.exclusion_keywords is None:
            self.exclusion_keywords = [
                "live", "remix", "cover", "karaoke", 
                "instrumental", "acoustic", "demo"
            ]

@dataclass
class SearchAndDownloadResponse:
    """Response nach Download-Start."""
    download_id: str
    status: str
    source_user: Optional[str] = None
    source_filename: Optional[str] = None

class SearchAndDownloadTrackUseCase:
    """Use Case für Track-Suche und Download."""
    
    def __init__(
        self,
        track_repo: ITrackRepository,
        download_repo: IDownloadRepository,
        slskd_client: SlskdClient,
    ):
        self._track_repo = track_repo
        self._download_repo = download_repo
        self._slskd = slskd_client
    
    async def execute(
        self, 
        request: SearchAndDownloadRequest
    ) -> SearchAndDownloadResponse:
        """Sucht und startet Download."""
        
        # Track-Daten holen
        track = await self._track_repo.get_by_id(TrackId(request.track_id))
        if not track:
            raise ValueError(f"Track not found: {request.track_id}")
        
        # Bereits heruntergeladen?
        if track.is_downloaded:
            logger.info(f"Track already downloaded: {track.title}")
            existing_download = await self._download_repo.get_completed_for_track(
                track.id
            )
            return SearchAndDownloadResponse(
                download_id=existing_download.id.value if existing_download else "",
                status="already_downloaded"
            )
        
        # Search Query bauen
        artist_name = await self._get_artist_name(track.artist_id)
        query = f"{artist_name} {track.title}"
        
        logger.info(f"Searching for: {query}")
        
        # Suchen
        search_results = await self._slskd.search(query, timeout_seconds=30)
        
        # Beste Ergebnis finden
        best_result = self._find_best_result(
            search_results,
            track.title,
            artist_name,
            request
        )
        
        if not best_result:
            # Download als fehlgeschlagen markieren
            download = Download(
                id=DownloadId(),
                track_id=track.id,
                status=DownloadStatus.FAILED,
                priority=request.priority,
                error_message="No suitable source found"
            )
            await self._download_repo.add(download)
            
            return SearchAndDownloadResponse(
                download_id=download.id.value,
                status="no_source_found"
            )
        
        # Download starten
        username, filename = best_result
        await self._slskd.start_download(username, filename)
        
        # Download Entity erstellen
        download = Download(
            id=DownloadId(),
            track_id=track.id,
            status=DownloadStatus.DOWNLOADING,
            priority=request.priority,
            source_user=username,
            source_filename=filename,
        )
        download.start()
        await self._download_repo.add(download)
        
        logger.info(f"Started download: {filename} from {username}")
        
        return SearchAndDownloadResponse(
            download_id=download.id.value,
            status="downloading",
            source_user=username,
            source_filename=filename,
        )
    
    def _find_best_result(
        self,
        search_results: list[dict],
        track_title: str,
        artist_name: str,
        request: SearchAndDownloadRequest
    ) -> Optional[tuple[str, str]]:
        """Findet bestes Suchergebnis basierend auf Qualitätskriterien."""
        
        scored_results = []
        
        for result in search_results:
            username = result.get("username")
            files = result.get("files", [])
            
            for file_info in files:
                filename = file_info.get("filename", "")
                
                # Filter: Blacklisted Keywords
                if self._contains_exclusion(filename, request.exclusion_keywords):
                    continue
                
                # Filter: Format
                extension = filename.lower().split(".")[-1]
                if extension not in request.preferred_formats:
                    continue
                
                # Filter: Bitrate (wenn verfügbar)
                bitrate = file_info.get("bitRate", 0)
                if bitrate > 0 and bitrate < request.min_bitrate:
                    continue
                
                # Score berechnen
                score = self._calculate_score(
                    filename, track_title, artist_name,
                    extension, bitrate
                )
                
                scored_results.append((score, username, filename))
        
        if not scored_results:
            return None
        
        # Beste Ergebnis (höchster Score)
        scored_results.sort(key=lambda x: x[0], reverse=True)
        _, best_user, best_file = scored_results[0]
        
        return best_user, best_file
    
    def _calculate_score(
        self,
        filename: str,
        track_title: str,
        artist_name: str,
        extension: str,
        bitrate: int
    ) -> float:
        """Berechnet Quality Score für ein Suchergebnis."""
        
        score = 0.0
        
        # Fuzzy Match Score (50% Gewichtung)
        expected = f"{artist_name} {track_title}"
        fuzzy_score = fuzz.token_set_ratio(expected.lower(), filename.lower())
        score += fuzzy_score * 0.5
        
        # Format Score (40% Gewichtung)
        format_scores = {"flac": 100, "wav": 90, "mp3": 70, "m4a": 60, "ogg": 50}
        format_score = format_scores.get(extension, 30)
        score += format_score * 0.4
        
        # Bitrate Bonus (10% Gewichtung)
        if bitrate >= 320:
            score += 10
        elif bitrate >= 256:
            score += 5
        
        return score
    
    @staticmethod
    def _contains_exclusion(filename: str, keywords: list[str]) -> bool:
        """Prüft ob Filename blacklisted Keywords enthält."""
        filename_lower = filename.lower()
        return any(kw.lower() in filename_lower for kw in keywords)
    
    async def _get_artist_name(self, artist_id) -> str:
        """Holt Artist-Namen (helper)."""
        # Implementation abhängig von Artist Repository
        return "Unknown Artist"  # Placeholder
```

### 9.3 Job Queue System

```python
# src/soulspot/application/workers/job_queue.py

"""
Hey future me - Das Job Queue System ist das Herzstück für async Verarbeitung.
Jobs haben Prioritäten (höher = wichtiger) und Status-Tracking.
Die Queue ist in-memory mit asyncio.PriorityQueue.
Worker holen Jobs und führen registered Handler aus.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass(order=True)
class Job:
    """Job-Definition mit Priorität."""
    priority: int = field(compare=True)
    id: str = field(compare=False)
    job_type: str = field(compare=False)
    payload: dict = field(compare=False, default_factory=dict)
    status: JobStatus = field(compare=False, default=JobStatus.PENDING)
    created_at: datetime = field(compare=False, default_factory=datetime.utcnow)
    started_at: Optional[datetime] = field(compare=False, default=None)
    completed_at: Optional[datetime] = field(compare=False, default=None)
    error_message: Optional[str] = field(compare=False, default=None)
    retry_count: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)
    
    def __post_init__(self):
        # Negative Priorität für PriorityQueue (höher = wichtiger)
        self.priority = -self.priority
    
    @property
    def actual_priority(self) -> int:
        return -self.priority
    
    @property
    def should_retry(self) -> bool:
        return self.retry_count < self.max_retries

JobHandler = Callable[[Job], Awaitable[Any]]

class JobQueue:
    """Async Job Queue mit Priority Support."""
    
    def __init__(self):
        self._queue: asyncio.PriorityQueue[Job] = asyncio.PriorityQueue()
        self._handlers: dict[str, JobHandler] = {}
        self._running = False
        self._paused = False
        self._workers: list[asyncio.Task] = []
        self._max_concurrent = 3
        self._active_jobs: dict[str, Job] = {}
    
    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        """Registriert Handler für Job-Typ."""
        self._handlers[job_type] = handler
        logger.info(f"Registered handler for: {job_type}")
    
    async def enqueue(self, job: Job) -> None:
        """Fügt Job zur Queue hinzu."""
        await self._queue.put(job)
        logger.info(f"Enqueued job {job.id} with priority {job.actual_priority}")
    
    async def start(self, num_workers: int = 3) -> None:
        """Startet Worker-Tasks."""
        self._running = True
        self._max_concurrent = num_workers
        
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)
        
        logger.info(f"Started {num_workers} workers")
    
    async def stop(self) -> None:
        """Stoppt alle Worker gracefully."""
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        logger.info("Stopped all workers")
    
    def pause(self) -> None:
        """Pausiert Queue-Verarbeitung."""
        self._paused = True
        logger.info("Queue paused")
    
    def resume(self) -> None:
        """Setzt Queue-Verarbeitung fort."""
        self._paused = False
        logger.info("Queue resumed")
    
    @property
    def is_paused(self) -> bool:
        return self._paused
    
    def set_max_concurrent_jobs(self, count: int) -> None:
        """Setzt maximale parallele Jobs."""
        self._max_concurrent = count
    
    async def _worker_loop(self, worker_id: str) -> None:
        """Worker-Loop der Jobs verarbeitet."""
        
        while self._running:
            try:
                # Pause respektieren
                while self._paused:
                    await asyncio.sleep(0.5)
                    if not self._running:
                        return
                
                # Concurrent Limit prüfen
                while len(self._active_jobs) >= self._max_concurrent:
                    await asyncio.sleep(0.1)
                    if not self._running:
                        return
                
                # Job holen (mit Timeout um regelmäßig Status zu prüfen)
                try:
                    job = await asyncio.wait_for(
                        self._queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Job verarbeiten
                await self._process_job(worker_id, job)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Worker {worker_id} error: {e}")
    
    async def _process_job(self, worker_id: str, job: Job) -> None:
        """Verarbeitet einzelnen Job."""
        
        handler = self._handlers.get(job.job_type)
        if not handler:
            logger.error(f"No handler for job type: {job.job_type}")
            return
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        self._active_jobs[job.id] = job
        
        logger.info(f"[{worker_id}] Processing job {job.id} ({job.job_type})")
        
        try:
            await handler(job)
            
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            
            logger.info(f"[{worker_id}] Completed job {job.id}")
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.retry_count += 1
            
            logger.error(f"[{worker_id}] Job {job.id} failed: {e}")
            
            # Retry wenn möglich
            if job.should_retry:
                # Exponential Backoff
                delay = 2 ** job.retry_count
                logger.info(f"Retrying job {job.id} in {delay}s")
                await asyncio.sleep(delay)
                
                job.status = JobStatus.PENDING
                await self.enqueue(job)
        
        finally:
            self._active_jobs.pop(job.id, None)
    
    def get_status(self) -> dict[str, Any]:
        """Gibt Queue-Status zurück."""
        return {
            "paused": self._paused,
            "max_concurrent": self._max_concurrent,
            "queued_count": self._queue.qsize(),
            "active_count": len(self._active_jobs),
            "active_jobs": list(self._active_jobs.keys()),
        }
```

### 9.4 Caching Layer

```python
# src/soulspot/application/services/cache.py

"""
Hey future me - Der Cache ist LRU-basiert mit TTL.
SpotifyCache speichert API Responses (teuer wegen Rate Limits).
MusicBrainzCache speichert Metadaten (Rate Limit ist strenger).
TrackFileCache speichert File-Paths (schnelle Existenz-Checks).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Any, Generic, TypeVar
from collections import OrderedDict
import asyncio
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class CacheEntry(Generic[T]):
    """Cache-Eintrag mit TTL."""
    value: T
    expires_at: datetime
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

class LRUCache(Generic[T]):
    """LRU Cache mit TTL Support."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()
        
        # Metrics
        self._hits = 0
        self._misses = 0
    
    async def get(self, key: str) -> Optional[T]:
        """Holt Wert aus Cache."""
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value
    
    async def set(
        self, 
        key: str, 
        value: T, 
        ttl: Optional[int] = None
    ) -> None:
        """Speichert Wert im Cache."""
        async with self._lock:
            ttl = ttl or self._default_ttl
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
            self._cache.move_to_end(key)
            
            # Eviction wenn über max_size
            while len(self._cache) > self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
    
    async def delete(self, key: str) -> None:
        """Löscht Eintrag aus Cache."""
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self) -> None:
        """Leert gesamten Cache."""
        async with self._lock:
            self._cache.clear()
    
    def get_metrics(self) -> dict[str, Any]:
        """Gibt Cache-Metriken zurück."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate * 100, 2),
        }

class SpotifyCache:
    """Spezialisierter Cache für Spotify API Responses."""
    
    def __init__(self):
        self._playlists = LRUCache[dict](max_size=100, default_ttl=300)  # 5 min
        self._tracks = LRUCache[dict](max_size=1000, default_ttl=3600)  # 1 hour
        self._search = LRUCache[dict](max_size=200, default_ttl=600)  # 10 min
    
    async def get_playlist(self, playlist_id: str) -> Optional[dict]:
        return await self._playlists.get(f"playlist:{playlist_id}")
    
    async def set_playlist(self, playlist_id: str, data: dict) -> None:
        await self._playlists.set(f"playlist:{playlist_id}", data)
    
    async def get_track(self, track_id: str) -> Optional[dict]:
        return await self._tracks.get(f"track:{track_id}")
    
    async def set_track(self, track_id: str, data: dict) -> None:
        await self._tracks.set(f"track:{track_id}", data)
```

### 9.5 Token Manager

```python
# src/soulspot/application/services/token_manager.py

"""
Hey future me - Der Token Manager speichert und refresht OAuth Tokens.
Tokens haben Expiration - wir refreshen proaktiv 5 Minuten vorher.
Session-basiert: Jeder User hat eigene Tokens.
In Production sollte das in Redis/DB statt Memory sein.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

@dataclass
class TokenData:
    """OAuth Token Daten."""
    access_token: str
    refresh_token: str
    expires_at: datetime
    
    @property
    def is_expired(self) -> bool:
        # 5 Minuten Puffer
        return datetime.utcnow() >= self.expires_at - timedelta(minutes=5)

class TokenManager:
    """Verwaltet OAuth Tokens für User Sessions."""
    
    def __init__(self):
        self._tokens: dict[str, TokenData] = {}
        self._lock = asyncio.Lock()
    
    async def store_tokens(
        self,
        session_id: str,
        access_token: str,
        refresh_token: str,
        expires_in: int
    ) -> None:
        """Speichert Tokens für Session."""
        async with self._lock:
            self._tokens[session_id] = TokenData(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=datetime.utcnow() + timedelta(seconds=expires_in)
            )
        logger.info(f"Stored tokens for session {session_id[:8]}...")
    
    async def get_tokens(self, session_id: str) -> Optional[TokenData]:
        """Holt Tokens für Session."""
        return self._tokens.get(session_id)
    
    async def get_valid_access_token(
        self, 
        session_id: str,
        refresh_callback
    ) -> Optional[str]:
        """Holt gültigen Access Token (refresht wenn nötig)."""
        
        token_data = self._tokens.get(session_id)
        if not token_data:
            return None
        
        if token_data.is_expired:
            # Token refreshen
            try:
                new_tokens = await refresh_callback(token_data.refresh_token)
                await self.store_tokens(
                    session_id,
                    new_tokens["access_token"],
                    new_tokens.get("refresh_token", token_data.refresh_token),
                    new_tokens["expires_in"]
                )
                token_data = self._tokens[session_id]
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                return None
        
        return token_data.access_token
    
    async def delete_tokens(self, session_id: str) -> None:
        """Löscht Tokens für Session (Logout)."""
        async with self._lock:
            self._tokens.pop(session_id, None)
```

### 9.6 Akzeptanzkriterien Phase 4

- [ ] Import Spotify Playlist Use Case funktioniert
- [ ] Search and Download Use Case funktioniert
- [ ] Enrich Metadata Use Case funktioniert
- [ ] Job Queue mit Priority Support
- [ ] Worker System mit Retry-Logik
- [ ] LRU Cache mit TTL implementiert
- [ ] Token Manager mit Auto-Refresh
- [ ] Session Store implementiert
- [ ] 50+ Unit Tests für Application Layer
- [ ] Integration Tests für Use Cases

### 9.7 Checkliste Phase 4

| Task | Effort | Status |
|------|--------|--------|
| Import Playlist Use Case | 8h | ☐ |
| Search & Download Use Case | 8h | ☐ |
| Enrich Metadata Use Case | 6h | ☐ |
| Job Queue System | 6h | ☐ |
| Download Worker | 4h | ☐ |
| Metadata Worker | 4h | ☐ |
| Playlist Sync Worker | 4h | ☐ |
| LRU Cache | 4h | ☐ |
| Spotify Cache | 2h | ☐ |
| MusicBrainz Cache | 2h | ☐ |
| Token Manager | 4h | ☐ |
| Session Store | 3h | ☐ |
| Unit Tests (50+) | 10h | ☐ |
| Integration Tests | 6h | ☐ |
| Documentation | 4h | ☐ |

---

## 10. Phase 5: Web UI & API Integration (Woche 13-16)

### 10.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 4 Wochen |
| **Ziel** | Vollständige Web-Oberfläche und REST API |
| **Ergebnis** | v0.1.0 Alpha Release |
| **Version** | v0.1.0 |

### 10.2 REST API Endpoints

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       REST API ENDPOINTS ÜBERSICHT                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  /api/auth                                                                 │
│  ├── GET  /login          → Redirect zu Spotify OAuth                     │
│  ├── GET  /callback       → OAuth Callback Handler                        │
│  ├── POST /logout         → Session beenden                               │
│  └── GET  /status         → Auth Status prüfen                            │
│                                                                             │
│  /api/playlists                                                            │
│  ├── GET  /               → Alle Playlists                                │
│  ├── POST /               → Playlist importieren                          │
│  ├── GET  /{id}           → Playlist Details                              │
│  ├── POST /{id}/sync      → Playlist synchronisieren                      │
│  ├── GET  /{id}/tracks    → Playlist Tracks                               │
│  └── GET  /{id}/missing   → Fehlende Tracks                               │
│                                                                             │
│  /api/downloads                                                            │
│  ├── GET  /               → Download Queue                                │
│  ├── POST /               → Download starten                              │
│  ├── POST /batch          → Batch Downloads                               │
│  ├── GET  /status         → Queue Status                                  │
│  ├── POST /pause          → Queue pausieren                               │
│  ├── POST /resume         → Queue fortsetzen                              │
│  ├── GET  /{id}           → Download Details                              │
│  ├── DELETE /{id}         → Download abbrechen                            │
│  ├── POST /{id}/pause     → Einzeln pausieren                             │
│  └── POST /{id}/resume    → Einzeln fortsetzen                            │
│                                                                             │
│  /api/tracks                                                               │
│  ├── GET  /               → Tracks suchen/listen                          │
│  ├── GET  /{id}           → Track Details                                 │
│  ├── PATCH /{id}          → Track aktualisieren                           │
│  └── GET  /{id}/metadata  → Metadaten anreichern                          │
│                                                                             │
│  /api/library                                                              │
│  ├── POST /scan           → Library Scan starten                          │
│  ├── GET  /scan/{id}      → Scan Status                                   │
│  ├── GET  /duplicates     → Duplikate                                     │
│  ├── GET  /broken-files   → Kaputte Dateien                               │
│  └── GET  /stats          → Library Statistiken                           │
│                                                                             │
│  /api/settings                                                             │
│  ├── GET  /               → Aktuelle Settings                             │
│  ├── POST /               → Settings aktualisieren                        │
│  ├── POST /reset          → Auf Defaults zurücksetzen                     │
│  └── GET  /defaults       → Default Settings                              │
│                                                                             │
│  /health                                                                   │
│  ├── GET  /live           → Liveness Check                                │
│  └── GET  /ready          → Readiness Check                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Web UI Pages

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WEB UI PAGES                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SEITE              ROUTE           FUNKTIONEN                             │
│  ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│  Dashboard          /               • Übersicht aller Statistiken          │
│                                     • Aktive Downloads                      │
│                                     • Zuletzt hinzugefügte Tracks          │
│                                     • Schnellzugriff Aktionen               │
│                                                                             │
│  Playlists          /playlists      • Liste aller Playlists                │
│                                     • Import-Button                         │
│                                     • Sync-Status je Playlist              │
│                                     • Filter und Suche                     │
│                                                                             │
│  Playlist Detail    /playlists/{id} • Track-Liste mit Status               │
│                                     • Download-All Button                   │
│                                     • Missing Tracks Anzeige               │
│                                     • Export Funktionen                    │
│                                                                             │
│  Downloads          /downloads      • Download Queue                        │
│                                     • Progress Bars                         │
│                                     • Pause/Resume Controls                │
│                                     • Filter nach Status                   │
│                                                                             │
│  Search             /search         • Spotify Suche                         │
│                                     • Quick Download                        │
│                                     • Ergebnis-Preview                     │
│                                                                             │
│  Library            /library        • Browse Artists/Albums                │
│                                     • Track-Liste                          │
│                                     • Metadata Editor                      │
│                                                                             │
│  Settings           /settings       • API Keys Konfiguration               │
│                                     • Download Präferenzen                 │
│                                     • Pfade Einstellungen                  │
│                                     • Theme Auswahl                        │
│                                                                             │
│  Login              /auth/login     • Spotify Connect Button               │
│                                     • OAuth Flow Start                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.4 HTMX Integration Patterns

```html
<!-- Beispiel: Download Queue mit Echtzeit-Updates -->
<div id="download-queue" 
     hx-get="/api/ui/downloads/partial"
     hx-trigger="load, every 2s"
     hx-swap="innerHTML">
    <!-- Queue Items werden hier geladen -->
</div>

<!-- Beispiel: Playlist Import Form -->
<form hx-post="/api/playlists"
      hx-target="#playlist-list"
      hx-swap="afterbegin"
      hx-indicator="#import-spinner">
    <input type="text" name="spotify_url" 
           placeholder="Spotify Playlist URL">
    <button type="submit">
        <span id="import-spinner" class="htmx-indicator">
            Importiere...
        </span>
        Importieren
    </button>
</form>

<!-- Beispiel: Download Button mit Optimistic UI -->
<button hx-post="/api/downloads"
        hx-vals='{"track_id": "abc123"}'
        hx-swap="outerHTML"
        hx-target="this"
        class="btn-download">
    <svg><!-- Download Icon --></svg>
    Download
</button>
```

### 10.5 Server-Sent Events (SSE)

```python
# src/soulspot/api/routers/sse.py

"""
Hey future me - SSE für Echtzeit-Updates ohne Polling.
EventSource im Browser verbindet sich einmal und bleibt offen.
Wir pushen Updates wenn Downloads sich ändern.
Heartbeat alle 30s verhindert Connection Timeout.
"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
from typing import AsyncGenerator

router = APIRouter()

async def event_generator(request: Request) -> AsyncGenerator[str, None]:
    """Generiert SSE Events."""
    
    # Event Format: "event: type\ndata: json\n\n"
    
    # Connected Event
    yield f"event: connected\ndata: {json.dumps({'status': 'ok'})}\n\n"
    
    last_heartbeat = asyncio.get_event_loop().time()
    
    while True:
        # Client Disconnect Check
        if await request.is_disconnected():
            break
        
        # Download Updates (wenn vorhanden)
        # In echtem Code: Updates aus Queue/Event Bus holen
        downloads_update = await get_download_updates()
        if downloads_update:
            yield f"event: downloads_update\ndata: {json.dumps(downloads_update)}\n\n"
        
        # Heartbeat alle 30 Sekunden
        now = asyncio.get_event_loop().time()
        if now - last_heartbeat >= 30:
            yield f"event: heartbeat\ndata: {json.dumps({'ts': now})}\n\n"
            last_heartbeat = now
        
        await asyncio.sleep(1)

@router.get("/stream")
async def sse_stream(request: Request):
    """SSE Endpoint für Echtzeit-Updates."""
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

### 10.6 Jinja2 Templates mit Tailwind CSS

```html
<!-- src/soulspot/templates/base.html -->
<!DOCTYPE html>
<html lang="de" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}SoulSpot{% endblock %}</title>
    
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    
    <!-- Custom Styles -->
    <style>
        /* Dark Mode Default */
        :root {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --text-primary: #eaeaea;
            --accent: #0ea5e9;
        }
        
        body {
            background-color: var(--bg-primary);
            color: var(--text-primary);
        }
        
        /* HTMX Indicator */
        .htmx-indicator {
            display: none;
        }
        .htmx-request .htmx-indicator {
            display: inline;
        }
    </style>
</head>
<body class="h-full">
    <!-- Navigation -->
    <nav class="bg-slate-900 border-b border-slate-800">
        <div class="max-w-7xl mx-auto px-4">
            <div class="flex items-center justify-between h-16">
                <a href="/" class="text-xl font-bold text-white">
                    🎵 SoulSpot
                </a>
                <div class="flex space-x-4">
                    <a href="/playlists" class="text-gray-300 hover:text-white">
                        Playlists
                    </a>
                    <a href="/downloads" class="text-gray-300 hover:text-white">
                        Downloads
                    </a>
                    <a href="/library" class="text-gray-300 hover:text-white">
                        Library
                    </a>
                    <a href="/settings" class="text-gray-300 hover:text-white">
                        Settings
                    </a>
                </div>
            </div>
        </div>
    </nav>
    
    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 py-8">
        {% block content %}{% endblock %}
    </main>
    
    <!-- Toast Notifications -->
    <div id="toast-container" 
         class="fixed bottom-4 right-4 space-y-2"
         hx-swap-oob="true">
    </div>
    
    {% block scripts %}{% endblock %}
</body>
</html>
```

### 10.7 Dashboard Page

```html
<!-- src/soulspot/templates/dashboard.html -->
{% extends "base.html" %}

{% block title %}Dashboard - SoulSpot{% endblock %}

{% block content %}
<div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
        <h1 class="text-3xl font-bold">Dashboard</h1>
        {% if not is_authenticated %}
        <a href="/auth/login" 
           class="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
            Mit Spotify verbinden
        </a>
        {% endif %}
    </div>
    
    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div class="bg-slate-800 rounded-lg p-4">
            <p class="text-gray-400 text-sm">Playlists</p>
            <p class="text-2xl font-bold">{{ stats.playlists_count }}</p>
        </div>
        <div class="bg-slate-800 rounded-lg p-4">
            <p class="text-gray-400 text-sm">Tracks</p>
            <p class="text-2xl font-bold">{{ stats.tracks_count }}</p>
        </div>
        <div class="bg-slate-800 rounded-lg p-4">
            <p class="text-gray-400 text-sm">Heruntergeladen</p>
            <p class="text-2xl font-bold">{{ stats.downloaded_count }}</p>
        </div>
        <div class="bg-slate-800 rounded-lg p-4">
            <p class="text-gray-400 text-sm">In Queue</p>
            <p class="text-2xl font-bold">{{ stats.queued_count }}</p>
        </div>
    </div>
    
    <!-- Active Downloads -->
    <div class="bg-slate-800 rounded-lg p-6">
        <h2 class="text-xl font-semibold mb-4">Aktive Downloads</h2>
        <div id="active-downloads"
             hx-get="/api/ui/downloads/active"
             hx-trigger="load, every 2s"
             hx-swap="innerHTML">
            <p class="text-gray-400">Lade...</p>
        </div>
    </div>
    
    <!-- Recent Tracks -->
    <div class="bg-slate-800 rounded-lg p-6">
        <h2 class="text-xl font-semibold mb-4">Zuletzt hinzugefügt</h2>
        <div class="space-y-2">
            {% for track in recent_tracks %}
            <div class="flex items-center justify-between py-2 border-b border-slate-700">
                <div>
                    <p class="font-medium">{{ track.title }}</p>
                    <p class="text-sm text-gray-400">{{ track.artist_name }}</p>
                </div>
                <span class="text-sm text-gray-500">
                    {{ track.created_at | timeago }}
                </span>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
```

### 10.8 Akzeptanzkriterien Phase 5

- [ ] Alle REST API Endpoints implementiert (50+)
- [ ] Web UI mit allen Pages (9 Seiten)
- [ ] HTMX Integration für dynamische Updates
- [ ] SSE für Echtzeit-Notifications
- [ ] OAuth Login Flow funktioniert
- [ ] Download Queue UI mit Progress
- [ ] Playlist Import und Sync
- [ ] Responsive Design (Mobile-First)
- [ ] Dark Mode als Default
- [ ] 7+ Integration Tests für API
- [ ] Version v0.1.0 Release Ready

### 10.9 Checkliste Phase 5

| Task | Effort | Status |
|------|--------|--------|
| Auth Router | 4h | ☐ |
| Playlists Router | 6h | ☐ |
| Downloads Router | 6h | ☐ |
| Tracks Router | 4h | ☐ |
| Library Router | 4h | ☐ |
| Settings Router | 3h | ☐ |
| UI Router | 6h | ☐ |
| SSE Implementation | 4h | ☐ |
| Base Template | 4h | ☐ |
| Dashboard Page | 4h | ☐ |
| Playlists Pages | 6h | ☐ |
| Downloads Page | 4h | ☐ |
| Search Page | 4h | ☐ |
| Library Pages | 6h | ☐ |
| Settings Page | 4h | ☐ |
| Integration Tests | 8h | ☐ |
| v0.1.0 Release | 4h | ☐ |

---

## 11. Phase 6: Automation & Watchlists (Woche 17-20)

### 11.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 4 Wochen |
| **Ziel** | Automatische Downloads, Artist Watchlists, Quality Upgrades |
| **Ergebnis** | Vollständige Automatisierung |
| **Version** | v0.2.0 |

### 11.2 Features

#### Artist Watchlist System
- Künstler zur Beobachtung hinzufügen
- Automatische Prüfung auf neue Releases (konfigurierbar: 1h - 24h)
- Auto-Download neuer Alben/Singles
- Benachrichtigungen bei neuen Releases
- Quality Profile pro Artist

#### Discography Completion
- Vergleich lokale Bibliothek vs. Spotify Discography
- Fehlende Alben identifizieren
- Completeness Percentage pro Artist
- Bulk-Download fehlender Alben

#### Quality Upgrade Detection
- Tracks mit niedriger Qualität identifizieren (< 256kbps)
- Bessere Versionen auf Soulseek suchen
- Automatisches Upgrade wenn FLAC/320kbps verfügbar
- Improvement Score Berechnung

#### Filter & Automation Rules
- Whitelist/Blacklist nach Keywords, Users, Formaten
- Regex-basierte Filter
- Automation Rules: Trigger → Action
- Triggers: new_release, missing_album, quality_upgrade
- Actions: search_and_download, notify_only, add_to_queue

### 11.3 Neue Datenbank-Tabellen

| Tabelle | Felder | Zweck |
|---------|--------|-------|
| artist_watchlists | id, artist_id, status, check_frequency, last_checked, auto_download | Watchlist Einträge |
| filter_rules | id, name, type, pattern, target, priority, enabled | Filter Regeln |
| automation_rules | id, name, trigger, action, config, enabled | Automation Regeln |
| quality_upgrade_candidates | id, track_id, current_quality, target_quality, improvement_score | Upgrade Kandidaten |

### 11.4 Background Workers

| Worker | Intervall | Funktion |
|--------|-----------|----------|
| WatchlistWorker | 1h | Prüft Watchlists auf neue Releases |
| DiscographyWorker | 24h | Scannt Library auf fehlende Alben |
| QualityUpgradeWorker | 24h | Identifiziert Upgrade-Möglichkeiten |

### 11.5 API Endpoints (26 neue)

- `/api/automation/watchlist/*` - Watchlist CRUD (5 Endpoints)
- `/api/automation/discography/*` - Discography Checks (2 Endpoints)
- `/api/automation/quality-upgrades/*` - Quality Upgrades (2 Endpoints)
- `/api/automation/filters/*` - Filter Management (8 Endpoints)
- `/api/automation/rules/*` - Automation Rules (7 Endpoints)
- `/api/automation/workers/*` - Worker Controls (2 Endpoints)

### 11.6 Akzeptanzkriterien Phase 6

- [ ] Artist Watchlist vollständig implementiert
- [ ] Discography Completion Check funktioniert
- [ ] Quality Upgrade Detection implementiert
- [ ] Filter System mit Regex Support
- [ ] Automation Rules Engine
- [ ] Background Workers mit Start/Stop
- [ ] 26 neue API Endpoints
- [ ] Notification System (Log-basiert)
- [ ] Tests für alle neuen Features

---

## 12. Phase 7: Performance & Scalability (Woche 21-23)

### 12.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 3 Wochen |
| **Ziel** | Optimierung für große Libraries (100k+ Tracks) |
| **Ergebnis** | 2-50x Performance-Verbesserung |
| **Version** | v0.3.0 |

### 12.2 Optimierungen

#### Query Optimization
- Eager Loading mit `selectinload()` (N+1 Prevention)
- Batch Operations für Bulk Inserts/Updates
- Composite Indexes für häufige Queries

#### Database Indexes (11 neue)
| Index | Tabelle | Spalten |
|-------|---------|---------|
| ix_tracks_album_track_number | tracks | album_id, track_number |
| ix_downloads_status_priority | downloads | status, priority |
| ix_tracks_is_broken_updated | tracks | is_broken, updated_at |
| ix_artists_spotify_id | artists | spotify_id |
| ix_tracks_file_path | tracks | file_path |
| ... | ... | ... |

#### Connection Pool Tuning
- Pool Size: 5 (Dev) / 20 (Prod)
- Pool Timeout: 30s
- Pool Recycle: 1800s
- Pre-Ping: True

#### Batch Processing
- Generic `BatchProcessor` Framework
- `SpotifyBatchProcessor` für API Calls (50 Items/Request)
- Bis zu 50x weniger API Calls

#### LRU Cache mit Metrics
- Cache Hit Rate Tracking
- Automatic Eviction
- Cache Warming für Hot Paths
- 70%+ Hit Rate erreichbar

### 12.3 Performance Impact

| Operation | Vorher | Nachher | Verbesserung |
|-----------|--------|---------|--------------|
| List Playlists | 1s | 200ms | 5x |
| Bulk Insert (100 Tracks) | 5s | 100ms | 50x |
| Indexed Queries | 500ms | 50ms | 10x |
| Cache Hits | 100ms | <1ms | 100x |

---

## 13. Phase 8: Security Hardening (Woche 24-26)

### 13.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 3 Wochen |
| **Ziel** | OWASP-konforme Sicherheit |
| **Ergebnis** | Production-ready Security |
| **Version** | v0.4.0 |

### 13.2 Security Features

#### CSRF Protection
- Double Submit Cookie Pattern
- Token in Forms und Headers
- Automatische Validierung in FastAPI Middleware

#### Rate Limiting
- Per-IP Limits: 100 req/min (API), 20 req/min (Auth)
- Slowdown statt Block
- Redis-basiert (optional)

#### Security Headers
```python
# Middleware für Security Headers
headers = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'; ...",
    "Strict-Transport-Security": "max-age=31536000",
}
```

#### Input Validation
- Pydantic Validation auf allen Endpoints
- SQL Injection Prevention (SQLAlchemy ORM)
- XSS Prevention (Jinja2 Auto-Escaping)

#### Token Encryption
- Fernet Encryption für gespeicherte Tokens
- Key Rotation Support
- Secure Key Storage via Environment

#### Audit Logging
- Login/Logout Events
- Admin Actions
- Security-relevante Änderungen
- Structured JSON Logs

### 13.3 Akzeptanzkriterien Phase 8

- [ ] CSRF Protection implementiert
- [ ] Rate Limiting aktiv
- [ ] Alle Security Headers gesetzt
- [ ] Input Validation vollständig
- [ ] Tokens verschlüsselt
- [ ] Audit Logging aktiv
- [ ] Security Scan bestanden (Bandit, CodeQL)

---

## 14. Phase 9: Advanced Features (Woche 27-32)

### 14.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 6 Wochen |
| **Ziel** | Premium Features für Power User |
| **Ergebnis** | Feature-Complete Version |
| **Version** | v0.5.0 - v0.8.0 |

### 14.2 Feature Roadmap

#### v0.5.0 - Post-Processing Pipeline (2 Wochen)
- Artwork Download (Multi-Source, Multi-Resolution)
- Lyrics Integration (LRClib, Genius, Musixmatch)
- ID3v2.4 Tagging (alle Standard-Felder)
- Template-basierte Umbenennung
- Auto-Move zu finaler Bibliothek

#### v0.6.0 - Library Management (2 Wochen)
- Full Library Scanner mit Progress
- SHA256-basierte Duplikat-Erkennung
- Broken File Detection (Audio Validation)
- Album Completeness Check
- Auto Re-Download für kaputte Dateien

#### v0.7.0 - Advanced Search (1 Woche)
- Fuzzy Matching (rapidfuzz, 80% Threshold)
- Quality Filters (Bitrate, Format)
- Exclusion Keywords (Live, Remix, etc.)
- Smart Scoring Algorithmus

#### v0.8.0 - UI Enhancements (1 Woche)
- PWA Support (Offline, Installable)
- Native Browser Notifications
- Mobile Gestures (Swipe, Pull-to-Refresh)
- Glassmorphism Design System
- 60fps Animations

### 14.3 Akzeptanzkriterien Phase 9

- [ ] Post-Processing Pipeline vollständig
- [ ] Library Scanner mit allen Features
- [ ] Advanced Search implementiert
- [ ] PWA funktionsfähig
- [ ] UI auf Master-Class Niveau
- [ ] 90%+ der geplanten Features implementiert

---

## 15. Phase 10: Production Readiness (Woche 33-36)

### 15.1 Übersicht

| Attribut | Wert |
|----------|------|
| **Dauer** | 4 Wochen |
| **Ziel** | Stabiler v1.0.0 Release |
| **Ergebnis** | Production-Ready Application |
| **Version** | v1.0.0 |

### 15.2 Release Checklist

#### Code Quality
- [ ] 500+ Tests (Unit + Integration + E2E)
- [ ] Test Coverage >80%
- [ ] Zero Ruff Violations
- [ ] Zero Mypy Errors
- [ ] Zero Bandit High Findings
- [ ] CodeQL Clean

#### Documentation
- [ ] README aktuell und vollständig
- [ ] API Documentation (OpenAPI)
- [ ] User Guide komplett
- [ ] Developer Guide
- [ ] Architecture Documentation
- [ ] CHANGELOG vollständig

#### Deployment
- [ ] Docker Image optimiert (<500MB)
- [ ] docker-compose.yml production-ready
- [ ] Environment Variables dokumentiert
- [ ] Health Checks funktionieren
- [ ] Graceful Shutdown implementiert

#### Monitoring
- [ ] Structured Logging
- [ ] Health Endpoints
- [ ] Error Tracking Setup
- [ ] Performance Baselines dokumentiert

### 15.3 Release Process

1. **Feature Freeze** - Keine neuen Features
2. **Bug Bash** - Intensive Testphase
3. **Performance Testing** - Load Tests
4. **Security Audit** - Finale Prüfung
5. **Documentation Review** - Alle Docs aktuell
6. **Release Candidate** - RC1, RC2 Testing
7. **Final Release** - v1.0.0 Tag + GitHub Release

---

## 16. Langfristige Vision (v2.0/v3.0)

### 16.1 v2.0 - Plugin System (Q2 2026)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         v2.0 PLUGIN ARCHITEKTUR                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     SOULSPOT CORE                                    │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │                   Plugin Manager                               │  │   │
│  │  │  • Plugin Discovery (File System / Registry)                  │  │   │
│  │  │  • Plugin Lifecycle (Load / Unload / Reload)                  │  │   │
│  │  │  • Event Bus (Publish / Subscribe)                            │  │   │
│  │  │  • Hook System (Pre / Post Hooks)                             │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│          ┌───────────────────┼───────────────────┐                         │
│          ▼                   ▼                   ▼                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                 │
│   │ Source      │     │ Metadata    │     │ Integration │                 │
│   │ Plugins     │     │ Plugins     │     │ Plugins     │                 │
│   │             │     │             │     │             │                 │
│   │ • Soulseek  │     │ • MusicBrainz│    │ • Jellyfin  │                 │
│   │ • YouTube   │     │ • Discogs   │     │ • Plex      │                 │
│   │ • Bandcamp  │     │ • Beatport  │     │ • Navidrome │                 │
│   │ • SoundCloud│     │ • Tidal     │     │ • Webhooks  │                 │
│   └─────────────┘     └─────────────┘     └─────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 16.2 v3.0 - Modular Architecture (Q4 2026)

- Microservices-Ansatz (optional)
- GraphQL API
- Real-time Sync (WebSockets)
- Multi-User Support
- Cloud Deployment Support

---

## 17. Risiken und Mitigationsstrategien

### 17.1 Technische Risiken

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| **API Rate Limits** | HOCH | MITTEL | Caching, Exponential Backoff, Queue |
| **Database Performance** | MITTEL | HOCH | Indexing, Connection Pool, Batch Ops |
| **External API Changes** | MITTEL | HOCH | Versioned Clients, Integration Tests |
| **Data Corruption** | NIEDRIG | KRITISCH | Checksums, Backups, Atomic Ops |
| **Memory Leaks** | NIEDRIG | MITTEL | Profiling, Resource Cleanup |

### 17.2 Projekt-Risiken

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| **Scope Creep** | HOCH | MITTEL | Klare Phase-Definitionen, MVP Focus |
| **Technical Debt** | MITTEL | MITTEL | Regelmäßiges Refactoring, Code Reviews |
| **Knowledge Loss** | MITTEL | HOCH | Dokumentation, Future-Self Kommentare |

### 17.3 Externe Risiken

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| **Spotify API Änderungen** | MITTEL | HOCH | Abstraction Layer, Monitoring |
| **slskd Updates** | NIEDRIG | MITTEL | Version Pinning, Tests |
| **Soulseek Network Issues** | MITTEL | MITTEL | Retry Logic, Alternative Sources |

---

## 18. Erfolgskriterien und KPIs

### 18.1 Quantitative KPIs

| KPI | Ziel | Messung |
|-----|------|---------|
| **Test Coverage** | >80% | pytest-cov |
| **API Response Time (p95)** | <500ms | Logging/Monitoring |
| **Download Success Rate** | >85% | DB Metrics |
| **Memory Usage** | <512MB | Docker Stats |
| **Startup Time** | <10s | Timing Logs |
| **Uptime** | >99% | Health Checks |

### 18.2 Qualitative Ziele

- Codebase ist wartbar und erweiterbar
- Dokumentation ist vollständig und aktuell
- Neue Features können in <1 Woche hinzugefügt werden
- Onboarding neuer Entwickler in <1 Tag möglich

### 18.3 Release Milestones

| Version | Milestone | Kriterien |
|---------|-----------|-----------|
| v0.1.0 | Alpha | Core Features funktionieren |
| v0.5.0 | Beta | Alle Features implementiert |
| v1.0.0 | Stable | Production-ready, dokumentiert |
| v2.0.0 | Plugin | Erweiterbar durch Community |

---

## 19. Anhang

### 19.1 Glossar

| Begriff | Definition |
|---------|------------|
| **PKCE** | Proof Key for Code Exchange - Sicherer OAuth Flow ohne Client Secret |
| **slskd** | Soulseek Daemon - REST API für Soulseek Netzwerk |
| **ISRC** | International Standard Recording Code - Eindeutige Track-ID |
| **SSE** | Server-Sent Events - Echtzeit-Updates vom Server |
| **HTMX** | HTML Extensions - JS-minimierte Interaktivität |
| **LRU** | Least Recently Used - Cache Eviction Strategie |
| **TTL** | Time To Live - Cache Ablaufzeit |

### 19.2 Referenzen

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API)
- [slskd API](https://github.com/slskd/slskd)
- [HTMX Documentation](https://htmx.org/docs/)

### 19.3 Entwicklungs-Tools

| Tool | Zweck | Befehl |
|------|-------|--------|
| Poetry | Dependencies | `poetry install` |
| Ruff | Linting | `ruff check .` |
| Mypy | Type Checking | `mypy src/` |
| Pytest | Testing | `pytest tests/` |
| Bandit | Security | `bandit -r src/` |
| Alembic | Migrations | `alembic upgrade head` |

### 19.4 Kontakt & Support

- **Repository:** https://github.com/bozzfozz/soulspot
- **Issues:** GitHub Issues
- **Dokumentation:** /docs Verzeichnis

---

**Dokument Ende**

*Erstellt: 2025-11-26*  
*Version: 1.0*  
*Status: Vollständig*
