# Docker Usage Quick Reference

This directory contains all Docker-related files for SoulSpot (local single-user setup).

## Files in this Directory

- **Dockerfile** - Multi-stage Docker image definition
- **docker-compose.yml** - Main compose file for local use
- **docker-entrypoint.sh** - Container startup script
- **README.md** - Complete Docker setup guide

## Quick Start

From the **repository root**, run:

```bash
# Start services
docker-compose -f docker/docker-compose.yml up -d

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# Stop services
docker-compose -f docker/docker-compose.yml down
```

## Using Make/Just

The Makefile and Justfile in the root directory provide convenient shortcuts:

```bash
# With Make
make docker-up
make docker-logs
make docker-down

# With Just
just docker-up
just docker-logs
just docker-down
```

## Building the Docker Image

```bash
# Build from repository root
docker build -f docker/Dockerfile -t soulspot .
```

## Documentation

For complete setup instructions, troubleshooting, and configuration options, see [README.md](README.md) in this directory.

## Important Notes

⚠️ **Always run docker-compose from the repository root**, not from inside the docker/ directory. The compose files use relative paths that expect to be run from the root.

⚠️ **Create required directories** before starting:
```bash
mkdir -p mnt/downloads mnt/music
```

See the [full Docker Setup Guide](README.md) for detailed information.
