# Release Quick Reference

Quick guide for maintainers on creating releases.

## Prerequisites

- Write access to the repository
- All tests passing on main branch
- docs/project/CHANGELOG.md updated with changes

## Creating a Release (3 Options)

### Option 1: GitHub Actions (Recommended for Most Releases)

1. Go to **Actions** → **Create Release**
2. Click **Run workflow**
3. Select:
   - `patch` for bug fixes (1.0.0 → 1.0.1)
   - `minor` for new features (1.0.0 → 1.1.0)
   - `major` for breaking changes (1.0.0 → 2.0.0)
   - `custom` for specific version (e.g., 1.2.3)
4. The workflow creates a PR with version bumps
5. Edit the docs/project/CHANGELOG.md to add actual changes
6. Merge the PR
7. Create the release tag:
   ```bash
   git pull
   git tag v1.2.3
   git push origin v1.2.3
   ```

### Option 2: Local Script (For Experienced Maintainers)

```bash
# From repository root
./scripts/prepare-release.sh

# Follow the interactive prompts
# Script will:
# - Bump version in pyproject.toml and package.json
# - Update docs/project/CHANGELOG.md
# - Create release branch
# - Guide you through next steps
```

### Option 3: Manual (Not Recommended)

See [docs/ci-cd.md](../docs/ci-cd.md#option-3-manual-process) for manual steps.

## What Happens After Pushing a Tag?

When you push a tag like `v1.2.3`, the release workflow automatically:

1. ✅ Builds Docker images for amd64 and arm64
2. ✅ Pushes images to `ghcr.io/bozzfozz/soulspot`
3. ✅ Tags images with: `1.2.3`, `1.2`, `1`, and `latest`
4. ✅ Builds Python packages (wheel and sdist)
5. ✅ Creates GitHub Release with:
   - Changelog notes
   - Docker pull instructions
   - Python package artifacts
   - Auto-generated release notes

## Version Bump Guidelines

| Change Type | Bump Type | Example | When to Use |
|-------------|-----------|---------|-------------|
| Bug fix | patch | 1.0.0 → 1.0.1 | Only bug fixes, no new features |
| New feature | minor | 1.0.0 → 1.1.0 | New features, backward compatible |
| Breaking change | major | 1.0.0 → 2.0.0 | API changes, breaking changes |
| Pre-release | custom | 1.0.0 → 1.1.0-beta.1 | Alpha, beta, rc releases |

## docs/project/CHANGELOG.md Categories

Use these categories in order:

1. **Added** - New features
2. **Changed** - Changes to existing functionality
3. **Deprecated** - Features that will be removed soon
4. **Removed** - Features removed
5. **Fixed** - Bug fixes
6. **Security** - Security updates

## Common Issues

### Tag already exists
```bash
# Delete local and remote tag
git tag -d v1.2.3
git push origin :refs/tags/v1.2.3

# Create new tag
git tag v1.2.3
git push origin v1.2.3
```

### CI fails
```bash
# Run checks locally first
poetry run pytest
poetry run ruff check src/ tests/
poetry run mypy src/soulspot
docker build -t test .
```

### Need to update release notes
1. Go to GitHub Releases
2. Find your release
3. Click "Edit release"
4. Update the description
5. Save

## Files Modified During Release

- `pyproject.toml` - Python package version
- `package.json` - Node.js package version  
- `docs/project/CHANGELOG.md` - New version section and link

## Resources

- [Full CI/CD Guide](../ci-cd.md)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)

## Emergency Rollback

If a release has critical issues:

1. Create hotfix branch from previous tag:
   ```bash
   git checkout -b hotfix/v1.2.4 v1.2.2
   ```

2. Fix the issue

3. Create patch release following normal process

4. Mark broken release as pre-release in GitHub Releases
