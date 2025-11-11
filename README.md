# SoulSpot Bridge

> 🎵 Intelligente Musik-Download-Anwendung mit Spotify-Playlist-Synchronisation und Soulseek-Integration

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-TBD-lightgrey.svg)](LICENSE)
[![CI](https://github.com/bozzfozz/soulspot-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/bozzfozz/soulspot-bridge/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/bozzfozz/soulspot-bridge?include_prereleases)](https://github.com/bozzfozz/soulspot-bridge/releases)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/bozzfozz/soulspot-bridge/pkgs/container/soulspot-bridge)

## 📖 Überblick

**SoulSpot Bridge** ist eine moderne Musik-Download-Anwendung, die Spotify-Playlists mit dem Soulseek-Netzwerk verbindet. Die Anwendung ermöglicht es, Musik-Sammlungen automatisch zu synchronisieren, Metadaten anzureichern und Dateien zu organisieren.

### 🎯 Kernfeatures

- 🎵 **Spotify-Integration:** Import von Playlists und Tracks via OAuth PKCE
- ⬇️ **Automatisierte Downloads:** Soulseek-Downloads über [slskd](https://github.com/slskd/slskd)
- 🔄 **Auto Music Import:** Automatisches Verschieben fertiger Downloads in die Musikbibliothek
- 📊 **Metadata-Enrichment:** Anreicherung mit MusicBrainz und CoverArtArchive
- 🎨 **Artwork-Management:** Automatischer Download und Optimierung von Cover-Arts
- 🗂️ **File-Organisation:** Intelligente Datei-Struktur und Tagging
- 🔄 **Worker-System:** Asynchrone Verarbeitung für performante Downloads
- 🌐 **Web-UI:** Moderne Benutzeroberfläche mit HTMX und Tailwind CSS
- 🔍 **Observability:** Strukturiertes Logging mit Correlation IDs und Health Checks
- 🐳 **Docker-Ready:** Vollständige Docker-Unterstützung mit Compose-Setup

### 🏗️ Architektur

SoulSpot Bridge folgt einer **Layered Architecture** mit Domain-Driven Design Prinzipien:

```
┌─────────────────────────────────────┐
│   Presentation (REST API / Web UI) │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   Application (Use Cases / CQRS)   │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   Domain (Entities / Value Objects)│
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   Infrastructure (DB / Integrations)│
└─────────────────────────────────────┘
```

**Mehr Details:** [docs/architecture.md](docs/architecture.md)

### 📋 Projekt-Status

**✅ Phase 5 Complete! - Alpha Version 0.1.0**

Aktueller Stand:
- ✅ Umfassende Architektur-Dokumentation
- ✅ Design-System und Style Guide
- ✅ Complete Development Roadmap
- ✅ Initial Assessment abgeschlossen
- ✅ Domain Layer implementiert
- ✅ Infrastructure Layer implementiert
- ✅ External Integrations implementiert (slskd, Spotify, MusicBrainz)
- ✅ Application Layer implementiert (Use Cases, Workers, Caching)
- ✅ Web UI implementiert (Jinja2, HTMX, Tailwind CSS)
- ✅ REST API vollständig integriert
- ✅ Session Management und OAuth Flow
- 🔄 Ready for Phase 6: Production Readiness

**Nächste Schritte:** Continue enhancing production-ready features (CI/CD improvements, deployment automation) - See [Roadmap](docs/development-roadmap.md)

## 📚 Dokumentation

### Getting Started
- **[Docker Setup Guide](docs/docker-setup.md)** - Vollständige Docker-Deployment-Anleitung ⭐
- **[Setup Guide](docs/setup-guide.md)** - Umfassende Installations- und Konfigurationsanleitung
- **[Contributing Guide](docs/contributing.md)** - Wie man zum Projekt beiträgt
- **[Testing Guide](docs/testing-guide.md)** - Test-Strategie und Best Practices

### Haupt-Dokumentation
- **[Architecture Guide](docs/architecture.md)** - Detaillierte Architektur-Spezifikation
- **[Style Guide](docs/soulspot-style-guide.md)** - Design-System und UI-Guidelines
- **[Observability Guide](docs/observability-guide.md)** - Strukturiertes Logging und Health Checks
- **[CI/CD Guide](docs/ci-cd.md)** - Continuous Integration und Automated Releases
- **[Development Roadmap](docs/development-roadmap.md)** - Zukünftige Entwicklungsphasen und Features
- **[CHANGELOG](CHANGELOG.md)** - Vollständige Versionshistorie

### Entwickler-Dokumentation
- **[Example Issues](docs/issues/example-issues.md)** - Vorgefertigte Issue-Templates für Top-Tasks
- **[Copilot Instructions](.github/copilot-instructions.md)** - Entwicklungs-Prozess
- **[Initial Assessment](docs/analysis/initial-assessment.md)** - Initiale Analyse und Aufgabenplan
- **[Development History](docs/history/)** - Phase Summaries und PR-Zusammenfassungen

## 🚀 Quick Start

### Option 1: Docker (Empfohlen für Production)

Docker ist der einfachste Weg, SoulSpot Bridge zu starten:

```bash
# Repository klonen
git clone https://github.com/bozzfozz/soulspot-bridge.git
cd soulspot-bridge

# Erforderliche Verzeichnisse erstellen
mkdir -p mnt/downloads mnt/music

# Environment-Datei erstellen
cp .env.example .env
# .env bearbeiten und anpassen (siehe Docker Setup Guide)

# Services mit Docker starten
docker-compose up -d --build

# Logs ansehen
docker-compose logs -f
```

**Wichtig:** Vor dem Start müssen `mnt/downloads` und `mnt/music` Verzeichnisse existieren!

**Vollständige Docker-Anleitung:** [Docker Setup Guide](docs/docker-setup.md)

### Option 2: Lokale Entwicklung

Für Entwicklungszwecke kannst du die Anwendung lokal ausführen:

#### Prerequisites

- Python 3.12 oder höher
- Docker und Docker Compose (für slskd)
- Git

#### Installation

```bash
# Repository klonen
git clone https://github.com/bozzfozz/soulspot-bridge.git
cd soulspot-bridge

# Dependencies installieren (Poetry empfohlen)
poetry install

# Environment-Datei erstellen
cp .env.example .env
# .env bearbeiten und anpassen

# Nur slskd mit Docker starten
docker-compose up -d slskd

# Database Migrations ausführen
poetry run alembic upgrade head

# Development Server starten
poetry run uvicorn soulspot.main:app --reload --port 8000
```

### Zugriff

#### Docker Deployment
- **SoulSpot Bridge:** http://localhost:8765
- **API Docs:** http://localhost:8765/docs
- **Web UI:** http://localhost:8765/ui
- **Health:** http://localhost:8765/health
- **Readiness:** http://localhost:8765/ready
- **slskd UI:** http://localhost:5030

#### Local Development
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Web UI:** http://localhost:8000/ui
- **Health:** http://localhost:8000/health
- **Readiness:** http://localhost:8000/ready
- **slskd UI:** http://localhost:5030

## 🛠️ Technologie-Stack

### Backend
- **Framework:** FastAPI 0.115+ (Async, Type-Safe)
- **ORM:** SQLAlchemy 2.0+ (Async)
- **Database:** SQLite (simple) / PostgreSQL (standard)
- **Queue:** Celery/Dramatiq + Redis *(standard Profile)*
- **Migrations:** Alembic 1.14+

### Frontend
- **Template Engine:** Jinja2
- **CSS Framework:** Tailwind CSS
- **JavaScript:** HTMX (Progressive Enhancement)

### Integrationen
- **Spotify:** Web API mit OAuth PKCE
- **Soulseek:** [slskd](https://github.com/slskd/slskd) HTTP API
- **Metadata:** MusicBrainz + CoverArtArchive

### Code-Qualität
- **Linting:** ruff 0.7+
- **Type-Checking:** mypy 1.13+
- **Testing:** pytest 8.3+ mit pytest-asyncio
- **Security:** bandit, safety

## 📦 Profile

SoulSpot Bridge unterstützt zwei Deployment-Profile:

### `simple` Profile (Default)
- SQLite Datenbank
- Keine externe Message Queue
- Lokales Dateisystem
- Ideal für Entwicklung und Single-User-Setup

### `standard` Profile
- PostgreSQL Datenbank
- Redis + Celery/Dramatiq für Background-Jobs
- Optional: S3/MinIO für Artwork-Storage
- Ideal für Production und Multi-User-Setup

**Profil wählen:** `export PROFILE=simple` oder `export PROFILE=standard`

## 🧪 Testing (geplant)

```bash
# Alle Tests ausführen
poetry run pytest

# Mit Coverage
poetry run pytest --cov=src/ --cov-report=html

# Nur Unit-Tests
poetry run pytest tests/unit/

# Integration-Tests (benötigt Docker-Services)
docker-compose up -d postgres redis
poetry run pytest tests/integration/
```

## 🔧 Entwicklung

### Code Quality Checks

```bash
# Linting
poetry run ruff check src/

# Auto-Formatting
poetry run ruff format src/

# Type-Checking
poetry run mypy src/

# Security-Scanning
poetry run bandit -r src/
```

### Database-Migrations

```bash
# Neue Migration erstellen
poetry run alembic revision --autogenerate -m "Description"

# Migration anwenden
poetry run alembic upgrade head

# Migration rückgängig machen
poetry run alembic downgrade -1
```

## 🤝 Contributing

Contributions sind willkommen! Bitte beachte:

1. Lies den **[Contributing Guide](docs/contributing.md)** für detaillierte Anweisungen
2. Folge dem **[Setup Guide](docs/setup-guide.md)** für die Entwicklungsumgebung
3. Lies die **[Architektur-Dokumentation](docs/architecture.md)**
4. Erstelle ein Issue für neue Features oder Bugs
5. Nutze die [Issue-Templates](.github/ISSUE_TEMPLATE/)
6. Folge dem [Style Guide](docs/soulspot-style-guide.md)
7. Schreibe Tests für neuen Code (siehe [Testing Guide](docs/testing-guide.md))
8. Erstelle einen Pull Request

### Entwicklungs-Workflow

Siehe [.github/copilot-instructions.md](.github/copilot-instructions.md) für den vollständigen Entwicklungs-Lifecycle.

## 📋 Roadmap

### Phase 1: Foundation (Wochen 1-2) ✅
- [x] Projekt-Setup und Dependency-Management
- [x] Domain-Layer mit Entities und Value Objects
- [x] Docker Compose Development Environment

### Phase 2: Core Infrastructure (Wochen 3-5) ✅
- [x] Settings-Management mit Profile-Support
- [x] Database-Layer mit SQLAlchemy und Alembic
- [x] FastAPI Application Entry

### Phase 3: External Integrations (Wochen 6-9) ✅
- [x] slskd Client Implementation
- [x] Spotify Client mit OAuth
- [x] MusicBrainz Client

### Phase 4: Business Logic (Wochen 10-14) ✅
- [x] Worker-System (Async Job Queue)
- [x] Application Use-Cases
- [x] Token Management Service
- [x] Caching Layer

### Phase 5: User Interface (Wochen 15-18) ✅
- [x] Web UI mit Jinja2 und HTMX
- [x] UI-Komponenten nach Style Guide
- [x] REST API Integration
- [x] Session Management und OAuth

### Phase 6: Production-Ready (Wochen 19-20) 🔄
- [x] **Observability** (Logging und Health Checks)
  - [x] Structured logging with JSON formatting and correlation IDs
  - [x] Enhanced health checks with dependency monitoring
- [x] **Docker Setup** (Production-ready Deployment)
  - [x] Production Dockerfile with multi-stage build
  - [x] Docker Compose configuration
  - [x] Docker entrypoint with directory validation
  - [x] PUID/PGID support for file permissions
  - [x] Complete Docker documentation
- [x] **Auto Music Import**
  - [x] Automatic file moving from downloads to music library
  - [x] Support for multiple audio formats
  - [x] File completion detection
  - [x] Background service integration
- [ ] CI/CD Pipeline
- [ ] Security Hardening

**Detaillierte Roadmap:** [docs/development-roadmap.md](docs/development-roadmap.md)

## 🔗 Referenzen

### Ähnliche Projekte
- [SoulSync](https://github.com/Nezreka/SoulSync) - Python-Anwendung mit slskd-Integration
- [Soulify](https://github.com/WB2024/soulify) - Web-App für Spotify + Soulseek

### Technologie-Dokumentation
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Pydantic](https://docs.pydantic.dev/)
- [slskd](https://github.com/slskd/slskd)
- [Tailwind CSS](https://tailwindcss.com/)

## 📄 Lizenz

TBD - Lizenz wird noch festgelegt

## 🙏 Acknowledgments

- [slskd](https://github.com/slskd/slskd) für die Soulseek-API-Bridge
- [SoulSync](https://github.com/Nezreka/SoulSync) und [Soulify](https://github.com/WB2024/soulify) als Referenzprojekte
- Die Open-Source-Community für die großartigen Tools und Libraries

---

**Version:** 0.1.0 (Alpha) | **Status:** Active Development | **Letzte Aktualisierung:** 2025-11-09