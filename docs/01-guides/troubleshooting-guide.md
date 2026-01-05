# Troubleshooting Guide

**Category:** User Guide  
**Version:** 1.1  
**Last Updated:** 2025-01-27  
**Audience:** Users, Operators, Developers

---

## Quick Diagnosis

### Health Check Commands

```bash
# Check services running
docker-compose ps

# Application health
curl http://localhost:8765/health

# Readiness (includes dependencies)
curl http://localhost:8765/ready

# Recent logs
docker-compose logs --tail=50 soulspot
```

### Understanding Box-Drawing Logs (NEW!)

SoulSpot uses **Box-Drawing Character** formatted logs for task flows:

```
┌────────────────────────────────────────────────────────────┐
│  🔄 UnifiedLibraryManager - Cycle #42                       │
└────────────────────────────────────────────────────────────┘
│
├─► ARTIST_SYNC
│   ├─► ArtistService.sync_followed_artists_all_providers()
│   │   ├─► SPOTIFY: ✓ 15 fetched
│   │   └─► DEEZER: ⏭️ Skipped (disabled)
│   └─► Total: 15 fetched, 3 created
└─► ✓ ARTIST_SYNC in 2.5s
```

**Key indicators:**
- `✓` = Success
- `✗` = Error  
- `⏭️` = Skipped (provider disabled or cooldown)

👉 See [Log Analysis Guide](../10-quality/log-analysis.md) for full reference.

---

## Installation & Startup Issues

### Container Fails to Start

**Symptoms:** `docker-compose up` fails, container exits immediately, "Exited (1)" status

**Solutions:**

**1. Missing environment file**
```bash
# Check if .env exists
ls -la .env

# Create from example
cp .env.example .env
vim .env  # Edit configuration
```

**2. Port already in use**
```bash
# Check what's using port 8765
lsof -i :8765  # Linux/Mac
netstat -ano | findstr :8765  # Windows

# Change port in .env or docker-compose.yml
API_PORT=8766
```

**3. Missing directories**
```bash
# Create required directories
mkdir -p mnt/downloads mnt/music

# Set proper permissions
chmod -R 755 mnt/
```

**4. Database migration issues**
```bash
# Check logs for migration errors
docker-compose logs soulspot | grep -i migration

# Run migrations manually
docker-compose run --rm soulspot alembic upgrade head
```

---

### Permission Denied Errors

**Symptoms:** "Permission denied" in logs, cannot write to directories, file operations fail

**Solutions:**

**1. Fix directory permissions**
```bash
# Check current permissions
ls -la mnt/

# Fix ownership
sudo chown -R $(id -u):$(id -g) mnt/

# OR use PUID/PGID in docker-compose.yml
environment:
  - PUID=1000
  - PGID=1000
```

**2. SELinux issues (RHEL/CentOS)**
```bash
# Add SELinux context
chcon -Rt svirt_sandbox_file_t mnt/

# OR permissive mode (NOT recommended for production)
setenforce 0
```

---

## API & Web UI Issues

### Cannot Access Web UI

**Symptoms:** Browser "Connection refused", 502 Bad Gateway, page not loading

**Solutions:**

**1. Check service running**
```bash
docker-compose ps soulspot
docker-compose logs soulspot | tail -20
```

**2. Verify port mapping**
```bash
# Check docker port mapping
docker-compose ps

# Should show: 0.0.0.0:8765->8000/tcp
```

**3. Test with curl**
```bash
# From host
curl http://localhost:8765/health

# From inside container
docker-compose exec soulspot curl http://localhost:8000/health
```

**4. Check firewall**
```bash
# Linux
sudo iptables -L -n | grep 8765
sudo ufw status

# Allow port if needed
sudo ufw allow 8765/tcp
```

---

### 500 Internal Server Error

**Symptoms:** HTTP 500 errors, stack traces in logs, API calls failing

**Diagnosis:**
```bash
# Check recent errors
docker-compose logs soulspot | grep ERROR | tail -20

# Check with correlation ID (from error page)
docker-compose logs soulspot | grep "correlation_id:YOUR_ID"
```

**Solutions:**

**1. Database connection issues**
```bash
# Restart database (PostgreSQL)
docker-compose restart postgres

# Check database file (SQLite)
ls -la soulspot.db
sqlite3 soulspot.db "PRAGMA integrity_check;"
```

**2. Missing dependencies**
```bash
# Rebuild container
docker-compose build --no-cache soulspot
docker-compose up -d soulspot
```

**3. Configuration errors**
```bash
# Validate .env file
docker-compose config

# Check for syntax errors
docker-compose logs soulspot | grep -i "config\|setting"
```

---

## Authentication Issues

### Spotify OAuth Not Working

**Symptoms:** "Invalid client" error, redirect loop, cannot authorize

**Solutions:**

**1. Check Spotify credentials**
```bash
# Verify in .env
cat .env | grep SPOTIFY

# Must have:
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8765/api/auth/callback
```

