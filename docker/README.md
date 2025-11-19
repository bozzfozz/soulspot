# Docker Setup Guide

> 🐳 Complete guide for running SoulSpot Bridge with Docker Compose

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Directory Structure](#directory-structure)
- [Environment Configuration](#environment-configuration)
- [Starting the Application](#starting-the-application)
- [Accessing the Services](#accessing-the-services)
- [Auto Music Import](#auto-music-import)
- [File Permissions](#file-permissions)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:

- **Docker** (version 20.10+)
- **Docker Compose** (version 2.0+)
- **slskd running on your host machine** (not in Docker)
  - Download and install from: https://github.com/slskd/slskd
  - Configure it to run on port 5030 (default)
  - Ensure it's accessible from Docker containers
- **Spotify API Credentials** (Client ID and Secret)
  - Get them from: https://developer.spotify.com/dashboard
- **slskd API Key or credentials**

### Verify Docker Installation

```bash
docker --version
docker-compose -f docker/docker-compose.yml --version
```

---

## Directory Structure

SoulSpot Bridge requires a specific directory structure for bind mounts:

```
your-project/
├── docker/
│   ├── docker-compose.yml      # Main compose file for local use
│   ├── Dockerfile              # Docker image definition
│   ├── docker-entrypoint.sh    # Container startup script
│   └── README.md               # This file
├── .env
├── mnt/
│   ├── downloads/      # Downloads from slskd (must exist before starting)
│   ├── music/          # Final music library (must exist before starting)
│   └── soulspot/       # SoulSpot config (auto-created)
│       ├── soulspot.db
│       ├── artwork/
│       └── tmp/
```

**Note:** The `slskd` directories are not needed in the `mnt/` folder since slskd runs on the host machine, not in Docker.

### Creating Required Directories

**Important:** The `/downloads` and `/music` directories **must exist** on the host before starting the container, or the application will fail to start with an error message.

```bash
# Create required directories
mkdir -p mnt/downloads
mkdir -p mnt/music
```

The `/config` directory (`mnt/soulspot`) will be automatically created by the container at startup.

---

## Environment Configuration

### 1. Copy the Example Environment File

```bash
cp .env.example .env
```

### 2. Configure Required Variables

Edit the `.env` file and set the following **required** variables:

#### Spotify Configuration

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/api/v1/auth/callback
```

#### slskd Configuration

**Important:** slskd must be running on your host machine before starting SoulSpot Bridge.

```env
# For Docker on Windows/Mac (use host.docker.internal)
SLSKD_BASE_URL=http://host.docker.internal:5030
SLSKD_API_KEY=your_slskd_api_key_here
```

For Linux, you may need to use your host IP address instead:
```env
# For Docker on Linux (use host IP, e.g., 192.168.1.100)
SLSKD_BASE_URL=http://192.168.1.100:5030
SLSKD_API_KEY=your_slskd_api_key_here
```

Or if using username/password:

```env
SLSKD_BASE_URL=http://host.docker.internal:5030
SLSKD_USERNAME=admin
SLSKD_PASSWORD=your_password_here
```

### 3. Optional Configuration

#### User and Group IDs (File Permissions)

```env
PUID=1000  # Your user ID (use `id -u` to find yours)
PGID=1000  # Your group ID (use `id -g` to find yours)
UMASK=002  # File creation mask
```

#### Timezone

```env
TZ=Europe/Berlin  # Your timezone (e.g., America/New_York, UTC)
```

#### Security

```env
SECRET_KEY=generate-a-random-secret-key-here
```

Generate a secure secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Complete Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PUID` | No | `1000` | User ID for file permissions |
| `PGID` | No | `1000` | Group ID for file permissions |
| `UMASK` | No | `002` | File creation mask |
| `TZ` | No | `UTC` | Timezone |
| `SPOTIFY_CLIENT_ID` | Yes | - | Spotify OAuth Client ID |
| `SPOTIFY_CLIENT_SECRET` | Yes | - | Spotify OAuth Client Secret |
| `SPOTIFY_REDIRECT_URI` | No | `http://127.0.0.1:8765/api/v1/auth/callback` | OAuth redirect URI |
| `SLSKD_BASE_URL` | Yes | - | slskd base URL |
| `SLSKD_API_KEY` | Yes* | - | slskd API key |
| `SLSKD_USERNAME` | Yes* | `admin` | slskd username (if no API key) |
| `SLSKD_PASSWORD` | Yes* | - | slskd password (if no API key) |
| `SECRET_KEY` | No | (default) | Application secret key |
| `DEBUG` | No | `false` | Enable debug mode |
| `LOG_LEVEL` | No | `INFO` | Logging level |

\*Either `SLSKD_API_KEY` or both `SLSKD_USERNAME` and `SLSKD_PASSWORD` are required.

---

## Starting the Application

### 1. Build and Start Services

```bash
# Build and start in detached mode
docker-compose -f docker/docker-compose.yml up -d --build

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# View logs for specific service
docker-compose -f docker/docker-compose.yml logs -f soulspot
```

### 2. Verify Services are Running

```bash
# Check service status
docker-compose -f docker/docker-compose.yml ps

# Expected output:
# NAME                  STATUS              PORTS
# soulspot-bridge       Up (healthy)        0.0.0.0:8765->8765/tcp
```

### 3. Check Health Status

```bash
# SoulSpot Bridge health
curl http://localhost:8765/health

# slskd health (running on host)
curl http://localhost:5030/health
```

---

## Accessing the Services

Once the services are running:

| Service | URL | Description |
|---------|-----|-------------|
| **SoulSpot Bridge** | http://localhost:8765 | Main application |
| **SoulSpot API Docs** | http://localhost:8765/docs | Interactive API documentation |
| **SoulSpot UI** | http://localhost:8765/ui | Web interface |
| **slskd Web UI** | http://localhost:5030 | Soulseek daemon interface (running on host) |

---

## Auto Music Import

SoulSpot Bridge includes an **automatic music import feature** that moves completed downloads from the `/downloads` directory to the `/music` library.

### How It Works

1. **Monitoring:** The service scans the `/downloads` directory every 60 seconds
2. **File Detection:** Identifies completed audio files (MP3, FLAC, M4A, etc.)
3. **Validation:** Ensures files are complete and not being written
4. **Import:** Moves files to `/music` preserving directory structure
5. **Cleanup:** Removes empty directories from `/downloads`

### Supported Audio Formats

- MP3 (`.mp3`)
- FLAC (`.flac`)
- M4A/AAC (`.m4a`, `.aac`)
- OGG Vorbis (`.ogg`)
- Opus (`.opus`)
- WAV (`.wav`)
- WMA (`.wma`)
- APE (`.ape`)
- ALAC (`.alac`)

### File Completion Detection

A file is considered "complete" when:

1. File size is greater than 0 bytes
2. File hasn't been modified in the last 5 seconds
3. File is readable

This ensures that only fully downloaded files are moved to the music library.

### Configuration

The auto-import service is enabled by default with these settings:

- **Poll Interval:** 60 seconds
- **Download Path:** `/downloads` (mapped to `./mnt/downloads`)
- **Music Path:** `/music` (mapped to `./mnt/music`)

To adjust the poll interval, you can modify the `main.py` file or set it via environment variable (future enhancement).

### Logs

Monitor the auto-import service:

```bash
docker-compose -f docker/docker-compose.yml logs -f soulspot | grep -i "auto-import\|importing"
```

---

## File Permissions

### Understanding PUID and PGID

SoulSpot Bridge runs with the user and group IDs specified by `PUID` and `PGID`. This ensures that files created by the container have the correct ownership on the host system.

### Finding Your IDs

```bash
# Get your user ID
id -u

# Get your group ID
id -g
```

### Setting Permissions

The container automatically:

1. Updates the internal user/group to match `PUID`/`PGID`
2. Sets ownership of `/config` directory
3. Applies the `UMASK` for new files

### Fixing Permission Issues

If you encounter permission errors:

```bash
# Fix ownership of all directories
sudo chown -R 1000:1000 mnt/

# Or use your specific user:
sudo chown -R $(id -u):$(id -g) mnt/
```

---

## Troubleshooting

### Container Fails to Start

**Error:** "ERROR: /downloads directory does not exist!"

**Solution:**

```bash
# Create the required directories
mkdir -p mnt/downloads mnt/music
```

**Error:** "ERROR: /music directory does not exist!"

**Solution:**

```bash
# Create the required directories
mkdir -p mnt/downloads mnt/music
```

### Permission Denied Errors

**Solution:**

1. Check your `PUID` and `PGID` settings in `.env`
2. Ensure they match your host user:

```bash
echo "PUID=$(id -u)" >> .env
echo "PGID=$(id -g)" >> .env
```

3. Restart the container:

```bash
docker-compose -f docker/docker-compose.yml down
docker-compose -f docker/docker-compose.yml up -d
```

### Database Issues

**Error:** "Database file locked" or "Unable to open database"

**Solution:**

1. Stop all containers:

```bash
docker-compose -f docker/docker-compose.yml down
```

2. Fix database file permissions:

```bash
sudo chown -R $(id -u):$(id -g) mnt/soulspot/
```

3. Restart:

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### Auto-Import Not Working

**Check logs:**

```bash
docker-compose -f docker/docker-compose.yml logs -f soulspot | grep -i "auto-import"
```

**Common issues:**

1. **No files detected:** Ensure files are in `/downloads` (mapped to `mnt/downloads`)
2. **Permission errors:** Check `PUID`/`PGID` settings
3. **Files not complete:** Wait for downloads to finish (5+ seconds of no modification)

### Viewing Container Logs

```bash
# All services (only SoulSpot Bridge in Docker)
docker-compose -f docker/docker-compose.yml logs -f

# SoulSpot service
docker-compose -f docker/docker-compose.yml logs -f soulspot

# Last 100 lines
docker-compose -f docker/docker-compose.yml logs --tail=100 soulspot
```

**Note:** slskd logs are not available through docker-compose since it runs on the host. Check slskd's own logs in its installation directory.

### Restarting Services

```bash
# Restart all services
docker-compose -f docker/docker-compose.yml restart

# Restart specific service
docker-compose -f docker/docker-compose.yml restart soulspot

# Stop all services
docker-compose -f docker/docker-compose.yml down

# Stop and remove volumes
docker-compose -f docker/docker-compose.yml down -v
```

### Rebuilding After Code Changes

```bash
# Rebuild and restart
docker-compose -f docker/docker-compose.yml up -d --build

# Force rebuild without cache
docker-compose -f docker/docker-compose.yml build --no-cache
docker-compose -f docker/docker-compose.yml up -d
```

---

## Advanced Configuration

> **Hinweis:** Funktionen/Instruktionen zu PostgreSQL, Redis, nginx und externen Datenbankdiensten wurden entfernt, da SoulSpot als lokaler Dienst im privaten Netzwerk mit SQLite betrieben wird und nicht über das Internet erreichbar sein soll.

### Custom Port Mapping

To change the application port, edit `docker-compose.yml`:

```yaml
services:
  soulspot:
    ports:
      - "8080:8765"  # Map host port 8080 to container port 8765
```

### Volume Backups

Backup your data regularly:

```bash
# Backup SoulSpot config
tar -czf soulspot-backup-$(date +%Y%m%d).tar.gz mnt/soulspot/

# Backup everything
tar -czf full-backup-$(date +%Y%m%d).tar.gz mnt/
```

---

## Deployment Notes

This application is designed for **local single-user use**:

- No multi-environment setups (development/staging/production)
- No HTTPS/SSL configuration needed (local-only)
- No secure cookies configuration (local network only)
- SQLite database for simplicity
- All services run on localhost

### Checklist Before Running

- [ ] Set a strong `SECRET_KEY`
- [ ] Configure proper `PUID`/`PGID` for your system
- [ ] Set `DEBUG=false` for less verbose logging
- [ ] Set up regular backups of `/config` directory
- [ ] Ensure `/downloads` and `/music` exist before starting

---

## Next Steps

- Read the [Setup Guide](setup-guide.md) for development setup
- Check the [Contributing Guide](contributing.md) to contribute
- Review the [Architecture Guide](architecture.md) to understand the codebase

---

**Need Help?**

- Check the [GitHub Issues](https://github.com/bozzfozz/soulspot-bridge/issues)
- Read the [FAQ](setup-guide.md#faq)
- Join our community discussions
