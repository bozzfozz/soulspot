# SoulSpot Bridge - Operations Runbook

> **Version:** 1.0  
> **Last Updated:** 2025-11-11  
> **Target Audience:** Operations Engineers, DevOps, System Administrators

## 📋 Overview

This operations runbook provides step-by-step procedures for common operational tasks, incident response, and system maintenance for SoulSpot Bridge.

---

## 🔧 Prerequisites

### Required Access
- SSH access to deployment server
- Docker and Docker Compose access
- Database access (if using PostgreSQL)
- Log aggregation system access (if configured)

### Required Tools
- `docker` and `docker-compose`
- `curl` or `httpie` for API testing
- Text editor (`vim`, `nano`, etc.)
- `jq` for JSON processing (recommended)

---

## 🚀 Common Operations

### 1. Service Management

#### Start Services
```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d soulspot
```

#### Stop Services
```bash
# Stop all services gracefully
docker-compose down

# Stop with cleanup (removes volumes - USE WITH CAUTION)
docker-compose down -v
```

#### Restart Services
```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart soulspot
```

#### View Service Status
```bash
# Check container status
docker-compose ps

# Check service health
curl http://localhost:8765/health
curl http://localhost:8765/ready
```

---

### 2. Log Management

#### View Real-time Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f soulspot

# Last 100 lines
docker-compose logs --tail=100 soulspot

# Filter by level (if using JSON logging)
docker-compose logs soulspot | jq 'select(.level == "ERROR")'
```

#### Extract Logs for Analysis
```bash
# Export logs to file
docker-compose logs soulspot > soulspot-$(date +%Y%m%d-%H%M%S).log

# Extract errors from last hour
docker-compose logs --since 1h soulspot | grep ERROR > errors.log

# Search for specific correlation ID
docker-compose logs soulspot | grep "correlation_id\":\"<ID>\""
```

---

### 3. Health Checks

#### Manual Health Checks
```bash
# Basic health check
curl http://localhost:8765/health

# Detailed readiness check (includes dependencies)
curl http://localhost:8765/ready

# Expected responses:
# Healthy: {"status":"healthy",...}
# Ready: {"status":"ready","checks":{...}}
```

#### Check Individual Dependencies
```bash
# Database
docker-compose exec soulspot python -c "
from soulspot.config import get_settings
from soulspot.infrastructure.persistence import Database
import asyncio

async def check():
    settings = get_settings()
    db = Database(settings)
    try:
        async with db.session_scope() as session:
            await session.execute('SELECT 1')
            print('Database: OK')
    except Exception as e:
        print(f'Database: FAILED - {e}')
    finally:
        await db.close()

asyncio.run(check())
"

# slskd
curl http://localhost:5030/health

# Spotify (requires valid tokens)
curl http://localhost:8765/api/v1/auth/spotify/status
```

---

### 4. Configuration Management

#### Update Environment Variables
```bash
# 1. Edit .env file
vim .env

# 2. Restart services to apply changes
docker-compose down
docker-compose up -d

# 3. Verify new configuration
docker-compose logs soulspot | head -20
```

#### Backup Configuration
```bash
# Create backup
cp .env .env.backup-$(date +%Y%m%d-%H%M%S)
cp docker-compose.yml docker-compose.yml.backup-$(date +%Y%m%d-%H%M%S)
```

---

### 5. Database Operations

#### SQLite (Default)

**Backup Database:**
```bash
# Stop application first
docker-compose stop soulspot

# Copy database file
cp soulspot.db soulspot-backup-$(date +%Y%m%d-%H%M%S).db

# Restart application
docker-compose start soulspot
```

**Restore Database:**
```bash
# Stop application
docker-compose stop soulspot

# Restore from backup
cp soulspot-backup-YYYYMMDD-HHMMSS.db soulspot.db

# Restart application
docker-compose start soulspot
```

**Run Migrations:**
```bash
# Check current migration status
docker-compose exec soulspot alembic current

# Run pending migrations
docker-compose exec soulspot alembic upgrade head

# Rollback one migration
docker-compose exec soulspot alembic downgrade -1
```

#### PostgreSQL (Production Profile)

**Backup Database:**
```bash
# Using docker-compose
docker-compose exec postgres pg_dump -U soulspot soulspot > backup-$(date +%Y%m%d-%H%M%S).sql

# Or using pg_dump directly
pg_dump -h localhost -U soulspot soulspot > backup-$(date +%Y%m%d-%H%M%S).sql
```

**Restore Database:**
```bash
# Stop application first
docker-compose stop soulspot

# Restore backup
docker-compose exec -T postgres psql -U soulspot soulspot < backup-YYYYMMDD-HHMMSS.sql

# Or using psql directly
psql -h localhost -U soulspot soulspot < backup-YYYYMMDD-HHMMSS.sql

