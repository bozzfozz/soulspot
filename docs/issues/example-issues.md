# Example Issue Templates for Top-Priority Tasks

Dieses Dokument enthält vorgefertigte Issue-Texte für die Top-Priority Tasks aus dem Initial Assessment. Diese können direkt als GitHub Issues erstellt werden.

---

## Issue #1: Initial Python Project Setup with Dependency Management

**Title:** `[P0][SETUP] Initial Python Project Setup with Dependency Management`

**Labels:** `P0`, `setup`, `dependencies`, `enhancement`

**Body:**

```markdown
## Feature-Beschreibung
Initiales Python-Projekt mit allen notwendigen Dependencies und Tooling aufsetzen, basierend auf der Architektur-Dokumentation.

## Motivation / Use Case
Dieses Task ist die Grundvoraussetzung für alle weiteren Implementierungen. Ohne ein ordentlich konfiguriertes Projekt mit Dependency-Management können keine weiteren Module entwickelt werden.

## Akzeptanzkriterien
- [ ] `pyproject.toml` mit allen Dependencies aus `docs/architecture.md` erstellt
- [ ] Poetry oder setuptools für Dependency-Management konfiguriert
- [ ] Python 3.12 als Target-Version definiert
- [ ] Development Dependencies (pytest, ruff, mypy, etc.) konfiguriert
- [ ] Pre-commit Hooks für Linting und Formatting eingerichtet
- [ ] `.gitignore` für Python-Projekte angelegt
- [ ] `ruff.toml` und `mypy.ini` für Code Quality Tools konfiguriert
- [ ] README.md mit Quick-Start erweitert

## Betroffene Layer / Komponenten
- [x] Infrastructure Layer (Build-System, Tooling)
- [ ] Presentation Layer
- [ ] Application Layer
- [ ] Domain Layer

## Geschätzter Aufwand
- [x] S (Small: 1-3 Tage)

## Abhängigkeiten
Keine - ist Grundvoraussetzung für alle weiteren Tasks

## Technische Details

### Core Dependencies (aus architecture.md)
```toml
[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.115.0"
pydantic = "^2.9.0"
pydantic-settings = "^2.5.0"
uvicorn = "^0.31.0"
httpx = "^0.28.0"
sqlalchemy = {extras = ["asyncio"], version = "^2.0.0"}
alembic = "^1.14.0"
```

### Dev Dependencies
```toml
[tool.poetry.group.dev.dependencies]
pytest = "^8.3.0"
pytest-asyncio = "^0.24.0"
pytest-cov = "^5.1.0"
ruff = "^0.7.0"
mypy = "^1.13.0"
bandit = "^1.8.0"
safety = "^3.2.0"
pre-commit = "^3.8.0"
factory-boy = "^3.3.0"
httpx-mock = "^0.26.0"
```

### Pre-commit Configuration
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic]
```

## Referenzen
- docs/architecture.md - Section 1.4 Technologie-Stack
```

---

## Issue #2: Implement Domain Layer with Entities and Value Objects

**Title:** `[P0][DOMAIN] Implement Domain Layer with Entities and Value Objects`

**Labels:** `P0`, `domain`, `architecture`, `enhancement`

**Body:**

```markdown
## Feature-Beschreibung
Ordnerstruktur und Domain-Entities gemäß DDD-Prinzipien implementieren. Dies bildet die fachliche Kernlogik der Anwendung ab.

## Motivation / Use Case
Der Domain Layer ist das Herzstück der Anwendung und enthält die gesamte Business-Logik. Ohne diese Grundlage können keine Use-Cases implementiert werden.

## Akzeptanzkriterien
- [ ] Ordnerstruktur gemäß `docs/architecture.md` erstellt:
  ```
  src/soulspot/
  ├── __init__.py
  ├── domain/
  │   ├── __init__.py
  │   ├── entities/
  │   │   ├── __init__.py
  │   │   ├── artist.py
  │   │   ├── album.py
  │   │   ├── track.py
  │   │   ├── playlist.py
  │   │   └── download.py
  │   ├── value_objects/
  │   │   ├── __init__.py
  │   │   ├── artist_id.py
  │   │   ├── album_id.py
  │   │   ├── track_id.py
  │   │   ├── file_path.py
  │   │   └── spotify_uri.py
  │   ├── services/
  │   │   └── __init__.py
  │   ├── events/
  │   │   ├── __init__.py
  │   │   ├── track_downloaded.py
  │   │   └── playlist_synced.py
  │   ├── ports/
  │   │   └── __init__.py
  │   └── exceptions/
  │       ├── __init__.py
  │       └── domain_errors.py
  ```
- [ ] Domain Entities mit dataclasses implementiert
- [ ] Value Objects mit Validation implementiert
- [ ] Domain Exceptions definiert
- [ ] Domain Events definiert
- [ ] Type-Hints vollständig und mit mypy validiert
- [ ] Docstrings für alle Public Classes/Methods

## Betroffene Layer / Komponenten
- [x] Domain Layer (Entities / Value Objects / Services)

## Geschätzter Aufwand
- [x] S (Small: 1-3 Tage)

## Abhängigkeiten
- Issue #1 (Projekt-Setup)

## Technische Details

### Beispiel Entity (Track)
```python
# src/soulspot/domain/entities/track.py
from dataclasses import dataclass
from datetime import datetime
from domain.value_objects import TrackId, ArtistId, AlbumId

@dataclass
class Track:
    """Represents a music track in the domain."""
    
    id: TrackId
    title: str
    artist_id: ArtistId
    album_id: AlbumId | None
    duration_ms: int
    isrc: str | None = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    def update_metadata(self, title: str | None = None, duration_ms: int | None = None):
        """Update track metadata."""
        if title is not None:
            self.title = title
        if duration_ms is not None:
            self.duration_ms = duration_ms
        self.updated_at = datetime.utcnow()
```

### Beispiel Value Object (TrackId)
```python
# src/soulspot/domain/value_objects/track_id.py
from dataclasses import dataclass
from uuid import UUID, uuid4

@dataclass(frozen=True)
class TrackId:
    """Value object for track identification."""
    
    value: UUID
    
    def __post_init__(self):
        if not isinstance(self.value, UUID):
            raise ValueError(f"TrackId must be a UUID, got {type(self.value)}")
    
    @classmethod
    def generate(cls) -> "TrackId":
        """Generate a new unique TrackId."""
        return cls(value=uuid4())
    
    @classmethod
    def from_string(cls, id_str: str) -> "TrackId":
        """Create TrackId from string representation."""
        return cls(value=UUID(id_str))
    
    def __str__(self) -> str:
        return str(self.value)
```

### Beispiel Domain Exception
```python
# src/soulspot/domain/exceptions/domain_errors.py
class DomainException(Exception):
    """Base exception for domain layer."""
    pass

class EntityNotFoundException(DomainException):
    """Raised when an entity is not found."""
    
    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id {entity_id} not found")

class InvalidValueObjectException(DomainException):
    """Raised when a value object has invalid data."""
    pass
```

## Referenzen
- docs/architecture.md - Section 1.3 Ordnerstruktur
- docs/roadmap - Section 4 Kernkomponenten
```

---

## Issue #3: Docker Compose Setup for Local Development Environment

**Title:** `[P0][INFRA] Docker Compose Setup for Local Development Environment`

**Labels:** `P0`, `docker`, `infrastructure`, `enhancement`

**Body:**

```markdown
## Feature-Beschreibung
Docker Compose Setup mit allen benötigten Services (slskd, PostgreSQL, Redis) für lokale Entwicklung.

## Motivation / Use Case
Entwickler benötigen eine einfache Möglichkeit, alle externen Services lokal zu starten. Docker Compose ermöglicht einen einheitlichen Entwicklungsumgebung über verschiedene Betriebssysteme hinweg.

## Akzeptanzkriterien
- [ ] `docker-compose.yml` für Development erstellt
- [ ] `docker-compose.prod.yml` als Vorlage für Production
- [ ] slskd Service konfiguriert und unter http://localhost:5030 erreichbar
- [ ] PostgreSQL Service für standard Profile (Port 5432)
- [ ] Redis Service für Queue/Cache (Port 6379)
- [ ] `.env.example` mit allen notwendigen Environment Variables
- [ ] Health-Checks für alle Services implementiert
- [ ] Volume-Mapping für Daten-Persistenz
- [ ] Netzwerk-Konfiguration für Service-Communication
- [ ] `Makefile` oder `Justfile` mit häufigen Commands
- [ ] README.md mit Docker-Anleitung erweitert

## Betroffene Layer / Komponenten
- [x] Infrastructure Layer (External Services)

## Geschätzter Aufwand
- [x] M (Medium: 4-7 Tage)

## Abhängigkeiten
- Issue #1 (Projekt-Setup)

## Technische Details

### docker-compose.yml
```yaml
version: '3.9'

services:
  # Soulseek daemon - kritische Dependency für Downloads
  slskd:
    image: slskd/slskd:latest
    container_name: soulspot-slskd
    ports:
      - "5030:5030"      # Web UI
      - "50300:50300"    # Soulseek Network
    volumes:
      - ./data/slskd/config:/app/config
      - ./data/slskd/downloads:/var/slskd/downloads
      - ./data/slskd/incomplete:/var/slskd/incomplete
      - ./data/slskd/shared:/var/slskd/shared
    environment:
      - SLSKD_SLSK_USERNAME=${SLSKD_USERNAME:-soulspot}
      - SLSKD_SLSK_PASSWORD=${SLSKD_PASSWORD:-changeme}
      - SLSKD_WEB_AUTHENTICATION_USERNAME=${SLSKD_WEB_USERNAME:-admin}
      - SLSKD_WEB_AUTHENTICATION_PASSWORD=${SLSKD_WEB_PASSWORD:-admin}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5030/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    networks:
      - soulspot-network

  # PostgreSQL für standard Profile
  postgres:
    image: postgres:16-alpine
    container_name: soulspot-postgres
    ports:
      - "5432:5432"
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=${DB_NAME:-soulspot}
      - POSTGRES_USER=${DB_USER:-soulspot}
      - POSTGRES_PASSWORD=${DB_PASSWORD:-soulspot}
      - POSTGRES_INITDB_ARGS=--encoding=UTF-8 --locale=C
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-soulspot}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - soulspot-network

  # Redis für Queue und Cache
  redis:
    image: redis:7-alpine
    container_name: soulspot-redis
    ports:
      - "6379:6379"
    volumes:
      - ./data/redis:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - soulspot-network

networks:
  soulspot-network:
    driver: bridge

volumes:
  postgres-data:
  redis-data:
  slskd-config:
  slskd-downloads:
```

### .env.example
```bash
# SoulSpot Bridge Environment Configuration
# Kopiere diese Datei zu .env und passe die Werte an

# ============================================
# Profile Configuration
# ============================================
PROFILE=simple  # simple oder standard

# ============================================
# Database Configuration
# ============================================
# SQLite für simple Profile
DATABASE_URL=sqlite:///./data/soulspot.db

# PostgreSQL für standard Profile
# DATABASE_URL=postgresql+asyncpg://soulspot:soulspot@localhost:5432/soulspot
DB_NAME=soulspot
DB_USER=soulspot
DB_PASSWORD=changeme_in_production

# ============================================
# slskd Configuration
# ============================================
SLSKD_URL=http://localhost:5030
SLSKD_USERNAME=soulspot
SLSKD_PASSWORD=changeme_in_production
SLSKD_WEB_USERNAME=admin
SLSKD_WEB_PASSWORD=changeme_in_production

# ============================================
# Redis Configuration (standard Profile)
# ============================================
REDIS_URL=redis://localhost:6379/0

# ============================================
# Spotify Configuration
# ============================================
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/auth/spotify/callback

# ============================================
# Security
# ============================================
SECRET_KEY=generate_a_secure_random_secret_key_here_at_least_32_chars
JWT_SECRET=generate_another_secure_random_secret_for_jwt_tokens

# ============================================
# Application Configuration
# ============================================
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
API_HOST=0.0.0.0
API_PORT=8000

# ============================================
# Worker Configuration (standard Profile)
# ============================================
WORKER_CONCURRENCY=4
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### Makefile
```makefile
.PHONY: help up down logs restart clean build test

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start all services
	docker-compose up -d
	@echo "Services started. slskd UI: http://localhost:5030"

down: ## Stop all services
	docker-compose down

logs: ## Show logs from all services
	docker-compose logs -f

restart: ## Restart all services
	docker-compose restart

clean: ## Stop services and remove volumes
	docker-compose down -v
	@echo "Warning: This removes all data volumes!"

build: ## Rebuild all services
	docker-compose build --no-cache

test: ## Run tests with Docker services
	docker-compose up -d postgres redis
	poetry run pytest
	docker-compose down

health: ## Check health of all services
	@docker-compose ps
```

## Referenzen
- docs/architecture.md - Section 1.4 Technologie-Stack
- docs/roadmap - Section 3 Profile-spezifische Festlegungen
- slskd: https://github.com/slskd/slskd
```

---

## Issue #4: Implement Settings Management with Profile Support

**Title:** `[P1][CONFIG] Implement Settings Management with Profile Support`

**Labels:** `P1`, `config`, `settings`, `enhancement`

**Body:**

```markdown
## Feature-Beschreibung
Pydantic-basiertes Settings-System mit Unterstützung für simple/standard Profile implementieren.

## Motivation / Use Case
Ein robustes Settings-Management ist essentiell für verschiedene Deployment-Szenarien. Profile ermöglichen es, zwischen einfacher lokaler Entwicklung (simple) und Production-Setup (standard) zu wechseln.

## Akzeptanzkriterien
- [ ] `config/settings.py` mit Pydantic BaseSettings implementiert
- [ ] Profil-System (`PROFILE=simple|standard`) implementiert
- [ ] Environment-Variable-Parsing für alle Services
- [ ] Settings-Validation mit Pydantic
- [ ] Separate Settings-Klassen für Sub-Systeme:
  - [ ] DatabaseSettings
  - [ ] SpotifySettings
  - [ ] SoulseekSettings
  - [ ] WorkerSettings
  - [ ] SecuritySettings
  - [ ] LoggingSettings
- [ ] Settings-Loading mit Dotenv-Support
- [ ] Type-safe Settings-Zugriff
- [ ] Unit-Tests für Settings-Validation
- [ ] Dokumentation der Settings-Parameter

## Betroffene Layer / Komponenten
- [x] Infrastructure Layer (Configuration)

## Geschätzter Aufwand
- [x] S (Small: 1-3 Tage)

## Abhängigkeiten
- Issue #1 (Projekt-Setup)
- Issue #2 (Domain-Layer)

## Technische Details

### Main Settings Module
```python
# src/soulspot/config/settings.py
from enum import Enum
from pathlib import Path
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Profile(str, Enum):
    """Application profile/environment."""
    SIMPLE = "simple"
    STANDARD = "standard"


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    model_config = SettingsConfigDict(env_prefix="DB_")
    
    url: str = Field(
        default="sqlite:///./data/soulspot.db",
        description="Database connection URL"
    )
    echo: bool = Field(
        default=False,
        description="Enable SQL query logging"
    )
    pool_size: int = Field(
        default=5,
        description="Connection pool size (PostgreSQL only)"
    )
    max_overflow: int = Field(
        default=10,
        description="Max overflow connections (PostgreSQL only)"
    )
    
    @validator("url")
    def validate_url(cls, v: str, values: dict) -> str:
        """Validate database URL based on profile."""
        profile = values.get("profile", Profile.SIMPLE)
        if profile == Profile.SIMPLE and not v.startswith("sqlite"):
            raise ValueError("simple profile requires SQLite database")
        return v


class SoulseekSettings(BaseSettings):
    """slskd client configuration."""
    
    model_config = SettingsConfigDict(env_prefix="SLSKD_")
    
    url: str = Field(
        default="http://localhost:5030",
        description="slskd API URL"
    )
    username: str = Field(
        ...,
        description="Soulseek username"
    )
    password: str = Field(
        ...,
        description="Soulseek password"
    )
    web_username: str = Field(
        default="admin",
        description="slskd web UI username"
    )
    web_password: str = Field(
        ...,
        description="slskd web UI password"
    )
    timeout: int = Field(
        default=30,
        description="API request timeout in seconds"
    )


class SpotifySettings(BaseSettings):
    """Spotify API configuration."""
    
    model_config = SettingsConfigDict(env_prefix="SPOTIFY_")
    
    client_id: str = Field(
        ...,
        description="Spotify Client ID"
    )
    client_secret: str = Field(
        ...,
        description="Spotify Client Secret"
    )
    redirect_uri: str = Field(
        default="http://localhost:8000/auth/spotify/callback",
        description="OAuth redirect URI"
    )
    scopes: list[str] = Field(
        default=[
            "playlist-read-private",
            "playlist-read-collaborative",
            "user-library-read"
        ],
        description="Required OAuth scopes"
    )


class WorkerSettings(BaseSettings):
    """Worker/Queue configuration."""
    
    model_config = SettingsConfigDict(env_prefix="WORKER_")
    
    concurrency: int = Field(
        default=4,
        description="Number of concurrent workers"
    )
    broker_url: str | None = Field(
        default=None,
        description="Message broker URL (standard profile only)"
    )
    result_backend: str | None = Field(
        default=None,
        description="Result backend URL (standard profile only)"
    )


class SecuritySettings(BaseSettings):
    """Security-related settings."""
    
    secret_key: str = Field(
        ...,
        min_length=32,
        description="Application secret key"
    )
    jwt_secret: str = Field(
        ...,
        min_length=32,
        description="JWT signing secret"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    jwt_expiration_minutes: int = Field(
        default=60,
        description="JWT token expiration in minutes"
    )


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    
    model_config = SettingsConfigDict(env_prefix="LOG_")
    
    level: str = Field(
        default="INFO",
        description="Logging level"
    )
    format: str = Field(
        default="json",
        description="Log format: json or text"
    )


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Profile
    profile: Profile = Field(
        default=Profile.SIMPLE,
        description="Application profile"
    )
    
    # Application
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    soulseek: SoulseekSettings
    spotify: SpotifySettings
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    security: SecuritySettings
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    @validator("worker")
    def validate_worker_for_profile(cls, v: WorkerSettings, values: dict) -> WorkerSettings:
        """Validate worker settings based on profile."""
        profile = values.get("profile")
        if profile == Profile.STANDARD:
            if not v.broker_url:
                raise ValueError("standard profile requires worker broker_url")
        return v


# Singleton instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

### Unit Tests
```python
# tests/unit/config/test_settings.py
import pytest
from pydantic import ValidationError
from soulspot.config.settings import Settings, Profile


def test_settings_simple_profile_with_sqlite():
    """Test simple profile with SQLite database."""
    settings = Settings(
        profile=Profile.SIMPLE,
        database__url="sqlite:///./test.db",
        slskd__username="test",
        slskd__password="test",
        slskd__web_password="test",
        spotify__client_id="test_id",
        spotify__client_secret="test_secret",
        security__secret_key="a" * 32,
        security__jwt_secret="b" * 32,
    )
    assert settings.profile == Profile.SIMPLE
    assert settings.database.url.startswith("sqlite")


def test_settings_simple_profile_rejects_postgresql():
    """Test that simple profile rejects PostgreSQL."""
    with pytest.raises(ValidationError):
        Settings(
            profile=Profile.SIMPLE,
            database__url="postgresql://localhost/db",
            # ... other required fields
        )


def test_settings_standard_profile_requires_broker():
    """Test that standard profile requires broker URL."""
    with pytest.raises(ValidationError):
        Settings(
            profile=Profile.STANDARD,
            database__url="postgresql://localhost/db",
            worker__broker_url=None,  # Missing!
            # ... other required fields
        )


def test_settings_from_env_file(tmp_path):
    """Test loading settings from .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("""
PROFILE=simple
DB_URL=sqlite:///./test.db
SLSKD_USERNAME=testuser
SLSKD_PASSWORD=testpass
SLSKD_WEB_PASSWORD=webpass
SPOTIFY_CLIENT_ID=client123
SPOTIFY_CLIENT_SECRET=secret456
SECRET_KEY=""" + "x" * 32 + """
JWT_SECRET=""" + "y" * 32)
    
    settings = Settings(_env_file=str(env_file))
    assert settings.profile == Profile.SIMPLE
    assert settings.soulseek.username == "testuser"
```

## Referenzen
- docs/architecture.md - Section 1.6 12-Factor-App
- docs/roadmap - Section 3 Profile-spezifische Festlegungen
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
```

---

## Issue #5: Setup SQLAlchemy 2.0 Async with Alembic Migrations

**Title:** `[P1][DATABASE] Setup SQLAlchemy 2.0 Async with Alembic Migrations`

**Labels:** `P1`, `database`, `persistence`, `enhancement`

**Body:**

```markdown
## Feature-Beschreibung
SQLAlchemy 2.0 Async Setup mit Repository-Pattern und Alembic für Database Migrations.

## Motivation / Use Case
Eine robuste Persistence-Schicht ist essentiell für die Anwendung. SQLAlchemy 2.0 mit Async-Support ermöglicht performante Datenbankzugriffe, während Alembic eine saubere Migration-Strategie sicherstellt.

## Akzeptanzkriterien
- [ ] SQLAlchemy 2.0 Async Engine und Session konfiguriert
- [ ] Base Model-Klasse für alle ORM-Models
- [ ] ORM-Models für Domain-Entities in `infrastructure/persistence/models/`:
  - [ ] ArtistModel
  - [ ] AlbumModel
  - [ ] TrackModel
  - [ ] PlaylistModel
  - [ ] DownloadModel
- [ ] Alembic Migrations Setup mit `alembic init`
- [ ] Initial Migration mit allen Tables
- [ ] Repository-Interfaces in `domain/ports/` definiert
- [ ] Repository-Implementierungen in `infrastructure/persistence/repositories/`
- [ ] Unit-of-Work Pattern implementiert
- [ ] Profil-basierte DB-Konfiguration (SQLite vs. PostgreSQL)
- [ ] Connection-Pooling für Async Sessions
- [ ] Integration-Tests für Repositories
- [ ] Dokumentation für Migration-Workflow

## Betroffene Layer / Komponenten
- [x] Domain Layer (Repository Ports)
- [x] Infrastructure Layer (Persistence / Repositories)

## Geschätzter Aufwand
- [x] M (Medium: 4-7 Tage)

## Abhängigkeiten
- Issue #1 (Projekt-Setup)
- Issue #2 (Domain-Layer)
- Issue #4 (Settings-Management)

## Technische Details

### Database Engine Setup
```python
# src/soulspot/infrastructure/persistence/database.py
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase
from soulspot.config.settings import get_settings

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def create_engine() -> AsyncEngine:
    """Create async database engine based on settings."""
    settings = get_settings()
    
    engine = create_async_engine(
        settings.database.url,
        echo=settings.database.echo,
        pool_size=settings.database.pool_size if "postgresql" in settings.database.url else None,
        max_overflow=settings.database.max_overflow if "postgresql" in settings.database.url else None,
    )
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# Global session factory (initialized in lifespan)
session_factory: async_sessionmaker[AsyncSession] | None = None


async def get_session() -> AsyncSession:
    """FastAPI dependency for database session."""
    if session_factory is None:
        raise RuntimeError("Database not initialized")
    
    async with session_factory() as session:
        yield session
```

### Example ORM Model
```python
# src/soulspot/infrastructure/persistence/models/track_model.py
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class TrackModel(Base):
    """ORM model for Track entity."""
    
    __tablename__ = "tracks"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id"), nullable=False)
    album_id: Mapped[int | None] = mapped_column(ForeignKey("albums.id"), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    isrc: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    artist: Mapped["ArtistModel"] = relationship("ArtistModel", back_populates="tracks")
    album: Mapped["AlbumModel"] = relationship("AlbumModel", back_populates="tracks")
    
    def __repr__(self) -> str:
        return f"<TrackModel(id={self.id}, title='{self.title}')>"
```

### Repository Interface (Port)
```python
# src/soulspot/domain/ports/track_repository.py
from abc import ABC, abstractmethod
from domain.entities.track import Track
from domain.value_objects import TrackId


class ITrackRepository(ABC):
    """Repository interface for Track entity."""
    
    @abstractmethod
    async def add(self, track: Track) -> Track:
        """Add a new track."""
        pass
    
    @abstractmethod
    async def get_by_id(self, track_id: TrackId) -> Track | None:
        """Get track by ID."""
        pass
    
    @abstractmethod
    async def get_by_isrc(self, isrc: str) -> Track | None:
        """Get track by ISRC."""
        pass
    
    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Track]:
        """List all tracks with pagination."""
        pass
    
    @abstractmethod
    async def update(self, track: Track) -> Track:
        """Update existing track."""
        pass
    
    @abstractmethod
    async def delete(self, track_id: TrackId) -> bool:
        """Delete track by ID."""
        pass
```

### Repository Implementation
```python
# src/soulspot/infrastructure/persistence/repositories/track_repository.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domain.entities.track import Track
from domain.value_objects import TrackId, ArtistId, AlbumId
from domain.ports.track_repository import ITrackRepository
from infrastructure.persistence.models.track_model import TrackModel


class TrackRepository(ITrackRepository):
    """SQLAlchemy implementation of Track repository."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def add(self, track: Track) -> Track:
        """Add a new track."""
        model = self._to_model(track)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)
    
    async def get_by_id(self, track_id: TrackId) -> Track | None:
        """Get track by ID."""
        stmt = select(TrackModel).where(TrackModel.external_id == str(track_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def get_by_isrc(self, isrc: str) -> Track | None:
        """Get track by ISRC."""
        stmt = select(TrackModel).where(TrackModel.isrc == isrc)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
    
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Track]:
        """List all tracks with pagination."""
        stmt = select(TrackModel).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]
    
    async def update(self, track: Track) -> Track:
        """Update existing track."""
        stmt = select(TrackModel).where(TrackModel.external_id == str(track.id))
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        
        # Update fields
        model.title = track.title
        model.duration_ms = track.duration_ms
        model.isrc = track.isrc
        # ... weitere Felder
        
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)
    
    async def delete(self, track_id: TrackId) -> bool:
        """Delete track by ID."""
        stmt = select(TrackModel).where(TrackModel.external_id == str(track_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model:
            await self._session.delete(model)
            return True
        return False
    
    def _to_entity(self, model: TrackModel) -> Track:
        """Convert ORM model to domain entity."""
        return Track(
            id=TrackId.from_string(model.external_id),
            title=model.title,
            artist_id=ArtistId(value=model.artist_id),
            album_id=AlbumId(value=model.album_id) if model.album_id else None,
            duration_ms=model.duration_ms,
            isrc=model.isrc,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    
    def _to_model(self, entity: Track) -> TrackModel:
        """Convert domain entity to ORM model."""
        return TrackModel(
            external_id=str(entity.id),
            title=entity.title,
            artist_id=entity.artist_id.value,
            album_id=entity.album_id.value if entity.album_id else None,
            duration_ms=entity.duration_ms,
            isrc=entity.isrc,
        )
```

### Alembic Configuration
```ini
# alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

```python
# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from soulspot.infrastructure.persistence.database import Base
from soulspot.config.settings import get_settings

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add model's MetaData for autogenerate support
target_metadata = Base.metadata

# Import all models so they're registered
from soulspot.infrastructure.persistence.models import *  # noqa


def get_url():
    """Get database URL from settings."""
    return get_settings().database.url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
```

### Migration Commands
```bash
# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history
```

## Referenzen
- docs/architecture.md - Section 1.4 Technologie-Stack (Database & ORM)
- docs/roadmap - Section 2 Architekturprinzipien
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
- Alembic: https://alembic.sqlalchemy.org/
```

---

Diese Issue-Texte können direkt in GitHub Issues kopiert werden. Sie enthalten:
- Klare Beschreibungen und Motivation
- Detaillierte Akzeptanzkriterien
- Code-Beispiele
- Abhängigkeiten und Referenzen
- Realistische Aufwandsschätzungen
