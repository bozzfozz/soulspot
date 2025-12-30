# Linting & Code Quality

**Category:** Quality Assurance  
**Last Updated:** 2025-12-30  
**Status:** 🟢 A- Quality Grade  
**Tool:** Ruff v0.14.10

---

## Executive Summary

**Initial State:** 2,322 linting issues (Grade: 🔴 D)  
**Current State:** 145 remaining issues (Grade: 🟢 A-)  
**Fixed:** 2,177 issues (94% reduction)

### Quality Progress

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Issues | 2,322 | 145 | **-94%** |
| Import Issues | ~800 | 20 | **-98%** |
| Code Style | 1,500+ | 3 | **-99%** |

---

## Automatic Fixes Applied (2,177 issues)

### 1. Import Organization (795 issues)
- Sorted imports alphabetically
- Grouped imports by category (stdlib → third-party → local)
- Deduplicated imports
- Removed unused imports (F401)

**Example:**
```python
# Before
from typing import List
import os
from soulspot.domain.entities import Track
import sys
from typing import Dict

# After
import os
import sys
from typing import Dict, List

from soulspot.domain.entities import Track
```

### 2. Code Formatting (1,337 issues)
- Fixed whitespace and indentation
- Enforced line length <120 characters
- Standardized quote usage (double quotes)
- Removed trailing whitespace

### 3. Code Style (45 issues)
- Simplified list comprehensions
- Applied pyupgrade (modern Python syntax)
- Removed unnecessary else clauses

---

## Remaining Issues (145)

### Critical: Fix Required (6 issues)

#### B904 - Missing Exception Chaining
**Impact:** 🔴 HIGH - Loses original exception context

**Files:**
- `api/routers/playlists.py` (4 occurrences)
- `api/routers/quality_profiles.py` (1 occurrence)
- `api/routers/settings.py` (1 occurrence)

**Fix:**
```python
# ❌ Wrong
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))

# ✅ Correct
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e)) from e
```

### Medium: Review Needed (31 issues)

#### F821 - Undefined Name (11 issues)
**Impact:** 🟠 MEDIUM - Missing TYPE_CHECKING imports

**Fix:**
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soulspot.domain.ports.plugin import CapabilityInfo
```

#### ARG001 - Unused Function Argument (15 issues)
**Impact:** 🟡 LOW - Review case-by-case

**Examples:**
- Callback signatures (HTMX handlers)
- Interface implementations (must match signature)
- Future use parameters

**Fix:**
```python
# Option 1: Remove if truly unused
def process_data(data: str):  # Removed unused 'context' param
    ...

# Option 2: Mark as intentionally unused
def callback(event: Event, _context=None):  # Prefix with _
    ...
```

#### E402 - Module Import Not at Top (20 issues)
**Impact:** 🟡 LOW - Intentional (circular import prevention)

**Pattern:**
```python
# Intentional: Break circular dependency
def get_service():
    from soulspot.application.services import TrackService  # E402
    return TrackService()
```

**Action:** Add `# noqa: E402` comment to silence

### Low: Optional (87 issues)

#### ARG002 - Unused Method Argument (87 issues)
**Impact:** 🟢 INFO - Interface implementations

**Reason:** Methods must match interface signature even if argument unused

**Example:**
```python
class TrackRepository:
    # Interface requires 'session' parameter even if implementation uses it from __init__
    async def get_by_id(self, id: str, session=None):  # session unused (ARG002)
        result = await self.session.execute(...)  # Uses self.session instead
        ...
```

**Action:** No fix required (interface contract)

---

## Configuration Updates Applied

Added per-file ignores to reduce noise by 24%:

```toml
# pyproject.toml
[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Unused imports OK in __init__ (re-exports)
"tests/*" = ["ARG001", "ARG002"]  # Unused args OK in test fixtures
"api/routers/*" = ["ARG001"]  # HTMX callbacks may have unused params
```

---

## Commands

```bash
# Run linter
make lint
ruff check src/

# Auto-format code
make format
ruff format src/

# Check specific directory
ruff check src/soulspot/api/

# Fix safe issues automatically
ruff check --fix src/

# Show rule explanation
ruff rule B904
```

---

## Quality Gates

**Pre-PR Requirements:**
- [ ] `ruff check .` reports <150 issues
- [ ] No B904 (missing exception chaining) violations
- [ ] All F821 (undefined name) resolved
- [ ] Critical ARG001/ARG002 reviewed

**CI/CD:**
```yaml
# .github/workflows/quality.yml
- name: Lint
  run: ruff check . --output-format=github
```

---

## Next Steps

### Immediate (Week 1)
1. Fix 6 B904 exceptions (add `from e`)
2. Add TYPE_CHECKING imports for 11 F821 issues
3. Remove duplicate `get_image_service()` (F811)

### Short-term (Month 1)
4. Review 15 ARG001 unused function arguments
5. Add `# noqa: E402` to intentional late imports

### Long-term (Optional)
6. Refactor interfaces to avoid ARG002 pattern (large effort, low value)

---

## Related Documentation

- [Testing Guide](../08-guides/testing-guide.md) - Test quality standards
- [Contributing Guide](./contributing.md) - Code style guidelines
- [CI/CD](../03-development/ci-cd.md) - Quality gate integration
