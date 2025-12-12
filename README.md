# SoulSpot

<div align="center">

# ⚠️ ACTIVE DEVELOPMENT - DO NOT USE IN PRODUCTION ⚠️

## 🚧 THIS PROJECT IS UNDER HEAVY DEVELOPMENT 🚧

**This software is experimental and unstable. Use at your own risk.**

- 🔴 **APIs change frequently without notice**
- 🔴 **Database schemas may break between commits**
- 🔴 **Features are incomplete or broken**
- 🔴 **No backwards compatibility guaranteed**
- 🔴 **Data loss may occur**

**If you're looking for a stable music downloader, please wait for a stable release.**

---

</div>

> 🎵 Automatically download music from Spotify playlists via Soulseek and organize it cleanly - for local use.

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/github/v/release/bozzfozz/soulspot?include_prereleases)](https://github.com/bozzfozz/soulspot/releases)

## What is SoulSpot?
SoulSpot connects your Spotify playlists with the Soulseek network. The application automatically downloads tracks, enriches them with metadata, and stores them in a structured way in your music library – all via a modern web interface for local single-user use.

## Highlights for Users
- **Playlist Synchronization:** Import Spotify playlists via OAuth and keep them up to date.
- **Automated Downloads:** Downloads songs via the Soulseek service [slskd](https://github.com/slskd/slskd).
- **Library Management:** Automatically moves finished downloads to your music library.
- **Metadata & Cover Art:** Enriches tracks with information from MusicBrainz and CoverArtArchive.
- **Modern Web App:** Browser-based interface with intuitive UI, search filters, and status messages.
- **Local Use:** Optimized for single-user setup without cloud deployment.

## System Requirements
- Docker 20.10 or newer plus Docker Compose 2.x.
- A Spotify developer account (Client ID & Secret) for OAuth access.
- A Soulseek account or slskd API key.
- Sufficient storage space for downloads and two local folders: `mnt/downloads` and `mnt/music`.

## Quickstart with Docker
1. Clone the repository and navigate to it:
   ```bash
   git clone https://github.com/bozzfozz/soulspot.git
   cd soulspot
   ```
2. Create folders for downloads and library:
   ```bash
   mkdir -p mnt/downloads mnt/music
   ```
3. Copy and edit the example environment file:
   ```bash
   cp .env.example .env
   ```
   Enter at least the following values:
   ```env
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   SLSKD_API_KEY=your_slskd_api_key   # alternatively username/password
   ```
4. Start the containers:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```
5. Check logs (optional):
   ```bash
   docker-compose -f docker/docker-compose.yml logs -f
   ```

More configuration options (e.g., user IDs, timezone, secret keys) can be found in the [Docker Setup Guide](docker/README.md).

## Access After Startup
| Service | URL | Description |
| --- | --- | --- |
| Web App | http://localhost:8765 | Main interface for managing your music |
| API | http://localhost:8765/api | API endpoints of the application |
| API Documentation | http://localhost:8765/docs | Technical API view (optional) |
| slskd Web UI | http://localhost:5030 | Management of the Soulseek service |

## Getting Started
1. Open the web app and log in with your Spotify account to authorize playlists.
2. Configure your Soulseek access (API key or username/password).
3. Select the playlists you want to synchronize.
4. Monitor the download status and check your `mnt/music` library.

The automatic music import function periodically moves finished downloads from `mnt/downloads` to `mnt/music`. Supported formats include MP3, FLAC, M4A, and OGG.

## Documentation

### For Users
- **[Setup Guide](docs/guides/user/setup-guide.md)** - Detailed installation and configuration instructions
- **[User Guide](docs/guides/user/user-guide.md)** - Complete guide for all features
- **[Troubleshooting](docs/guides/user/troubleshooting-guide.md)** - Solutions for common problems
- **[Docker Setup Guide](docker/README.md)** - Docker-specific configuration

### For Developers
- **[Architecture](docs/project/architecture.md)** - System architecture and design
- **[Service-Agnostic Backend](docs/architecture/SERVICE_AGNOSTIC_BACKEND.md)** - Multi-service architecture (Spotify/Tidal/Deezer)
- **[Contributing](docs/project/contributing.md)** - Guidelines for contributions
- **[Backend Roadmap](docs/development/backend-roadmap.md)** - Backend development plan
- **[API Documentation](docs/api/)** - REST API reference (200 endpoints)

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                       │
│   18 Router · 200 Endpoints · HTMX/Jinja2 Templates         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                Application Layer (Services)                  │
│   20+ Services · Clean Architecture · Async/Await           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Domain Layer (Entities + Ports)                 │
│   Track · Artist · Album · Playlist │ Interface Definitions │
│   (Service-agnostic: Spotify/Tidal/Deezer ready)            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│            Infrastructure Layer (Implementations)            │
│   SpotifyClient · SQLAlchemy Repos · MusicBrainz Client     │
└─────────────────────────────────────────────────────────────┘
```

**Key Features:**
- **ISRC-based Deduplication** - Tracks are uniquely identified via International Standard Recording Code
- **Multi-Service IDs** - Entities have `spotify_uri`, `deezer_id`, `tidal_id` for cross-service compatibility
- **Service-agnostic Domain** - Same Track/Artist/Album entities for all music services

### Additional Resources
- **[CHANGELOG](docs/project/CHANGELOG.md)** - Release notes and change history
- **[Modernization Plan](docs/MODERNIZATION_PLAN.md)** - Backend modernization roadmap
- **[Complete Documentation](docs/)** - Full documentation overview

## License
The license is still being finalized and will be published before the first stable release.

---

<div align="center">

**Version:** 2.0 · **Status:** ⚠️ ACTIVE DEVELOPMENT - NOT FOR PRODUCTION ⚠️ · **Use:** Local Single-User · **Last Updated:** 2025-01-15

</div>
