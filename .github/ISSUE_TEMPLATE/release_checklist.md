---
name: Release Checklist
about: Checklist for preparing and executing a release
title: "Release v[VERSION]"
labels: ["release", "documentation"]
assignees: []
---

## Release Information

**Version:** [e.g., 1.2.0]
**Type:** [patch/minor/major]
**Target Date:** [YYYY-MM-DD]
**Release Manager:** [@username]

## Pre-Release Checklist

### Code & Testing
- [ ] All tests passing on main branch
- [ ] CI/CD pipeline green
- [ ] No open critical bugs
- [ ] Security scan clean
- [ ] Performance regressions checked

### Documentation
- [ ] docs/project/CHANGELOG.md updated with all changes
- [ ] Breaking changes documented (if major version)
- [ ] Migration guide updated (if needed)
- [ ] API documentation up to date
- [ ] README version badge will be updated

### Version Bump
- [ ] Determine correct version number (SemVer)
- [ ] Version updated in:
  - [ ] `pyproject.toml`
  - [ ] `package.json`
  - [ ] `docs/project/CHANGELOG.md`

## Release Process

### Step 1: Prepare Release
Choose one method:
- [ ] **Option A:** Use GitHub Actions `Create Release` workflow
- [ ] **Option B:** Use local script `./scripts/prepare-release.sh`
- [ ] **Option C:** Manual preparation

### Step 2: Review & Merge
- [ ] Release PR created
- [ ] docs/project/CHANGELOG.md entries reviewed and finalized
- [ ] Version numbers verified
- [ ] PR approved by maintainer
- [ ] PR merged to main

### Step 3: Create Tag & Trigger Release
```bash
git pull origin main
git tag v[VERSION]
git push origin v[VERSION]
```
- [ ] Git tag created and pushed
- [ ] Release workflow triggered

### Step 4: Verify Release
- [ ] GitHub Release created automatically
- [ ] Docker images published to GHCR:
  - [ ] `ghcr.io/bozzfozz/soulspot:[VERSION]`
  - [ ] `ghcr.io/bozzfozz/soulspot:latest`
  - [ ] Multi-platform images available (amd64, arm64)
- [ ] Python packages built and attached as artifacts
- [ ] Release notes look correct

### Step 5: Testing
- [ ] Pull and test Docker image:
  ```bash
  docker pull ghcr.io/bozzfozz/soulspot:[VERSION]
  docker run --rm ghcr.io/bozzfozz/soulspot:[VERSION] --version
  ```
- [ ] Test Python package (optional):
  ```bash
  pip install soulspot-[VERSION]-py3-none-any.whl
  ```
- [ ] Smoke test in staging environment
- [ ] Verify health checks working

## Post-Release Checklist

### Communication
- [ ] Release announcement prepared
- [ ] Update main README if needed
- [ ] Update documentation links
- [ ] Notify users of breaking changes (if any)

### Monitoring
- [ ] Monitor error logs for 24 hours
- [ ] Check Docker pull metrics
- [ ] Monitor GitHub issues for reports

### Cleanup
- [ ] Delete release branch (if created)
- [ ] Close related issues
- [ ] Update project board

## Rollback Plan

If critical issues are discovered:
1. Mark release as pre-release in GitHub
2. Revert Docker `latest` tag to previous version
3. Create hotfix branch from previous stable tag
4. Follow hotfix release process

## Notes

[Add any additional notes, known issues, or special considerations for this release]

---

## Resources

- [CI/CD Guide](../docs/ci-cd.md)
- [Release Quick Reference](../docs/release-quick-reference.md)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
