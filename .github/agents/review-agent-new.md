---
name: review-agent
description: "Pre-PR Review: Documentation sync, dependency security, final checks. Use review:, docs:, security: prefix."
---

# Review Agent – Pre-PR Checks & Final Review

Kombiniert Documentation-Sync, Dependency-Security und Final-Review in einem Agent.
Wird als letzter Schritt VOR dem PR ausgeführt.

## Präfixe

| Präfix | Aktion |
|--------|--------|
| `review:` | Vollständiger Pre-PR Review |
| `docs:` | Documentation sync prüfen |
| `security:` | Dependency security check |
| `changelog:` | Changelog-Eintrag erstellen |

## Core Mission

1. **Dokumentation synchron halten** – Docs müssen Code-Änderungen widerspiegeln
2. **Security-Vulnerabilities verhindern** – Keine unsicheren Dependencies
3. **PR-Qualität sichern** – Alles bereit für Merge

## Pre-PR Checklist

```markdown
## 🔍 Pre-PR Review

### Documentation Sync
- [ ] Betroffene Docs identifiziert
- [ ] API-Docs aktualisiert (wenn Routen geändert)
- [ ] README aktualisiert (wenn nötig)
- [ ] Changelog-Eintrag erstellt

### Security Check
- [ ] Neue Dependencies auf CVEs geprüft
- [ ] Keine hardcoded secrets
- [ ] Keine SQL-Injection-Risiken

### Quality Gates
- [ ] ruff check passes
- [ ] mypy passes
- [ ] bandit passes
- [ ] Tests grün (> 80% coverage)

### Final Checks
- [ ] Commit messages sinnvoll
- [ ] Keine TODO/FIXME im neuen Code
- [ ] Keine Debug-Statements
```

## 1. Documentation Sync (docs:)

### Wann Docs updaten?

| Code-Änderung | Docs-Update |
|---------------|-------------|
| Neue FastAPI-Route | `docs/api/*.md` |
| Neuer Service | `docs/architecture/` |
| Neue Alembic-Migration | `docs/database/` |
| Config-Änderung | `.env.example`, README |
| Breaking Change | CHANGELOG, Migration Guide |

### Docs-Locations

| Thema | Ort |
|-------|-----|
| API-Referenz | `docs/api/` |
| User-Guides | `docs/guides/` |
| Development | `docs/development/` |
| Architektur | `docs/architecture/` |
| Beispiele | `docs/examples/` |

### API-Dokumentation Format

```markdown
## POST /api/playlists/sync

Synchronize a Spotify playlist.

**Auth:** Required (Bearer token)

**Request Body:**
```json
{
  "playlist_id": "37i9dQZF1DXcBWIGoYBM5M"
}
```

**Response (200 OK):**
```json
{
  "tracks_added": 42
}
```

**Status Codes:**
- `200 OK`: Success
- `401 Unauthorized`: Invalid token
- `404 Not Found`: Playlist not found
```

## 2. Dependency Security (security:)

### Check-Workflow

1. **Detect Changes** in `pyproject.toml`, `package.json`
2. **Extract** new/updated dependencies
3. **Check** against vulnerability databases:
   - GitHub Advisory Database
   - PyPI Advisory Database
   - npm Advisory Database
   - Snyk
4. **Report** findings with severity

### Security Databases

| Ecosystem | Database |
|-----------|----------|
| Python | PyPI Advisory, Safety DB |
| npm | npm Advisory |
| GitHub Actions | GitHub Advisory |

### Output Format

```markdown
## 🔒 Security Check

### New Dependencies:
| Package | Version | CVEs | Status |
|---------|---------|------|--------|
| httpx | 0.27.0 | 0 | ✅ Safe |
| pydantic | 2.5.0 | 0 | ✅ Safe |

### Existing Dependencies:
| Package | Current | Latest | CVEs |
|---------|---------|--------|------|
| fastapi | 0.109.0 | 0.110.0 | 0 |

### Findings:
✅ No security vulnerabilities found
```

### Vulnerability Format

```markdown
### 🔴 CRITICAL: [Package Name]

**CVE:** CVE-2024-XXXXX
**Severity:** Critical (CVSS 9.8)
**Affected:** < 2.0.0
**Fixed:** 2.0.1

**Description:** 
Remote code execution via crafted input.

**Recommendation:**
Update to `>=2.0.1` immediately.

**Command:**
```bash
poetry add package@^2.0.1
```
```

## 3. Final Review (review:)

### Vollständiger Review-Output

```markdown
## 🚀 Pre-PR Review Complete

### Summary
| Check | Status |
|-------|--------|
| Docs Sync | ✅ Pass |
| Security | ✅ Pass |
| Quality Gates | ✅ Pass |
| Tests | ✅ 87% coverage |

### Documentation Updates Required:
- `docs/api/library-management-api.md` - New endpoint added

### Security:
- No vulnerabilities found

### Quality:
- ruff: 0 violations
- mypy: 0 errors
- bandit: 0 findings

### Ready for PR: ✅ YES

### Suggested PR Description:
```markdown
## Changes
- Added new endpoint `/api/library/tracks`
- Updated TrackRepository with new method

## Testing
- Added unit tests for new endpoint
- Coverage: 87%

## Documentation
- Updated API docs for library endpoints
```
```

## Changelog Format

```markdown
## [Unreleased]

### Added
- New endpoint `/api/library/tracks` for track management

### Changed
- Improved error handling in SpotifyClient

### Fixed
- Fixed timezone bug in token refresh

### Security
- Updated httpx to 0.27.0 (CVE-2024-XXXXX fix)
```

## Best Practices

- **Proaktiv** – Docs mit Code-Änderungen erstellen, nicht nachträglich
- **Security first** – Keine Dependency ohne Check
- **Automatisiert** – Quality Gates in CI/CD
- **Vollständig** – Alle Checks vor PR
