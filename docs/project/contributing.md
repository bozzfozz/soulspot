# Contributing to SoulSpot

First off, thank you for considering contributing to SoulSpot! It's people like you that make this project great.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Process](#development-process)
- [How Can I Contribute?](#how-can-i-contribute)
- [Style Guidelines](#style-guidelines)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Additional Resources](#additional-resources)

---

## Code of Conduct

This project and everyone participating in it is governed by our commitment to creating a welcoming and inclusive environment. By participating, you are expected to uphold professional standards:

- Be respectful and considerate
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Accept responsibility and learn from mistakes
- Show empathy towards other community members

---

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.12 or higher** - [Download Python](https://www.python.org/downloads/)
- **Git** - [Install Git](https://git-scm.com/downloads)
- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **Poetry** (optional but recommended) - [Install Poetry](https://python-poetry.org/docs/#installation)

### Setting Up Your Development Environment

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/soulspot.git
   cd soulspot
   ```

3. **Add the upstream repository**:
   ```bash
   git remote add upstream https://github.com/bozzfozz/soulspot.git
   ```

4. **Install dependencies**:
   ```bash
   # Using Poetry (recommended)
   poetry install
   
   # Or using pip
   pip install -r requirements.txt
   ```

5. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

6. **Start Docker services**:
   ```bash
   docker-compose up -d
   ```

7. **Run database migrations**:
   ```bash
   poetry run alembic upgrade head
   ```

8. **Verify the setup**:
   ```bash
   make test
   ```

---

## Development Process

### Workflow Overview

We follow a **feature branch workflow**:

1. **Create a branch** from `main` for your work
2. **Make your changes** following our style guidelines
3. **Write/update tests** for your changes
4. **Run quality checks** (tests, linting, type checking)
5. **Submit a pull request** to `main`
6. **Address review feedback** if any
7. **Merge** once approved

### Branch Naming Convention

Use descriptive branch names that indicate the type of work:

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

Write clear, concise commit messages following these guidelines:

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
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Test additions or changes
- `chore:` Maintenance tasks

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

## How Can I Contribute?

### Reporting Bugs

Before creating a bug report:
1. **Check the [issue tracker](https://github.com/bozzfozz/soulspot/issues)** to avoid duplicates
2. **Update to the latest version** to see if the issue persists
3. **Gather information** about your environment and how to reproduce the bug

When filing a bug report, use our [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Logs or error messages
- Screenshots if applicable

### Suggesting Enhancements

We welcome feature suggestions! Before creating an enhancement suggestion:
1. **Check existing issues** for similar suggestions
2. **Review the [roadmap](docs/development-roadmap.md)** - it might already be planned
3. **Consider the scope** - does it fit the project's goals?

Use our [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md) and include:
- Clear description of the feature
- Use cases and motivation
- Proposed solution or design
- Alternatives you've considered
- Additional context

### Contributing Code

#### Good First Issues

Look for issues labeled `good first issue` - these are great for newcomers:
- Well-defined scope
- Clear acceptance criteria
- Guidance provided
- Good learning opportunities

#### Areas That Need Help

- **Testing:** Increasing test coverage
- **Documentation:** Improving guides and examples
- **Bug Fixes:** Addressing reported issues
- **Performance:** Optimizing slow operations
- **UI/UX:** Improving the user interface

---

## Style Guidelines

### Python Code Style

We follow **PEP 8** and use automated tools to enforce consistency:

- **Linting:** ruff (configured in `pyproject.toml`)
- **Formatting:** ruff format (line length: 120)
- **Type Checking:** mypy in strict mode
- **Security:** bandit for security linting

**Before committing, run:**
```bash
make format      # Auto-format code
make lint        # Check code style
make type-check  # Verify type hints
make security    # Security scan
```

### Architecture Guidelines

We follow a **Layered Architecture** with **Domain-Driven Design** principles. Please read:

- [Architecture Documentation](docs/architecture.md) - Comprehensive architecture guide
- [Copilot Instructions](../.github/copilot-instructions.md) - Development lifecycle

**Key principles:**

1. **Dependency Flow:**
   ```
   Presentation → Application → Domain ← Infrastructure
   ```

2. **Separation of Concerns:**
   - **Domain:** Pure business logic, no external dependencies
   - **Application:** Use cases, orchestration
   - **Infrastructure:** External integrations, database
   - **Presentation:** API endpoints, UI

3. **Type Safety:**
   - Use type hints everywhere
   - Leverage Pydantic for validation
   - Strict mypy checking

4. **Testing:**
   - Unit tests for all business logic
   - Integration tests for API endpoints
   - Mock external dependencies

### Documentation Style

- Use **Markdown** for all documentation
- Include **code examples** where relevant
- Keep language **clear and concise**
- Add **diagrams** for complex concepts
- Update documentation when changing code

### UI/UX Guidelines

Follow our [Style Guide](docs/soulspot-style-guide.md) for UI work:
- Use **Tailwind CSS** classes
- Follow the defined **design system**
- Ensure **WCAG AA** accessibility
- Support **dark mode**
- Design **mobile-first**

---

## Project Structure

Understanding the project structure is crucial for contributions:

```
soulspot/
├── src/soulspot/           # Application source code
│   ├── domain/             # Domain layer (entities, value objects)
│   ├── application/        # Application layer (use cases, services)
│   ├── infrastructure/     # Infrastructure layer (database, integrations)
│   ├── api/                # Presentation layer (REST API)
│   ├── templates/          # Jinja2 templates for UI
│   ├── static/             # Static assets (CSS, JS)
│   ├── config/             # Configuration management
│   └── main.py             # Application entry point
├── tests/                  # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── conftest.py         # Pytest configuration
├── docs/                   # Documentation
├── alembic/                # Database migrations
├── .github/                # GitHub configuration
└── pyproject.toml          # Project dependencies and config
```

**See [Architecture Documentation](docs/architecture.md) for detailed structure guidelines.**

---

## Testing

### Running Tests

```bash
# All tests
make test

# Unit tests only
make test-unit

# With coverage report
make test-cov

# Specific test file
pytest tests/unit/domain/test_entities.py -v
```

### Writing Tests

We use **pytest** with the following conventions:

**Test Structure:**
```python
"""Tests for <module description>."""

import pytest


class TestFeatureName:
    """Test suite for specific feature."""
    
    def test_basic_functionality(self):
        """Test basic use case."""
        # Arrange
        expected = ...
        
        # Act
        result = ...
        
        # Assert
        assert result == expected
    
    def test_error_condition(self):
        """Test error handling."""
        with pytest.raises(ExpectedException):
            ...
```

**Guidelines:**
- One test file per module
- Group related tests in classes
- Use descriptive test names
- Follow Arrange-Act-Assert pattern
- Mock external dependencies
- Test both success and error paths

### Test Coverage

- Aim for **>80% coverage** for new code
- **100% coverage** for critical paths (authentication, payments, etc.)
- View coverage report: `make test-cov` then open `htmlcov/index.html`

---

## Submitting Changes

### Pull Request Process

1. **Update your branch** with the latest upstream changes:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all quality checks**:
   ```bash
   make test
   make lint
   make type-check
   make security
   ```

3. **Push your changes**:
   ```bash
   git push origin your-branch-name
   ```

4. **Create a Pull Request** on GitHub

5. **Fill out the PR template** completely

6. **Link related issues** using keywords (Fixes #123, Closes #456)

### Pull Request Guidelines

- **Keep PRs focused** - One feature/fix per PR
- **Keep PRs small** - Easier to review and merge
- **Write clear descriptions** - Explain what and why
- **Include tests** - All new code needs tests
- **Update documentation** - Keep docs in sync with code
- **Pass all checks** - CI must be green
- **Address review feedback** - Respond to comments promptly

### Review Process

1. **Automated checks** run on your PR (tests, linting, etc.)
2. **Code review** by project maintainers
3. **Feedback and discussion** if changes needed
4. **Approval** once ready
5. **Merge** by maintainers

**What reviewers look for:**
- Code quality and style
- Test coverage
- Documentation updates
- Architectural consistency
- Performance implications
- Security considerations

---

## Releases (For Maintainers)

### Release Process

SoulSpot uses automated CI/CD for releases. See the [CI/CD Guide](ci-cd.md) and [Release Quick Reference](release-quick-reference.md) for complete documentation.

**Quick overview:**

1. **Prepare Release:**
   - Use GitHub Actions "Create Release" workflow, or
   - Use local script: `./scripts/prepare-release.sh`, or
   - Prepare manually
   
2. **Update docs/project/CHANGELOG.md** with all changes for the release

3. **Create Release Tag:**
   ```bash
   git tag v1.2.3
   git push origin v1.2.3
   ```

4. **Automated Release:**
   - Docker images built and pushed to GHCR
   - GitHub Release created with artifacts
   - Python packages built and attached

### Semantic Versioning

We follow [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** (1.0.0 → 2.0.0): Breaking changes
- **MINOR** (1.0.0 → 1.1.0): New features, backward compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, backward compatible

### Release Checklist

Use the [Release Checklist](../.github/ISSUE_TEMPLATE/release_checklist.md) issue template for each release.

---

## Additional Resources

### Documentation

- [README.md](../README.md) - Project overview and quick start
- [Architecture Guide](architecture.md) - Detailed architecture
- [Style Guide](soulspot-style-guide.md) - UI/UX design system
- [CI/CD Guide](ci-cd.md) - Continuous Integration and Releases
- [Development Roadmap](development-roadmap.md) - Future plans
- [CHANGELOG.md](../project/CHANGELOG.md) - Version history

### External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)

### Getting Help

- **Issues:** [GitHub Issues](https://github.com/bozzfozz/soulspot/issues)
- **Discussions:** Use GitHub Discussions for questions
- **Documentation:** Check existing docs first
- **Code Examples:** Look at existing implementations

---

## Recognition

Contributors are recognized in:
- GitHub contributors page
- Release notes
- docs/project/CHANGELOG.md (for significant contributions)

Thank you for contributing to SoulSpot! 🎵🙏
