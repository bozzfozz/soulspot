# Setup Guide

This guide provides comprehensive instructions for setting up SoulSpot in different environments.

## Table of Contents

- [System Requirements](#system-requirements)
- [Installation Methods](#installation-methods)
- [Configuration](#configuration)
- [External Services Setup](#external-services-setup)
- [Database Setup](#database-setup)
- [Running the Application](#running-the-application)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements

- **Operating System:** Linux, macOS, or Windows (with WSL2)
- **Python:** 3.12 or higher
- **RAM:** 2GB minimum, 4GB recommended
- **Disk Space:** 10GB minimum (more for music storage)
- **Docker:** Version 20.10+ (for Docker-based setup)

### Software Dependencies

- **Git** - Version control
- **Python 3.12+** - Runtime environment
- **Docker & Docker Compose** - Container orchestration
- **Poetry** (optional) - Dependency management

---

## Installation Methods

### Method 1: Local Installation with Poetry (Recommended for Development)

**Step 1: Install Poetry**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Step 2: Clone the Repository**
```bash
git clone https://github.com/bozzfozz/soulspot.git
cd soulspot
```

**Step 3: Install Dependencies**
```bash
poetry install
```

**Step 4: Activate Virtual Environment**
```bash
poetry shell
```

**Step 5: Verify Installation**
```bash
python --version  # Should be 3.12+
poetry run pytest --version
```

---

### Method 2: Local Installation with pip

**Step 1: Clone the Repository**
```bash
git clone https://github.com/bozzfozz/soulspot.git
cd soulspot
```

**Step 2: Create Virtual Environment**
```bash
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**Step 3: Install Dependencies**
```bash
pip install -r requirements.txt
```

---

### Method 3: Docker Setup (Recommended for Production)

**Coming Soon:** Docker-based setup will be available in version 0.2.0.

---

## Configuration

### Environment Variables

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file with your configuration:**
   ```bash
   nano .env  # or use your preferred editor
   ```

### Essential Configuration

#### Application Settings
```env
APP_NAME=SoulSpot
APP_ENV=development  # or production
DEBUG=true           # Set to false in production
LOG_LEVEL=INFO       # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

#### Security
```env
# Generate a secure secret key:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=your-secure-secret-key-here
```

#### Database Configuration

**For Simple Profile (SQLite):**
```env
DATABASE_URL=sqlite+aiosqlite:///./soulspot.db
```

**For Standard Profile (PostgreSQL):**
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/soulspot
```

#### File Storage Paths
```env
DOWNLOAD_PATH=./downloads
MUSIC_PATH=./music
ARTWORK_PATH=./artwork
TEMP_PATH=./tmp
```

These directories will be created automatically if they don't exist.

---

## External Services Setup

### slskd Setup

slskd is required for Soulseek downloads.

**Step 1: Start slskd with Docker**
```bash
docker-compose -f docker/docker-compose.yml up -d slskd
```

**Step 2: Access slskd Web UI**
- URL: http://localhost:5030
- Default credentials: admin/changeme
- **Important:** Change the default password!

**Step 3: Configure slskd in `.env`**
```env
SLSKD_URL=http://localhost:5030
SLSKD_USERNAME=admin
SLSKD_PASSWORD=your-password
# Or use API key (recommended)
SLSKD_API_KEY=your-api-key
```

**Step 4: Get slskd API Key (Recommended)**
1. Log in to slskd web interface
2. Go to Settings → API
3. Generate new API key
4. Add it to your `.env` file

---

### Spotify API Setup

To import playlists from Spotify, you need API credentials.

**Step 1: Create Spotify Application**
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create an App"
4. Fill in app name and description
5. Accept terms and create

**Step 2: Get Credentials**
1. In your app dashboard, click "Settings"
2. Copy **Client ID** and **Client Secret**
3. Add Redirect URI: `http://localhost:8000/auth/spotify/callback`
4. Save settings

**Step 3: Configure in `.env`**
```env
SPOTIFY_CLIENT_ID=your-client-id-here
SPOTIFY_CLIENT_SECRET=your-client-secret-here
SPOTIFY_REDIRECT_URI=http://localhost:8000/auth/spotify/callback
```

---

### MusicBrainz Configuration

MusicBrainz is used for metadata enrichment. No API key required, but you should identify your app.

**Configure in `.env`:**
```env
MUSICBRAINZ_APP_NAME=SoulSpot
MUSICBRAINZ_APP_VERSION=0.1.0
MUSICBRAINZ_CONTACT=your-email@example.com
```

---

## Database Setup

### SQLite (Simple Profile)

**Automatic Setup:**
SQLite database is created automatically on first run.

**Manual Initialization:**
```bash
# Run migrations
poetry run alembic upgrade head

# Or using make
make db-upgrade
```

**Database Location:**
The SQLite database file is created at `./soulspot.db` by default.

---

### PostgreSQL (Standard Profile)

**Step 1: Install PostgreSQL**

**On Ubuntu/Debian:**
```bash
sudo apt-get install postgresql postgresql-contrib
```

**On macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Step 2: Create Database**
```bash
sudo -u postgres psql
```

In the PostgreSQL shell:
```sql
CREATE DATABASE soulspot;
CREATE USER soulspot WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE soulspot TO soulspot;
\q
```

**Step 3: Update `.env`**
```env
DATABASE_URL=postgresql+asyncpg://soulspot:your-password@localhost:5432/soulspot
```

**Step 4: Run Migrations**
```bash
poetry run alembic upgrade head
```

---

## Running the Application

### Development Mode

**Method 1: Using Make**
```bash
make dev
```

**Method 2: Using Uvicorn directly**
```bash
poetry run uvicorn soulspot.main:app --reload --host 0.0.0.0 --port 8000
```

**Method 3: Using Python**
```bash
poetry run python -m soulspot.main
```

### Access the Application

Once running, access:
- **Web UI:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Alternative API Docs:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

---

### Production Mode

**Important:** See [Development Roadmap](../../development/backend-roadmap.md) - Production setup will be fully documented in Phase 6.

**Basic Production Command:**
```bash
poetry run uvicorn soulspot.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Production Checklist:**
- [ ] Set `APP_ENV=production`
- [ ] Set `DEBUG=false`
- [ ] Use secure `SECRET_KEY`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Configure proper logging
- [ ] Set up reverse proxy (nginx)
- [ ] Enable HTTPS
- [ ] Configure firewall
- [ ] Set up monitoring

---

## Troubleshooting

### Common Issues

#### Issue: "ModuleNotFoundError: No module named 'soulspot'"

**Solution:**
```bash
# Ensure you're in the project directory
cd /path/to/soulspot

# Reinstall dependencies
poetry install
# or
pip install -r requirements.txt
```

---

#### Issue: "Database is locked" (SQLite)

**Solution:**
- SQLite doesn't handle concurrent writes well
- Use PostgreSQL for production
- Ensure no other process is accessing the database
- Check file permissions on `soulspot.db`

---

#### Issue: "Connection refused" when connecting to slskd

**Solution:**
```bash
# Check if slskd is running
docker ps | grep slskd

# Start slskd if not running
docker-compose -f docker/docker-compose.yml up -d slskd

# Check slskd logs
docker-compose -f docker/docker-compose.yml logs slskd

# Verify URL in .env matches container port
SLSKD_URL=http://localhost:5030
```

---

#### Issue: Spotify OAuth "Invalid redirect URI"

**Solution:**
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Open your app settings
3. Under "Redirect URIs", add exactly: `http://localhost:8000/auth/spotify/callback`
4. Make sure it matches your `.env` file
5. Click "Save"

---

#### Issue: "alembic.util.exc.CommandError: Can't locate revision identified by"

**Solution:**
```bash
# Reset migrations (WARNING: This will drop all data)
poetry run alembic downgrade base
poetry run alembic upgrade head

# Or delete the database and start fresh
rm soulspot.db
poetry run alembic upgrade head
```

---

#### Issue: Port 8000 already in use

**Solution:**
```bash
# Find and kill the process using port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
poetry run uvicorn soulspot.main:app --reload --port 8001
```

---

### Getting Help

If you encounter issues not covered here:

1. **Check existing issues:** [GitHub Issues](https://github.com/bozzfozz/soulspot/issues)
2. **Review logs:** Check application logs for error messages
3. **Enable debug mode:** Set `DEBUG=true` in `.env` for verbose logging
4. **Create an issue:** Use our [Bug Report template](../.github/ISSUE_TEMPLATE/bug_report.md)

---

## Next Steps

After successful setup:

1. **Test the installation:** Run `make test` to verify everything works
2. **Explore the API:** Visit http://localhost:8000/docs
3. **Import your first playlist:** Use the web UI or API
4. **Read the documentation:** Check out [Architecture](architecture.md) and [Contributing](contributing.md)

---

**Setup complete! 🎉 Enjoy using SoulSpot!**
