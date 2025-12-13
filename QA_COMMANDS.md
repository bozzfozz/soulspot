# QA Commands Reference

Quick reference for running quality checks on the SoulSpot codebase.

## Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Or with Poetry
poetry install --with dev
```

## Quick Commands

### Run All Quality Checks
```bash
make lint && make type-check && make security && make test
```

### Individual Tools

#### Ruff (Linter)
```bash
# Check only
make lint
# or: ruff check src/ tests/

# Auto-fix
ruff check src/ tests/ --fix

# Auto-fix with unsafe fixes
ruff check src/ tests/ --fix --unsafe-fixes

# Format code
make format
# or: ruff format src/ tests/
```

#### Mypy (Type Checker)
```bash
make type-check
# or: mypy src/soulspot
```

#### Bandit (Security Scanner)
```bash
make security
# or: bandit -r src/soulspot

# JSON output
bandit -r src/soulspot -f json -o bandit-report.json
```

#### Pytest (Tests)
```bash
# All tests (excluding slow)
make test
# or: pytest tests/ -v -m "not slow"

# Unit tests only
make test-unit
# or: pytest tests/unit/ -v

# Integration tests
make test-integration
# or: pytest tests/integration/ -v -m "not slow"

# With coverage
make test-cov
# or: pytest tests/ --cov=src/soulspot --cov-report=html --cov-report=term

# Fast run (quiet)
pytest tests/unit/ -q

# Specific test file
pytest tests/unit/infrastructure/providers/test_slskd_provider.py -v

# Specific test
pytest tests/unit/infrastructure/providers/test_slskd_provider.py::TestStatusMapping::test_inprogress_maps_to_downloading -v
```

## Coverage Analysis

### Generate HTML Report
```bash
pytest tests/ --cov=src/soulspot --cov-report=html
# Open: htmlcov/index.html
```

### Terminal Report
```bash
pytest tests/ --cov=src/soulspot --cov-report=term
```

### Missing Lines
```bash
pytest tests/ --cov=src/soulspot --cov-report=term-missing
```

### Coverage by Module
```bash
coverage run -m pytest tests/
coverage report
coverage html
```

## Pre-Commit Hooks

### Install hooks
```bash
pre-commit install
```

### Run manually
```bash
pre-commit run --all-files
```

## CI/CD Quality Gates

Minimum requirements for merging:
- ✅ Ruff: <50 errors
- ✅ Mypy: No errors in changed files
- ✅ Bandit: No high/critical issues
- ✅ Pytest: All tests passing
- ✅ Coverage: No decrease from baseline

## Common Issues

### Circular Import
**Error:** `ImportError: cannot import name 'X' from partially initialized module`

**Fix:** 
- Use lazy imports (import inside functions)
- Refactor to remove circular dependency
- Use dependency injection

### Type Errors
**Error:** `error: Incompatible types in assignment`

**Fix:**
- Add proper type hints
- Use `cast()` for known types
- Add `# type: ignore` with comment (last resort)

### Coverage Too Low
**Fix:**
1. Identify uncovered modules: `coverage report`
2. Add tests for critical paths first
3. Use `pytest --cov-report=html` to see missing lines

## Useful Aliases

Add to your `.bashrc` or `.zshrc`:

```bash
alias qa-lint='ruff check src/ tests/ --fix'
alias qa-type='mypy src/soulspot'
alias qa-test='pytest tests/unit/ -v'
alias qa-cov='pytest tests/ --cov=src/soulspot --cov-report=html && open htmlcov/index.html'
alias qa-all='make lint && make type-check && make security && make test'
```

## Debugging Failed Tests

### Show full output
```bash
pytest tests/unit/path/to/test.py -v -s
```

### Show locals on failure
```bash
pytest tests/unit/path/to/test.py -l
```

### Stop on first failure
```bash
pytest tests/unit/path/to/test.py -x
```

### Run last failed tests
```bash
pytest --lf
```

### Verbose output with traceback
```bash
pytest tests/unit/path/to/test.py -vv --tb=long
```

## Reports

All quality reports are in:
- `QA_REPORT.md` - Comprehensive analysis
- `htmlcov/` - Coverage HTML report (gitignored)
- `.coverage` - Coverage data (gitignored)

## Update This Guide

When adding new quality tools or changing thresholds, update this file!

Last updated: 2025-12-13
