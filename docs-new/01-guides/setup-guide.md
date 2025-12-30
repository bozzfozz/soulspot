# Setup Guide

**Category:** User Guide  
**Version:** 1.0  
**Last Updated:** 2025-01  
**Audience:** Users, System Administrators

---

## System Requirements

### Minimum Requirements
- **OS:** Linux, macOS, Windows (with WSL2)
- **Python:** 3.12+
- **RAM:** 2GB minimum, 4GB recommended
- **Disk:** 10GB minimum (more for music storage)
- **Docker:** Version 20.10+ (for Docker setup)

### Software Dependencies
- **Git** - Version control
- **Python 3.12+** - Runtime
- **Docker & Docker Compose** - Container orchestration
- **Poetry** (optional) - Dependency management

---

## Installation Methods

### Method 1: Local Installation with Poetry (Development)

**Step 1: Install Poetry**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Step 2: Clone Repository**
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

**Step 1: Clone Repository**
```bash
git clone https://github.com/bozzfozz/soulspot.git
cd soulspot
```

**Step 2: Create Virtual Environment**
```bash
python3.12 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

**Step 3: Install Dependencies**
```bash
pip install -r requirements.txt
```

---

### Method 3: Docker Setup (Production)

**Coming Soon:** Docker-based setup available in version 0.2.0

---

## Configuration

### Environment Variables

**Copy example file:**
```bash
cp .env.example .env
```

**Edit with your configuration:**
```bash
nano .env  # or your preferred editor
```

---

### Essential Configuration

#### Application Settings
```env
APP_NAME=SoulSpot
APP_ENV=development  # or production
DEBUG=true           # false in production
LOG_LEVEL=INFO       # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

#### Security
```env
# Generate secure secret key:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=your-secure-secret-key-here
```

#### Database Configuration

**Simple Profile (SQLite):**
```env
DATABASE_URL=sqlite+aiosqlite:///./soulspot.db
```

**Standard Profile (PostgreSQL):**
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

*Directories created automatically if missing*

---

## External Services Setup

### slskd Setup

slskd required for Soulseek downloads.

**Step 1: Start slskd with Docker**
```bash
docker-compose -f docker/docker-compose.yml up -d slskd
```

**Step 2: Access slskd Web UI**
- **URL:** `http://localhost:5030`
- **Default:** `admin/changeme`
- **⚠️ Important:** Change default password!

**Step 3: Configure slskd in .env**
```env
SLSKD_URL=http://localhost:5030
SLSKD_USERNAME=admin
SLSKD_PASSWORD=your-password
# OR use API key (recommended)
SLSKD_API_KEY=your-api-key
```

**Step 4: Get slskd API Key (Recommended)**
1. Login to slskd web interface
2. Settings → API
3. Generate new API key
4. Add to `.env` file

---

### Spotify API Setup

**Step 1: Create Spotify Application**
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Login with Spotify account
3. Click "Create an App"
4. Fill in app name + description
5. Accept terms → Create

**Step 2: Get Credentials**
1. In app dashboard → "Settings"
2. Copy **Client ID** and **Client Secret**
3. Add Redirect URI: `http://localhost:8000/api/auth/callback`
4. Save settings

**Step 3: Configure in .env**
```env
SPOTIFY_CLIENT_ID=your-client-id-here
SPOTIFY_CLIENT_SECRET=your-client-secret-here
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

---

### MusicBrainz Configuration

MusicBrainz for metadata enrichment (no API key required).

**Configure in .env:**
```env
MUSICBRAINZ_APP_NAME=SoulSpot
MUSICBRAINZ_APP_VERSION=0.1.0
MUSICBRAINZ_CONTACT=your-email@example.com
```

---

## Database Setup

### SQLite (Simple Profile)

**Automatic:** SQLite created on first run.

**Manual Initialization:**
```bash
# Run migrations
poetry run alembic upgrade head

# OR using make
make db-upgrade
```

**Database Location:** `./soulspot.db` (default)

---

### PostgreSQL (Standard Profile)

**Step 1: Install PostgreSQL**

**Ubuntu/Debian:**
```bash
sudo apt-get install postgresql postgresql-contrib
```

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Step 2: Create Database**
```bash
sudo -u postgres psql
```

In PostgreSQL shell:
```sql
CREATE DATABASE soulspot;
CREATE USER soulspot WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE soulspot TO soulspot;
\q
```

**Step 3: Update .env**
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

**Method 2: Using Uvicorn**
```bash
poetry run uvicorn soulspot.main:app --reload --host 0.0.0.0 --port 8000
```

**Method 3: Using Python**
```bash
poetry run python -m soulspot.main
```

---

### Access Application

- **Web UI:** `http://localhost:8000`
- **API Docs:** `http://localhost:8000/docs`
- **Alternative Docs:** `http://localhost:8000/redoc`
- **Health Check:** `http://localhost:8000/health`

---

### Production Mode

**Basic Production Command:**
```bash
poetry run uvicorn soulspot.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Production Checklist:**
- [ ] Set `APP_ENV=production`
- [ ] Set `DEBUG=false`
- [ ] Use secure `SECRET_KEY`
- [ ] Use PostgreSQL (not SQLite)
- [ ] Configure proper logging
- [ ] Set up reverse proxy (nginx)
- [ ] Enable HTTPS
- [ ] Configure firewall
- [ ] Set up monitoring

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'soulspot'"

**Solution:**
```bash
cd /path/to/soulspot
poetry install  # OR pip install -r requirements.txt
```

---

### "Database is locked" (SQLite)

**Solution:**
- SQLite doesn't handle concurrent writes well
- Use PostgreSQL for production
- Ensure no other process accessing database
- Check file permissions on `soulspot.db`

---

### "Connection refused" (slskd)

**Solution:**
```bash
# Check if slskd running
docker ps | grep slskd

# Start slskd if not running
docker-compose -f docker/docker-compose.yml up -d slskd

# Check slskd logs
docker-compose -f docker/docker-compose.yml logs slskd

# Verify URL in .env matches container port
SLSKD_URL=http://localhost:5030
```

---

### Spotify OAuth "Invalid redirect URI"

**Solution:**
1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Open app settings
3. Add Redirect URI: `http://localhost:8000/api/auth/callback`
4. **Must match .env file exactly**
5. Click "Save"

---

### "Can't locate revision identified by" (alembic)

**Solution:**
```bash
# Reset migrations (⚠️ Drops all data)
poetry run alembic downgrade base
poetry run alembic upgrade head

# OR delete database + start fresh
rm soulspot.db
poetry run alembic upgrade head
```

---

### Port 8000 already in use

**Solution:**
```bash
# Find and kill process using port 8000
lsof -ti:8000 | xargs kill -9

# OR use different port
poetry run uvicorn soulspot.main:app --reload --port 8001
```

---

## Getting Help

- **GitHub Issues:** [Report Bugs](https://github.com/bozzfozz/soulspot/issues)
- **Review Logs:** Check application logs for errors
- **Enable Debug:** Set `DEBUG=true` in `.env` for verbose logging
- **Create Issue:** Use Bug Report template

---

## Next Steps

After successful setup:

1. **Test Installation:** `make test` to verify
2. **Explore API:** Visit `http://localhost:8000/docs`
3. **Import First Playlist:** Use web UI or API
4. **Read Documentation:** Check Architecture and Contributing guides

---

**Setup complete! 🎉 Enjoy using SoulSpot!**