**2. Verify Spotify app settings**
- Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- Check "Redirect URIs" matches your `SPOTIFY_REDIRECT_URI`
- Ensure app not in development mode (if needed)

**3. Clear browser cache/cookies**
- Delete cookies for `localhost:8765`
- Try in incognito/private mode

**4. Check redirect URI**
- Must **exactly** match Spotify app settings
- Including protocol (http/https) and port

---

### Session Expires Too Quickly

**Symptoms:** Logged out frequently, "Session expired" messages

**Solution:**
```bash
# Adjust session timeout in .env
SESSION_LIFETIME=3600  # seconds (1 hour)

# Restart
docker-compose restart soulspot
```

---

## Download Issues

### Downloads Stuck in QUEUED

**Symptoms:** Downloads never start, status remains "QUEUED", no progress

**Solutions:**

**1. Check slskd connection**
```bash
# Test slskd directly (running on host)
curl http://localhost:5030/health

# Note: slskd not in Docker, check host logs
```

**2. Verify slskd credentials**
```bash
# In .env (slskd runs on host, use host.docker.internal)
SLSKD_URL=http://host.docker.internal:5030
SLSKD_USERNAME=admin
SLSKD_PASSWORD=your_password

# Restart after changes
docker-compose restart soulspot
```

**3. Check worker status**
```bash
# Look for worker logs
docker-compose logs soulspot | grep -i worker

# Restart service
docker-compose restart soulspot
```

**4. Manual retry**
```bash
# Via API
curl -X POST http://localhost:8765/api/v1/downloads/{download_id}/retry
```

---

### Downloads Fail "No Sources Found"

**Symptoms:** Downloads immediately fail, "No sources found" error, search returns nothing

**Solutions:**

**1. Check slskd network connection**
```bash
# Open slskd UI
firefox http://localhost:5030

# Check "Connected" status in slskd
# Verify username/password in slskd settings
```

**2. Try different search terms**
- Artist name may not match exactly
- Try searching manually in slskd UI first

**3. Check slskd privileges**
- Some users require privileges
- Wait for privileges or try different users

---

### Downloaded Files Wrong Format

**Symptoms:** Expected FLAC but got MP3, quality not as requested

**Solution:**
```bash
# Check quality preference in request
# API call should include quality parameter
curl -X POST "http://localhost:8765/api/v1/tracks/{track_id}/download?quality=best"

# Quality options: best, good, any
# "best" prefers FLAC > 320kbps MP3 > 256kbps > lower
```

---

## Database Issues

### Database Locked (SQLite)

**Symptoms:** "Database is locked" errors, slow queries, timeouts

**Solutions:**

**1. Check for multiple processes**
```bash
# Find processes accessing database
lsof soulspot.db

# Stop other processes
docker-compose down
docker-compose up -d
```

**2. Increase timeout**
```bash
# In .env
DATABASE_TIMEOUT=30

# Restart
docker-compose restart soulspot
```

**3. Switch to PostgreSQL (production)**
- SQLite not recommended for high concurrency
- See [Docker Setup Guide](../../docker/README.md)

---

### Migration Failures

**Symptoms:** "Migration failed" errors, schema mismatch, "Table already exists"

**Solutions:**

**1. Check migration status**
```bash
docker-compose exec soulspot alembic current
docker-compose exec soulspot alembic history
```

**2. Run migrations**
```bash
# Upgrade to latest
docker-compose exec soulspot alembic upgrade head

# If fails, check logs
docker-compose exec soulspot alembic upgrade head 2>&1 | tee migration.log
```

**3. Reset database (⚠️ LOSES DATA)**
```bash
# Stop service
docker-compose down

# Backup first!
cp soulspot.db soulspot.db.backup

# Remove database
rm soulspot.db

# Restart (will recreate)
docker-compose up -d
```

---

## Metadata & Integration Issues

### MusicBrainz Lookups Failing

**Symptoms:** "MusicBrainz error" in logs, metadata not enriched, 503 errors

**Solutions:**

**1. Check rate limiting**
```bash
# MusicBrainz allows 1 request/second
# Check if hitting rate limits
docker-compose logs soulspot | grep -i "musicbrainz.*429\|rate limit"
```

**2. Verify circuit breaker status**
```bash
# Check readiness endpoint
curl http://localhost:8765/ready | jq '.checks.circuit_breakers.musicbrainz'
```

**3. Wait and retry**
- Circuit breaker auto-resets after timeout
- Default timeout: 60 seconds
- OR restart: `docker-compose restart soulspot`

**4. Configure MusicBrainz contact**
```bash
# In .env
MUSICBRAINZ_CONTACT=your@email.com

# Restart
docker-compose restart soulspot
```

---

### Album Artwork Not Downloading

**Symptoms:** Missing cover art, broken image links, "Artwork not found"

**Solutions:**

**1. Check artwork directory**
```bash
# Verify exists + writable
ls -la mnt/artwork/
mkdir -p mnt/artwork
chmod 755 mnt/artwork
```

