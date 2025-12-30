# Contributing to SoulSpot

**Category:** Project Management  
**Last Updated:** 2025-12-30

Thank you for considering contributing to SoulSpot! This guide will help you get started.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Process](#development-process)
- [How to Contribute](#how-to-contribute)
- [Style Guidelines](#style-guidelines)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

---

## Code of Conduct

This project is committed to creating a welcoming and inclusive environment. By participating, you are expected to:

- Be respectful and considerate
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Accept responsibility and learn from mistakes
- Show empathy towards other community members

---

## Getting Started

### Prerequisites

- **Python 3.12+** - [Download Python](https://www.python.org/downloads/)
- **Git** - [Install Git](https://git-scm.com/downloads)
- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **Poetry** (recommended) - [Install Poetry](https://python-poetry.org/docs/#installation)

### Setup Development Environment

```bash
# 1. Fork and clone
git clone https://github.com/YOUR-USERNAME/soulspot.git
cd soulspot

# 2. Add upstream
git remote add upstream https://github.com/bozzfozz/soulspot.git

# 3. Install dependencies
poetry install --with dev

# 4. Set up environment
cp .env.example .env
# Edit .env with your configuration

# 5. Start Docker services
docker-compose up -d

# 6. Run migrations
poetry run alembic upgrade head

# 7. Verify setup
make lint
make type-check
```

---

## Development Process

### Workflow

We follow a **feature branch workflow**:

1. **Create a branch** from `main`
2. **Make changes** following style guidelines
3. **Write/update documentation**
4. **Run quality checks**
5. **Submit pull request** to `main`
6. **Address review feedback**
7. **Merge** once approved

### Branch Naming

Use descriptive branch names:

- `feature/short-description` - New features
- `fix/short-description` - Bug fixes
- `docs/short-description` - Documentation changes
- `refactor/short-description` - Code refactoring
- `test/short-description` - Test improvements

**Examples:**
- `feature/add-playlist-export`
- `fix/oauth-token-refresh`
- `docs/update-api-examples`

### Commit Messages

**Format:**
```
<type>: <subject>

<body (optional)>

<footer (optional)>
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style (formatting)
- `refactor:` Code refactoring
- `test:` Test changes
- `chore:` Maintenance

**Examples:**
```
feat: add playlist export to M3U format

Implements export functionality for playlists to M3U format.
Includes UTF-8 encoding support and extended M3U tags.

Closes #123
```

```
fix: resolve OAuth token refresh race condition

The token refresh mechanism had a race condition when multiple
requests attempted to refresh simultaneously. This adds a lock
to ensure only one refresh happens at a time.

Fixes #456
```

---

## How to Contribute

### Reporting Bugs

**Before creating a bug report:**
1. Check [issue tracker](https://github.com/bozzfozz/soulspot/issues) for duplicates
2. Update to latest version
3. Gather environment details and reproduction steps

**Include in bug report:**
- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python version)
- Logs or error messages
- Screenshots if applicable

### Suggesting Enhancements

**Before creating enhancement suggestion:**
1. Check existing issues for similar suggestions
2. Review the [roadmap](./todo.md)
3. Consider scope and project goals

**Include in feature request:**
- Clear description
- Use cases and motivation
- Proposed solution
- Alternatives considered
- Additional context

### Contributing Code

#### Good First Issues

Look for `good first issue` label:
- Well-defined scope
- Clear acceptance criteria
- Guidance provided
- Good learning opportunities

#### Areas Needing Help

- **Testing:** Manual testing in Docker environment
- **Documentation:** Improving guides and examples
- **Bug Fixes:** Addressing reported issues
- **Performance:** Optimizing slow operations
- **UI/UX:** Improving user interface

---

## Style Guidelines

### Python Code Style

We follow **PEP 8** with automated enforcement:

- **Linting:** ruff (configured in `pyproject.toml`)
- **Formatting:** ruff format (line length: 120)
- **Type Checking:** mypy (strict mode)
- **Security:** bandit

**Pre-commit checks:**
```bash
make format      # Auto-format code
make lint        # Check code style
make type-check  # Verify type hints
make security    # Security scan
```

### Architecture Guidelines

We follow **Layered Architecture** with **Domain-Driven Design**.

**Read:**
- [Core Philosophy](../02-architecture/core-philosophy.md)
- [Data Layer Patterns](../02-architecture/data-layer-patterns.md)
- [Copilot Instructions](../../.github/copilot-instructions.md)

**Key Principles:**

1. **Dependency Flow:**
   ```
   API → Application → Domain ← Infrastructure
   ```

2. **Separation of Concerns:**
   - **Domain:** Pure business logic, no external dependencies
   - **Application:** Use cases, orchestration
   - **Infrastructure:** External integrations, database
   - **Presentation:** API endpoints, UI

3. **Always Update Interfaces:**
   When adding a repository method:
   ```python
   # domain/ports/__init__.py
   class ITrackRepository(Protocol):
       async def get_by_isrc(self, isrc: str) -> Track | None: ...
   
   # infrastructure/persistence/repositories.py
   class TrackRepository:
       async def get_by_isrc(self, isrc: str) -> Track | None:
           ...
   ```

4. **Service-Agnostic Naming:**
   - Use `Track`, `Artist`, `Playlist` (generic domain models)
   - NOT `SpotifyTrack`, `DeezerArtist` (service-specific only in clients)

---

## Testing

### Testing Policy

🚨 **NO AUTOMATED TESTS** - ALL TESTING IS MANUAL/LIVE

- ❌ No pytest tests
- ❌ No integration/E2E tests
- ✅ User validates manually via UI/API after each change

### Manual Testing Checklist

**Before submitting PR:**
1. [ ] Test affected UI pages manually in Docker
2. [ ] Verify API endpoints with curl/Postman
3. [ ] Check browser console for errors
4. [ ] Test in different browsers (Chrome, Firefox, Safari)
5. [ ] Verify mobile responsiveness
6. [ ] Test keyboard navigation
7. [ ] Check error handling

---

## Submitting Changes

### Pull Request Process

1. **Update Documentation:**
   - Update relevant docs in `docs-new/`
   - Add changelog entry in `docs-new/11-project/changelog.md`
   - Update API reference if endpoints changed

2. **Run Quality Checks:**
   ```bash
   make format
   make lint
   make type-check
   make security
   ```

3. **Manual Testing:**
   - Start Docker: `make docker-up`
   - Test affected features manually
   - Verify error handling

4. **Create Pull Request:**
   - Use clear title and description
   - Reference related issues
   - Include screenshots/videos if UI changes
   - List manual testing performed

5. **Code Review:**
   - Address feedback promptly
   - Keep discussion focused
   - Update commits if requested

### Pull Request Template

```markdown
## Description
[Clear description of what this PR does]

## Related Issues
Closes #[issue number]

## Changes Made
- [List key changes]
- [List key changes]

## Manual Testing Performed
- [ ] Tested feature X in Docker
- [ ] Verified API endpoint Y
- [ ] Checked browser console
- [ ] Tested mobile view

## Screenshots
[If applicable]

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Quality checks pass
- [ ] Manual testing complete
```

---

## Development Tips

### Common Commands

```bash
# Development
make docker-up          # Start Docker services
make docker-down        # Stop Docker services
docker logs -f soulspot # Follow logs

# Quality
make lint               # Run linter
make format             # Auto-format code
make type-check         # Type checking
make security           # Security scan

# Database
alembic upgrade head    # Apply migrations
alembic revision -m "message"  # Create migration
```

### Debugging

```bash
# View logs
docker logs soulspot 2>&1 | grep ERROR

# Interactive shell
docker exec -it soulspot bash

# Database inspection
docker exec -it soulspot-db psql -U soulspot
```

---

## Additional Resources

- [Architecture Documentation](../02-architecture/) - System architecture
- [API Reference](../01-api/) - API documentation
- [Feature Guides](../06-features/) - Feature documentation
- [User Guides](../08-guides/) - User guides
- [Developer Guides](../08-guides/) - Developer guides
- [TODO List](./todo.md) - Current roadmap
- [Changelog](./changelog.md) - Version history

---

## Questions?

- **Issues:** [GitHub Issues](https://github.com/bozzfozz/soulspot/issues)
- **Discussions:** [GitHub Discussions](https://github.com/bozzfozz/soulspot/discussions)
- **Email:** [Maintainer Contact]

Thank you for contributing! 🎉