# Restart application
docker-compose start soulspot
```

---

### 6. Data Management

#### Clear Cache
```bash
# Delete cache files (application will recreate)
docker-compose exec soulspot rm -rf /app/cache/*

# Restart to ensure clean state
docker-compose restart soulspot
```

#### Clean Up Old Downloads
```bash
# List downloads older than 30 days
find ./mnt/downloads -type f -mtime +30

# Remove downloads older than 30 days (BE CAREFUL)
find ./mnt/downloads -type f -mtime +30 -delete

# Clean empty directories
find ./mnt/downloads -type d -empty -delete
```

#### Verify Music Library
```bash
# Count total files
find ./mnt/music -type f | wc -l

# Check for broken symlinks
find ./mnt/music -type l -! -exec test -e {} \; -print

# Check disk usage
du -sh ./mnt/music
df -h ./mnt/music
```

---

## 🔥 Incident Response

### Service Down / Not Responding

**Symptoms:**
- HTTP 502/503 errors
- Connection timeouts
- Health check failures

**Investigation Steps:**

1. **Check container status:**
   ```bash
   docker-compose ps
   docker-compose logs --tail=50 soulspot
   ```

2. **Check resource usage:**
   ```bash
   docker stats
   free -h
   df -h
   ```

3. **Check for errors in logs:**
   ```bash
   docker-compose logs soulspot | grep ERROR | tail -50
   ```

**Resolution:**

1. **Quick restart (if transient issue):**
   ```bash
   docker-compose restart soulspot
   ```

2. **Full restart (if persistent):**
   ```bash
   docker-compose down
   docker-compose up -d
   docker-compose logs -f soulspot
   ```

3. **Check health after restart:**
   ```bash
   curl http://localhost:8765/health
   curl http://localhost:8765/ready
   ```

---

### High Memory Usage

**Symptoms:**
- OOM (Out of Memory) errors in logs
- Container restarts
- Slow response times

**Investigation:**
```bash
# Check container memory usage
docker stats soulspot

# Check system memory
free -h

# Find memory-intensive processes
docker-compose exec soulspot top
```

**Resolution:**

1. **Restart service to clear memory:**
   ```bash
   docker-compose restart soulspot
   ```

2. **Adjust memory limits in docker-compose.yml:**
   ```yaml
   services:
     soulspot:
       mem_limit: 2g
       mem_reservation: 1g
   ```

3. **Monitor after changes:**
   ```bash
   docker stats soulspot
   ```

---

### Database Connection Errors

**Symptoms:**
- "Connection refused" errors
- "Too many connections" errors
- Slow queries

**Investigation:**
```bash
# Check database logs
docker-compose logs postgres  # or check SQLite access

# Test database connection
docker-compose exec soulspot python -c "
from soulspot.infrastructure.persistence.database import Database
from soulspot.config import get_settings
import asyncio

async def test():
    db = Database(get_settings())
    async with db.session_scope() as session:
        print('Connection: OK')
    await db.close()

asyncio.run(test())
"
```

**Resolution:**

1. **For SQLite - Check file permissions:**
   ```bash
   ls -la soulspot.db
   chmod 664 soulspot.db
   ```

2. **For PostgreSQL - Restart database:**
   ```bash
   docker-compose restart postgres
   ```

3. **Check connection pool settings in .env:**
   ```bash
   DATABASE_POOL_SIZE=5
   DATABASE_MAX_OVERFLOW=10
   ```

---

### External API Failures

**Symptoms:**
- Spotify/MusicBrainz/slskd errors
- Circuit breaker OPEN state
- Timeouts in logs

**Investigation:**
```bash
# Check circuit breaker status in health endpoint
curl http://localhost:8765/ready | jq '.checks.circuit_breakers'

# Check recent API errors
docker-compose logs soulspot | grep -E "Spotify|MusicBrainz|slskd" | grep ERROR
```

**Resolution:**

1. **Verify external service status:**
   ```bash
   # Check slskd
   curl http://localhost:5030/health
   
   # Check Spotify credentials
   docker-compose logs soulspot | grep "Spotify.*401\|403"
   ```

2. **Reset circuit breaker (restart service):**
   ```bash
   docker-compose restart soulspot
   ```

3. **Update API credentials if needed:**
   ```bash
   vim .env  # Update SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, etc.
   docker-compose restart soulspot
   ```

---

### Download Queue Stuck

**Symptoms:**
- Downloads remain in QUEUED state
- No progress on active downloads
- Worker not processing

**Investigation:**
```bash
# Check active downloads via API
curl http://localhost:8765/api/v1/downloads | jq '.[] | select(.status == "QUEUED")'

# Check worker logs
docker-compose logs soulspot | grep -i worker
```

**Resolution:**

1. **Restart service:**
   ```bash
   docker-compose restart soulspot
   ```

2. **Check slskd connection:**
   ```bash
   curl http://localhost:5030/api/v0/session
   ```

3. **Manually retry failed downloads via API:**
   ```bash
   curl -X POST http://localhost:8765/api/v1/downloads/{download_id}/retry
   ```

---

## 📊 Monitoring

### Key Metrics to Monitor

| Metric | Command | Threshold |
|--------|---------|-----------|
| CPU Usage | `docker stats soulspot \| head -2` | < 80% |
| Memory Usage | `docker stats soulspot \| head -2` | < 1.5GB |
| Disk Usage | `df -h ./mnt` | < 90% |
| Active Downloads | `curl localhost:8765/api/v1/downloads \| jq 'length'` | < 10 |
| Health Status | `curl localhost:8765/health` | "healthy" |
| Database Size | `du -sh soulspot.db` | Monitor growth |

### Automated Monitoring Script

```bash
#!/bin/bash
# monitor.sh - Basic health monitoring

echo "=== SoulSpot Bridge Health Check ==="
echo "Timestamp: $(date)"

# Container status
echo -e "\n--- Container Status ---"
docker-compose ps

# Health check
echo -e "\n--- Health Check ---"
curl -s http://localhost:8765/health | jq .

# Resource usage
echo -e "\n--- Resource Usage ---"
docker stats --no-stream soulspot

# Disk usage
echo -e "\n--- Disk Usage ---"
df -h ./mnt

# Active downloads
echo -e "\n--- Active Downloads ---"
curl -s http://localhost:8765/api/v1/downloads | jq 'map(select(.status == "DOWNLOADING" or .status == "QUEUED")) | length'

echo -e "\n=== End Health Check ===\n"
```

Make executable and run:
```bash
chmod +x monitor.sh
./monitor.sh
```

---

## 🔄 Maintenance Tasks

### Weekly Maintenance

**Every Monday (or as needed):**

1. **Check logs for errors:**
   ```bash
   docker-compose logs --since 7d soulspot | grep ERROR | wc -l
   ```

2. **Backup database:**
   ```bash
   cp soulspot.db backups/soulspot-$(date +%Y%m%d).db
   ```

3. **Clean old downloads:**
   ```bash
   find ./mnt/downloads -type f -mtime +30 -delete
   ```

4. **Check disk space:**
   ```bash
   df -h ./mnt
   ```

5. **Review failed downloads:**
   ```bash
   curl http://localhost:8765/api/v1/downloads | jq '.[] | select(.status == "FAILED")'
   ```

### Monthly Maintenance

**First day of month:**

1. **Update dependencies:**
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

2. **Rotate logs:**
   ```bash
   docker-compose logs > logs/soulspot-$(date +%Y%m).log
   ```

3. **Review and archive old backups:**
   ```bash
   find backups/ -name "*.db" -mtime +90 -delete
   ```

4. **Performance review:**
   ```bash
   docker stats --no-stream
   ./monitor.sh > reports/monthly-$(date +%Y%m).txt
   ```

---

## 📞 Escalation

### When to Escalate

Escalate to development team if:
- Multiple restart attempts fail
- Data corruption detected
- Security incidents
- Critical bugs affecting production
- Performance degradation > 24 hours

### Escalation Checklist

Before escalating, collect:
- [ ] Current logs (`docker-compose logs`)
- [ ] System metrics (`docker stats`, `df -h`)
- [ ] Health check output
- [ ] Recent changes (configuration, deployment)
- [ ] Steps already attempted
- [ ] Error messages and stack traces

### Contact Information

- **GitHub Issues:** https://github.com/bozzfozz/soulspot-bridge/issues
- **Documentation:** https://github.com/bozzfozz/soulspot-bridge/docs

---

## 🔒 Security Operations

### Security Incident Response

**If you detect unauthorized access:**

1. **Immediately stop services:**
   ```bash
   docker-compose down
   ```

2. **Preserve logs:**
   ```bash
   docker-compose logs > incident-$(date +%Y%m%d-%H%M%S).log
   ```

3. **Review access logs for suspicious activity**

4. **Rotate all credentials:**
   - Spotify OAuth tokens
   - slskd credentials
   - Database passwords

5. **Update .env with new credentials**

6. **Restart services and monitor closely**

### Regular Security Checks

**Monthly:**
```bash
# Check for security vulnerabilities
docker-compose exec soulspot pip list --outdated

# Review user access
docker-compose logs soulspot | grep -i "auth\|login"

# Check file permissions
ls -la ./mnt/downloads ./mnt/music
```

---

## 🛠️ Troubleshooting Tools

### Useful Commands

```bash
# Enter container shell
docker-compose exec soulspot /bin/bash

# Python REPL in container
docker-compose exec soulspot python

# Check Python dependencies
docker-compose exec soulspot pip list

# Test API endpoint
curl -X GET http://localhost:8765/api/v1/health -v

# Pretty print JSON responses
curl http://localhost:8765/api/v1/downloads | jq .

# Follow logs with grep filter
docker-compose logs -f soulspot | grep -i error
```

### Debug Mode

Enable debug logging:
```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG

# Restart
docker-compose restart soulspot
```

---

## 📚 Additional Resources

- [Docker Setup Guide](docker/README.md)
- [Troubleshooting Guide](troubleshooting-guide.md)
- [Architecture Documentation](architecture.md)
- [API Documentation](http://localhost:8765/docs)
- [Development Roadmap](development-roadmap.md)

---

**Document Version:** 1.0  
**Last Reviewed:** 2025-11-11  
**Next Review:** 2025-12-11