**2. Check CoverArtArchive API**
```bash
# Test manually (requires MusicBrainz release ID)
curl "https://coverartarchive.org/release/{mbid}"
```

**3. Retry metadata enrichment**
```bash
# Via API
curl -X POST "http://localhost:8765/api/v1/tracks/{track_id}/enrich?force_refresh=true"
```

---

## Performance Issues

### Slow Response Times

**Symptoms:** Pages load slowly, API timeouts, high latency

**Diagnosis:**
```bash
# Check resource usage
docker stats soulspot

# Check database performance
docker-compose logs soulspot | grep -i "slow query"

# Check active downloads
curl http://localhost:8765/api/v1/downloads | jq 'length'
```

**Solutions:**

**1. Restart services**
```bash
docker-compose restart
```

**2. Check disk space**
```bash
df -h ./mnt
# Clean up if needed
find ./mnt/downloads -type f -mtime +30 -delete
```

**3. Increase resources (docker-compose.yml)**
```yaml
services:
  soulspot:
    mem_limit: 2g
    cpus: '2.0'
```

**4. Enable caching**
```bash
# In .env
CACHE_ENABLED=true
CACHE_TTL=3600
```

---

### High Memory Usage

**Symptoms:** OOM errors, container restarts, system slowdown

**Solutions:**

**1. Check memory usage**
```bash
docker stats soulspot
free -h
```

**2. Restart service**
```bash
docker-compose restart soulspot
```

**3. Limit concurrent downloads**
```bash
# In .env
MAX_CONCURRENT_DOWNLOADS=2

# Restart
docker-compose restart soulspot
```

**4. Add swap space (if needed)**
```bash
# Linux
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## UI/UX Issues

### UI Not Loading / Blank Page

**Symptoms:** White/blank page, console errors, missing CSS/JS

**Solutions:**

**1. Check static files**
```bash
# Verify static directory exists
ls -la src/soulspot/static/

# Rebuild CSS if using Tailwind
cd /path/to/soulspot
npm run build:css
```

**2. Clear browser cache**
- Hard refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
- Clear browser cache completely

**3. Check browser console**
- Open DevTools (F12)
- Console tab for JavaScript errors
- Network tab for failed requests

---

### Layout Broken / CSS Issues

**Symptoms:** Unstyled content, broken layout, missing styles

**Solutions:**

**1. Rebuild CSS**
```bash
# If using Tailwind CSS
npm install
npm run build:css

# Restart service
docker-compose restart soulspot
```

**2. Check static file serving**
```bash
# Test static file access
curl http://localhost:8765/static/css/style.css
```

**3. Rebuild container**
```bash
docker-compose build --no-cache soulspot
docker-compose up -d soulspot
```

---

## Debugging Tips

### Enable Debug Logging

```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG
OBSERVABILITY_LOG_JSON_FORMAT=false  # Easier to read

# Restart
docker-compose restart soulspot
```

### Use Correlation IDs

```bash
# Find correlation ID for request
docker-compose logs soulspot | grep "correlation_id"

# Search logs by correlation ID
docker-compose logs soulspot | grep "correlation_id:abc-123-def"
```

### Log Analysis

**Common Error Patterns:**

| Error | Likely Cause | Solution |
|-------|--------------|----------|
| `Connection refused` | Service not running | `docker-compose up -d` |
| `Database locked` | SQLite concurrency | Use PostgreSQL or restart |
| `429 Too Many Requests` | Rate limiting | Wait, then retry |
| `401 Unauthorized` | Invalid credentials | Check .env configuration |
| `503 Service Unavailable` | External API down | Check status, retry later |
| `Circuit breaker OPEN` | Too many failures | Wait for auto-reset or restart |

**Log Filtering:**
```bash
# Only errors
docker-compose logs soulspot | grep ERROR

# Specific time range
docker-compose logs --since 2h soulspot

# Specific component
docker-compose logs soulspot | grep "spotify\|musicbrainz\|slskd"
```

---

## Getting Help

**Before asking for help, collect:**

**1. System info:**
```bash
docker --version
docker-compose --version
uname -a  # Linux/Mac
```

**2. Recent logs:**
```bash
docker-compose logs --tail=100 soulspot > logs.txt
```

**3. Configuration (redact secrets):**
```bash
cat .env | sed 's/=.*/=REDACTED/' > config.txt
```

**4. Health check:**
```bash
curl http://localhost:8765/health > health.json
curl http://localhost:8765/ready > ready.json
```

**Where to get help:**
- **GitHub Issues:** [Report Bugs](https://github.com/bozzfozz/soulspot/issues)
- **Documentation:** [Guides & Reference](../../)
- **Health Checks:** `http://localhost:8765/health`

---

## Related Documentation

- [Setup Guide](./setup-guide.md) - Installation instructions
- [User Guide](./user-guide.md) - Feature documentation
- [Spotify Auth Troubleshooting](./spotify-auth-troubleshooting.md) - OAuth issues
- [API Documentation](/api/endpoints/) - REST API reference

---

**Version:** 1.0  
**Last Updated:** 2025-01
