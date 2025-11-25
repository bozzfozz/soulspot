# Test Documentation

> **Version:** 1.0  
> **Last Updated:** 2025-11-25

---

## Overview

This directory contains documentation related to testing the SoulSpot application, including test execution guides, coverage reports, and comprehensive test reports.

## Contents

### Active Documentation

| File | Description |
|------|-------------|
| [TESTING.md](TESTING.md) | Test execution guide with commands for running tests |
| [TEST_COVERAGE_REPORT.md](TEST_COVERAGE_REPORT.md) | Current test coverage analysis and metrics |
| [TEST_REPORT.md](TEST_REPORT.md) | Comprehensive test & QA report |

### Related Documentation

For additional testing information, see:
- [Testing Guide](../../guides/developer/testing-guide.md) - Developer testing guide
- [Testing Strategy](../TESTING_STRATEGY.md) - Overall testing strategy

## Quick Start

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/soulspot --cov-report=html --cov-report=term

# Unit tests only
pytest tests/unit/ -v

# Fast tests
make test-fast
```

### Coverage Goals

- **Target Coverage:** 80%
- **Current Coverage:** See [TEST_COVERAGE_REPORT.md](TEST_COVERAGE_REPORT.md)

## Test Categories

| Category | Location | Count | Status |
|----------|----------|-------|--------|
| Unit Tests | `tests/unit/` | 490+ | ✅ Passing |
| Integration Tests | `tests/integration/` | 150+ | ✅ Passing |

---

For the complete testing guide, see [Developer Testing Guide](../../guides/developer/testing-guide.md).
