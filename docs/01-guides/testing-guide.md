# Testing Guide

**Category:** Developer Guide  
**Version:** 1.0  
**Last Updated:** 2025-01  
**Audience:** Developers

---

## Overview

**⚠️ CRITICAL: NO AUTOMATED TESTS - LIVE TESTING ONLY**

SoulSpot uses **live testing in Docker environment** - NO automated tests (unit/integration/e2e).

**Testing Policy:**
- ❌ NO pytest tests
- ❌ NO test automation
- ✅ ALL testing done manually via UI/API
- ✅ User validates changes after each deployment

---

## Testing Strategy

### Manual Testing Workflow

**After code changes:**
1. Deploy to Docker environment (`docker-compose up --build`)
2. Access application via browser (`http://localhost:8765`)
3. Test affected features manually via UI
4. Test API endpoints via Postman/curl
5. Verify database changes via SQLite browser
6. Check logs for errors (`docker-compose logs -f soulspot`)

### Test Checklist

**For UI changes:**
- [ ] Test in Chrome/Firefox/Safari
- [ ] Test responsive design (mobile/tablet/desktop)
- [ ] Verify HTMX interactions work
- [ ] Check accessibility (keyboard navigation)

**For API changes:**
- [ ] Test happy path scenarios
- [ ] Test error handling (invalid input, missing auth)
- [ ] Verify response format matches DTO schemas
- [ ] Check status codes correct

**For database changes:**
- [ ] Run migration (`alembic upgrade head`)
- [ ] Verify schema matches Entity/Model definitions
- [ ] Test CRUD operations via API
- [ ] Check data integrity constraints

---

## Development Tools

### Running Locally

```bash
# Start development server
make dev

# OR using poetry
poetry run uvicorn soulspot.main:app --reload --host 0.0.0.0 --port 8000
```

### Database Operations

```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Check migration status
alembic current
alembic history
```

### Code Quality Checks

**MUST pass before deployment:**

```bash
# Lint check
ruff check . --config pyproject.toml

# Type check
mypy --config-file mypy.ini src/

# Security scan
bandit -r src/

# Format check
ruff format --check .
```

**Auto-fix:**
```bash
# Auto-fix lint issues
ruff check . --fix

# Auto-format code
ruff format .
```

---

## API Testing

### Using curl

**Authentication:**
```bash
# Connect Spotify
open http://localhost:8000/api/auth/authorize

# Check session
curl http://localhost:8000/api/auth/session
```

**Playlists:**
```bash
# List playlists
curl http://localhost:8000/api/playlists

# Get playlist details
curl http://localhost:8000/api/playlists/{id}

# Import playlist
curl -X POST http://localhost:8000/api/playlists/import \
  -H "Content-Type: application/json" \
  -d '{"playlist_url": "spotify:playlist:..."}'
```

**Downloads:**
```bash
# List downloads
curl http://localhost:8000/api/downloads

# Queue download
curl -X POST http://localhost:8000/api/downloads \
  -H "Content-Type: application/json" \
  -d '{"track_id": "uuid-here"}'

# Pause download
curl -X POST http://localhost:8000/api/downloads/{id}/pause
```

### Using Postman

**Import Collection:**
- Visit `http://localhost:8000/docs`
- Export OpenAPI spec
- Import into Postman

**Environment Variables:**
```
BASE_URL: http://localhost:8000
SESSION_ID: <from browser cookies>
```

---

## UI Testing

### Manual Test Scenarios

**Dashboard:**
- [ ] Stats cards show correct counts
- [ ] Session status updates automatically
- [ ] Quick actions navigate correctly

**Search:**
- [ ] Autocomplete shows suggestions after 300ms
- [ ] Filters update results in real-time
- [ ] Bulk download works for multiple tracks
- [ ] Search history persists in localStorage

**Playlists:**
- [ ] Grid view loads all playlists
- [ ] Playlist detail shows all tracks
- [ ] Sync button updates from Spotify
- [ ] Export works (M3U/CSV/JSON)

**Downloads:**
- [ ] Queue displays all downloads
- [ ] Progress bars update in real-time (HTMX polling)
- [ ] Pause/Resume/Cancel actions work
- [ ] Status filters correctly

**Settings:**
- [ ] All tabs load without errors
- [ ] Form validation shows errors
- [ ] Save changes persists to database
- [ ] Reset to defaults works

---

## Debugging

### Enable Debug Mode

```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG

# Restart
docker-compose restart soulspot
```

### Check Logs

```bash
# Real-time logs
docker-compose logs -f soulspot

# Filter errors
docker-compose logs soulspot | grep ERROR

# Search by correlation ID
docker-compose logs soulspot | grep "correlation_id:abc-123"
```

### Database Inspection

```bash
# Access SQLite database
sqlite3 soulspot.db

# List tables
.tables

# Query example
SELECT * FROM playlists LIMIT 10;

# Exit
.quit
```

---

## Performance Testing

### Load Testing (Manual)

**Test concurrent downloads:**
1. Queue 10+ downloads
2. Monitor CPU/memory usage (`docker stats`)
3. Check download completion time
4. Verify no errors in logs

**Test API response times:**
```bash
# Use curl with timing
time curl http://localhost:8000/api/playlists

# Expected: < 1 second for simple queries
```

---

## Deployment Testing

### Pre-Deployment Checklist

- [ ] All code quality checks pass (ruff, mypy, bandit)
- [ ] Manual testing completed for affected features
- [ ] Database migrations tested
- [ ] No errors in logs during manual testing
- [ ] CHANGELOG.md updated
- [ ] poetry.lock in sync with pyproject.toml (`make check-lock`)

### Post-Deployment Verification

```bash
# Check service health
curl http://localhost:8765/health
curl http://localhost:8765/ready

# Test critical paths
# 1. Dashboard loads
# 2. Spotify auth works
# 3. Playlist import works
# 4. Download queue works
# 5. Settings save/load works

# Check logs for errors
docker-compose logs --tail=100 soulspot | grep ERROR
```

---

## Common Issues

### "Import Error: No module named ..."

**Solution:**
```bash
poetry install --with dev
# OR
docker-compose build --no-cache soulspot
```

### "Database Locked" Errors

**Solution:**
- SQLite doesn't handle concurrency well
- Use PostgreSQL for production
- OR restart service: `docker-compose restart soulspot`

### HTMX Not Working

**Solution:**
1. Check browser console for JavaScript errors (F12)
2. Verify HTMX loaded (Network tab)
3. Check API response format (should return HTML for HTMX)
4. Review `htmx-patterns.md` for correct attribute usage

---

## Related Documentation

- [HTMX Patterns](./htmx-patterns.md) - Frontend interaction patterns
- [Observability Guide](./observability-guide.md) - Logging and monitoring
- [Operations Runbook](./operations-runbook.md) - Deployment and operations
- [API Documentation](/api/endpoints/) - REST API reference

---

**Version:** 1.0  
**Last Updated:** 2025-01
