# Deployment Guide

This guide explains how to deploy SoulSpot Bridge to different environments using the automated deployment workflows.

## Table of Contents

1. [Overview](#overview)
2. [Environment Setup](#environment-setup)
3. [Development Deployment](#development-deployment)
4. [Staging Deployment](#staging-deployment)
5. [Production Deployment](#production-deployment)
6. [Rollback Procedures](#rollback-procedures)
7. [Troubleshooting](#troubleshooting)

---

## Overview

SoulSpot Bridge uses GitHub Actions for automated deployment to three environments:

- **Development**: Automatic deployment on push to `develop` branch
- **Staging**: Automatic deployment on push to `main` branch
- **Production**: Manual deployment triggered by releases or workflow dispatch

Each environment has its own Docker Compose configuration and environment variables.

---

## Environment Setup

### Prerequisites

1. **GitHub Repository Secrets**: Configure the following secrets for each environment:
   ```
   Development:
   - DEV_SSH_HOST (optional)
   - DEV_SSH_USER (optional)
   - DEV_SSH_PRIVATE_KEY (optional)
   
   Staging:
   - STAGING_SSH_HOST (optional)
   - STAGING_SSH_USER (optional)
   - STAGING_SSH_PRIVATE_KEY (optional)
   - SPOTIFY_CLIENT_ID
   - SPOTIFY_CLIENT_SECRET
   - SECRET_KEY
   
   Production:
   - PROD_SSH_HOST (optional)
   - PROD_SSH_USER (optional)
   - PROD_SSH_PRIVATE_KEY (optional)
   - SPOTIFY_CLIENT_ID
   - SPOTIFY_CLIENT_SECRET
   - SECRET_KEY
   - SLSKD_API_KEY
   - SLSKD_USERNAME
   - SLSKD_PASSWORD
   ```

2. **Server Requirements**:
   - Docker and Docker Compose installed
   - SSH access configured (if using automated deployment)
   - Sufficient storage for music library and downloads
   - Open ports: 8765 (SoulSpot Bridge), 5030 (slskd)

3. **Environment Configuration**:
   - Create `.env` files for each environment
   - Configure volume paths for data persistence

> **Hinweis:** Reverse Proxy (nginx/traefik) entfernt (lokal-only Betrieb).

---

## Development Deployment

### Automatic Deployment

Development deployment happens automatically when you push to the `develop` branch:

```bash
git checkout develop
git add .
git commit -m "feat: new feature"
git push origin develop
```

This triggers the `deploy-dev.yml` workflow which:
1. Builds a Docker image tagged with `dev-latest` and `dev-<sha>`
2. Pushes the image to GitHub Container Registry
3. (Optional) Deploys to development server via SSH

### Manual Deployment

You can also trigger deployment manually:

```bash
# Via GitHub CLI
gh workflow run deploy-dev.yml

# Via GitHub UI
# Go to Actions → Deploy to Development → Run workflow
```

### Local Testing

Test the development configuration locally:

```bash
# Pull the latest development image
docker pull ghcr.io/bozzfozz/soulspot-bridge:dev-latest

# Start services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop services
docker-compose -f docker-compose.dev.yml down
```

---

## Staging Deployment

### Automatic Deployment

Staging deployment happens automatically when you push to the `main` branch:

```bash
git checkout main
git merge develop
git push origin main
```

This triggers the `deploy-staging.yml` workflow which:
1. Runs all tests
2. Builds a Docker image tagged with `staging-latest` and `staging-<sha>`
3. Pushes the image to GitHub Container Registry
4. (Optional) Deploys to staging server via SSH
5. Runs smoke tests

### Manual Deployment

Trigger staging deployment manually:

```bash
# Via GitHub CLI
gh workflow run deploy-staging.yml -f skip_tests=false

# Via GitHub UI
# Go to Actions → Deploy to Staging → Run workflow
```

### Staging Configuration

Create a `.env.staging` file on your staging server:

```bash
# Required secrets
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SECRET_KEY=your_secret_key
SLSKD_API_KEY=your_slskd_api_key
SLSKD_USERNAME=your_username
SLSKD_PASSWORD=your_password

# Staging-specific settings
SPOTIFY_REDIRECT_URI=https://staging.soulspot.example.com/api/v1/auth/callback
APP_ENV=staging
DEBUG=false
LOG_LEVEL=INFO
API_SECURE_COOKIES=true
OBSERVABILITY__LOG_JSON_FORMAT=true
```

Deploy to staging server:

```bash
# On staging server
cd /opt/soulspot-bridge
docker pull ghcr.io/bozzfozz/soulspot-bridge:staging-latest
docker-compose -f docker-compose.staging.yml --env-file .env.staging up -d
```

---

## Production Deployment

### Release-based Deployment

Production deployment is triggered by creating a GitHub release:

1. **Create a release PR**:
   ```bash
   gh workflow run create-release.yml -f version_bump=minor
   ```

2. **Review and merge the release PR**

3. **Create and push a git tag**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

4. **The release workflow automatically**:
   - Builds multi-platform Docker images
   - Pushes images to GitHub Container Registry
   - Creates a GitHub release with artifacts
   - (Manual step) Deploy to production

### Manual Production Deployment

Deploy a specific version to production:

```bash
# Via GitHub CLI
gh workflow run deploy-prod.yml -f version=v1.0.0

# Via GitHub UI
# Go to Actions → Deploy to Production → Run workflow
```

### Production Configuration

Create a `.env.prod` file on your production server:

```bash
# Required secrets (use strong values!)
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SECRET_KEY=your_strong_secret_key_here
SLSKD_API_KEY=your_slskd_api_key
SLSKD_USERNAME=your_username
SLSKD_PASSWORD=your_strong_password

# Production settings
SPOTIFY_REDIRECT_URI=https://soulspot.example.com/api/v1/auth/callback
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO
API_SECURE_COOKIES=true
OBSERVABILITY__LOG_JSON_FORMAT=true
OBSERVABILITY__ENABLE_DEPENDENCY_HEALTH_CHECKS=true

# Timezone
TZ=Europe/Berlin
```

### Blue-Green Deployment (Recommended)

Deploy to production using blue-green strategy for zero downtime:

```bash
# On production server
cd /opt/soulspot-bridge

# Pull new version
docker pull ghcr.io/bozzfozz/soulspot-bridge:1.0.0

# Tag as production
docker tag ghcr.io/bozzfozz/soulspot-bridge:1.0.0 ghcr.io/bozzfozz/soulspot-bridge:production

# Update docker-compose.yml to use the production tag
export VERSION=1.0.0

# Deploy with zero downtime
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d --no-deps --remove-orphans soulspot

# Wait for health check
sleep 10
docker exec soulspot-bridge-prod curl -f http://localhost:8765/health

# Cleanup old images
docker image prune -f
```

### Production Health Checks

After deployment, verify production health:

```bash
# Check health endpoint
curl -f https://soulspot.example.com/health

# Check API health
curl -f https://soulspot.example.com/api/v1/health

# View logs
docker logs -f soulspot-bridge-prod

# Check container status
docker ps | grep soulspot
```

---

## Rollback Procedures

### Automatic Rollback Detection

If production deployment fails, the workflow will provide rollback instructions.

### Manual Rollback

To rollback to a previous version:

1. **Identify the last known good version**:
   ```bash
   gh release list
   ```

2. **Trigger rollback deployment**:
   ```bash
   gh workflow run deploy-prod.yml -f version=v0.9.0 -f rollback=true
   ```

3. **Manual rollback on server**:
   ```bash
   # On production server
   cd /opt/soulspot-bridge
   
   # Stop current version
   docker-compose -f docker-compose.prod.yml down
   
   # Pull and tag previous version
   docker pull ghcr.io/bozzfozz/soulspot-bridge:0.9.0
   docker tag ghcr.io/bozzfozz/soulspot-bridge:0.9.0 ghcr.io/bozzfozz/soulspot-bridge:production
   
   # Start previous version
   export VERSION=0.9.0
   docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
   
   # Verify health
   docker logs -f soulspot-bridge-prod
   curl -f https://soulspot.example.com/health
   ```

### Database Rollback

If database migrations are involved:

```bash
# On production server
docker exec -it soulspot-bridge-prod alembic downgrade -1
```

---

## Troubleshooting

### Common Issues

#### 1. Docker Image Pull Fails

**Problem**: Cannot pull image from GitHub Container Registry

**Solution**:
```bash
# Authenticate with GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Or use GitHub CLI
gh auth token | docker login ghcr.io -u USERNAME --password-stdin
```

#### 2. Health Check Fails

**Problem**: Container starts but health check fails

**Solution**:
```bash
# Check container logs
docker logs soulspot-bridge-prod

# Check if ports are accessible
curl -v http://localhost:8765/health

# Verify environment variables
docker exec soulspot-bridge-prod env | grep APP_ENV
```

#### 3. Database Migration Fails

**Problem**: Migration errors during deployment

**Solution**:
```bash
# Check migration status
docker exec -it soulspot-bridge-prod alembic current

# View migration history
docker exec -it soulspot-bridge-prod alembic history

# Rollback last migration
docker exec -it soulspot-bridge-prod alembic downgrade -1
```

#### 4. Permission Issues

**Problem**: Container cannot write to mounted volumes

**Solution**:
```bash
# Check volume permissions
ls -la /opt/soulspot/

# Fix ownership (use your PUID/PGID)
sudo chown -R 1000:1000 /opt/soulspot/

# Verify in docker-compose.yml
grep -A 2 PUID docker-compose.prod.yml
```

### Debug Mode

Enable debug mode temporarily:

```bash
# Edit docker-compose.prod.yml
# Set: DEBUG=true
# Set: LOG_LEVEL=DEBUG

# Restart container
docker-compose -f docker-compose.prod.yml restart soulspot

# View detailed logs
docker logs -f soulspot-bridge-prod
```

### Support

For additional help:
- Check [GitHub Issues](https://github.com/bozzfozz/soulspot-bridge/issues)
- Review [Documentation](https://github.com/bozzfozz/soulspot-bridge/tree/main/docs)
- Join community discussions

---

## Best Practices

1. **Always test in staging first** before deploying to production
2. **Create backups** before major deployments
3. **Monitor logs** during and after deployment
4. **Use semantic versioning** for releases
5. **Document changes** in CHANGELOG.md
6. **Run smoke tests** after deployment
7. **Keep secrets secure** - never commit to git
8. **Use SSL/TLS** in production with a reverse proxy
9. **Set up automated backups** for production database
10. **Configure alerting** for health check failures

---

**Last Updated**: 2025-11-11  
**Version**: 0.2.0
