# CI/CD and Release Process

This document describes the automated CI/CD pipeline and release process for SoulSpot.

## Table of Contents

- [Overview](#overview)
- [Continuous Integration](#continuous-integration)
- [Release Process](#release-process)
- [Docker Images](#docker-images)
- [Version Management](#version-management)
- [Changelog Management](#changelog-management)

## Overview

SoulSpot uses GitHub Actions for continuous integration and automated releases. The pipeline includes:

- **CI Pipeline**: Automated testing, linting, and Docker builds on every PR
- **Release Pipeline**: Automated releases with semantic versioning, Docker image publishing, and GitHub releases
- **Version Management**: Consistent version tracking across all project files

## Continuous Integration

### Triggers

The CI pipeline runs on:
- Pull requests to `main` and `develop` branches
- Direct pushes to `main` and `develop` branches

### Daily Docker Build

In addition to the CI pipeline, a separate workflow builds and publishes Docker images daily:
- **Schedule**: Runs daily at 02:00 UTC
- **Trigger**: Can also be triggered manually via GitHub Actions UI
- **Output**: Publishes to `ghcr.io/bozzfozz/soulspot:latest`
- **Platforms**: Builds for `linux/amd64` and `linux/arm64`
- **Tags**: Creates both `latest` and date-stamped tags (e.g., `20250120-abc123`)

This ensures that the `latest` tag always contains recent builds with the newest dependencies and security updates, even between releases.

### Jobs

#### 1. Test Job

Runs the test suite with coverage reporting:

```yaml
- Python 3.12
- All unit tests
- All integration tests
- Coverage report uploaded to Codecov
```

#### 2. Code Quality Job

Runs code quality checks:

```yaml
- Ruff linter (PEP 8, pyflakes, etc.)
- Ruff formatter check
- mypy type checker (strict mode)
- Bandit security scanner
```

#### 3. Docker Build Job

Validates Docker image builds:

```yaml
- Builds Docker image
- Uses build cache for faster builds
- Does not push (test only)
```

### Status Checks

All CI jobs must pass before a PR can be merged. Configure branch protection rules in GitHub to enforce this.

## Release Process

SoulSpot follows [Semantic Versioning 2.0.0](https://semver.org/).

### Version Format

```
MAJOR.MINOR.PATCH[-PRERELEASE]

Examples:
- 0.1.0 (initial alpha release)
- 1.0.0 (first stable release)
- 1.1.0 (new features, backward compatible)
- 1.1.1 (bug fixes)
- 2.0.0 (breaking changes)
- 1.2.0-beta.1 (pre-release)
```

### Version Bump Guidelines

| Type | When to Use | Example |
|------|-------------|---------|
| **MAJOR** | Breaking changes, incompatible API changes | 1.0.0 → 2.0.0 |
| **MINOR** | New features, backward compatible | 1.0.0 → 1.1.0 |
| **PATCH** | Bug fixes, backward compatible | 1.0.0 → 1.0.1 |

### Creating a Release

#### Option 1: Using GitHub Actions (Recommended)

1. Go to **Actions** → **Create Release** workflow
2. Click **Run workflow**
3. Select version bump type (patch/minor/major) or provide custom version
4. The workflow will:
   - Create a release branch
   - Update versions in all files
   - Update docs/project/CHANGELOG.md
   - Create a Pull Request

5. Review and update the docs/project/CHANGELOG.md with actual changes
6. Merge the PR
7. Create and push the git tag:
   ```bash
   git tag v1.2.3
   git push origin v1.2.3
   ```

#### Option 2: Using Local Script

1. Run the release preparation script:
   ```bash
   ./scripts/prepare-release.sh
   ```

2. Follow the interactive prompts
3. Edit docs/project/CHANGELOG.md to add changes
4. Push the release branch
5. Create a Pull Request on GitHub
6. After merge, create and push the tag:
   ```bash
   git tag v1.2.3
   git push origin v1.2.3
   ```

#### Option 3: Manual Process

1. Update version in `pyproject.toml`:
   ```bash
   poetry version patch  # or minor/major
   ```

2. Update version in `package.json`:
   ```json
   {
     "version": "1.2.3"
   }
   ```

3. Update `docs/project/CHANGELOG.md` (see [Changelog Management](#changelog-management))

4. Commit changes:
   ```bash
   git add pyproject.toml package.json docs/project/CHANGELOG.md
   git commit -m "chore: bump version to 1.2.3"
   ```

5. Create and push tag:
   ```bash
   git tag v1.2.3
   git push origin main v1.2.3
   ```

### What Happens When You Push a Tag

When you push a tag matching `v*.*.*`, the release workflow automatically:

1. **Extracts version** from the tag
2. **Extracts changelog** for that version from docs/project/CHANGELOG.md
3. **Builds Docker images** for multiple platforms (amd64, arm64)
4. **Pushes Docker images** to GitHub Container Registry (ghcr.io)
5. **Tags Docker images** with:
   - Exact version (e.g., `1.2.3`)
   - Minor version (e.g., `1.2`)
   - Major version (e.g., `1`)
   - `latest` (if on main branch)
6. **Builds Python packages** (wheel and source distribution)
7. **Creates GitHub Release** with:
   - Release notes from docs/project/CHANGELOG.md
   - Docker pull instructions
   - Python package files as assets
   - Auto-generated release notes

## Docker Images

### Registry

Docker images are published to GitHub Container Registry:

```
ghcr.io/bozzfozz/soulspot
```

### Image Tags

| Tag | Description | Updated | Example |
|-----|-------------|---------|---------|
| `latest` | Latest build (daily or release) | Daily at 02:00 UTC | `ghcr.io/bozzfozz/soulspot:latest` |
| `X.Y.Z` | Exact version | On release | `ghcr.io/bozzfozz/soulspot:0.1.0` |
| `X.Y` | Minor version line | On release | `ghcr.io/bozzfozz/soulspot:0.1` |
| `X` | Major version line | On release | `ghcr.io/bozzfozz/soulspot:0` |
| `YYYYMMDD-<sha>` | Daily build with date | Daily at 02:00 UTC | `ghcr.io/bozzfozz/soulspot:20250120-abc123` |

**Note**: The `latest` tag is updated daily via automated builds and also updated when a new release is published.

### Multi-Platform Support

Images are built for:
- `linux/amd64` (Intel/AMD 64-bit)
- `linux/arm64` (ARM 64-bit, e.g., Raspberry Pi 4, Apple Silicon)

Docker automatically pulls the correct image for your platform.

### Pulling Images

```bash
# Latest version
docker pull ghcr.io/bozzfozz/soulspot:latest

# Specific version
docker pull ghcr.io/bozzfozz/soulspot:0.1.0

# Specific platform
docker pull --platform linux/arm64 ghcr.io/bozzfozz/soulspot:latest
```

## Version Management

Versions must be kept in sync across multiple files:

1. **pyproject.toml** - Python package version (managed by Poetry)
2. **package.json** - Node.js package version (for Tailwind CSS)
3. **docs/project/CHANGELOG.md** - Version history with dates

### Checking Current Version

```bash
# Using Poetry
poetry version

# From pyproject.toml
grep "^version" pyproject.toml

# From package.json
grep "version" package.json
```

## Changelog Management

We follow [Keep a Changelog](https://keepachangelog.com/) format.

### Structure

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New features that have been added

### Changed
- Changes to existing functionality

### Deprecated
- Features that will be removed in upcoming releases

### Removed
- Features that have been removed

### Fixed
- Bug fixes

### Security
- Security updates

## [1.0.0] - 2025-01-15

### Added
- Initial stable release
...
```

### Categories

Use these categories in order:

1. **Added** - New features
2. **Changed** - Changes to existing functionality
3. **Deprecated** - Features that will be removed soon
4. **Removed** - Features that have been removed
5. **Fixed** - Bug fixes
6. **Security** - Security updates

### Best Practices

1. **Keep Unreleased section** - Add changes as you work
2. **Write for users** - Explain what changed and why it matters
3. **Link issues/PRs** - Reference GitHub issues and pull requests
4. **Date releases** - Use ISO 8601 format (YYYY-MM-DD)
5. **Group logically** - Group related changes together

### Example Entry

```markdown
## [1.2.0] - 2025-01-20

### Added
- Auto-import service for completed downloads (#42)
- Docker health checks for improved monitoring (#43)
- Multi-platform Docker images (amd64, arm64) (#44)

### Changed
- Improved error handling in Spotify client (#45)
- Updated dependencies to latest versions (#46)

### Fixed
- Fixed permission issues in Docker container (#47)
- Resolved race condition in job queue (#48)

### Security
- Updated vulnerable dependency xyz to version 2.0 (#49)
```

## Troubleshooting

### CI Failures

**Tests fail:**
1. Run tests locally: `poetry run pytest`
2. Check coverage: `poetry run pytest --cov`
3. Fix issues and push again

**Linting fails:**
1. Run linter: `poetry run ruff check src/ tests/`
2. Auto-fix: `poetry run ruff check --fix src/ tests/`
3. Format code: `poetry run ruff format src/ tests/`

**Docker build fails:**
1. Build locally: `docker build -t test .`
2. Check Dockerfile syntax
3. Ensure all dependencies are in pyproject.toml

### Release Failures

**Tag already exists:**
```bash
# Delete local tag
git tag -d v1.2.3

# Delete remote tag
git push origin :refs/tags/v1.2.3
```

**Docker push fails:**
- Check GitHub token has `packages: write` permission
- Verify you're logged into GHCR

**Release notes empty:**
- Ensure docs/project/CHANGELOG.md has an entry for the version
- Check the format: `## [1.2.3] - YYYY-MM-DD`

## References

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Documentation](https://docs.docker.com/)
