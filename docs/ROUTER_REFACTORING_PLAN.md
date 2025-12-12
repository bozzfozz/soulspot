# Automation Router Refactoring Plan

**Generated:** 2025-12-12  
**Status:** Planning Phase  
**Risk Level:** 🟡 Medium (requires extensive testing)  
**Estimated Effort:** 4-6 hours

---

## Problem Statement

`automation.py` is **1366 lines** with **25 endpoints** across 6 different concerns:
- Watchlists (5 endpoints)
- Discography (2 endpoints)
- Quality Upgrades (2 endpoints)
- Filters (7 endpoints)
- Rules (6 endpoints)
- Followed Artists (3 endpoints)

**Issues:**
- File too large for efficient editing
- Mixed concerns violate Single Responsibility Principle
- Difficult to navigate and maintain
- Test organization unclear

---

## Proposed Structure

###Split into 6 focused routers:

```
src/soulspot/api/routers/
├── automation/                    # New subdirectory
│   ├── __init__.py               # Aggregates all sub-routers
│   ├── watchlists.py             # 5 endpoints (POST, GET list, GET single, POST check, DELETE)
│   ├── discography.py            # 2 endpoints (POST check, GET missing)
│   ├── quality_upgrades.py       # 2 endpoints (POST identify, GET unprocessed)
│   ├── filters.py                # 7 endpoints (CRUD + enable/disable/patch)
│   ├── rules.py                  # 6 endpoints (CRUD + enable/disable)
│   └── followed_artists.py       # 3 endpoints (sync, bulk watchlists, preview)
└── automation.py                 # DELETE after migration complete
```

---

## Detailed Migration Plan

### Phase 1: Extract Shared DTOs (1 hour)

**Create:** `src/soulspot/api/schemas/automation.py`

Extract all Pydantic models from `automation.py`:
```python
# MOVE THESE CLASSES:
class CreateWatchlistRequest(BaseModel): ...
class WatchlistResponse(BaseModel): ...
class DiscographyCheckRequest(BaseModel): ...
class QualityUpgradeRequest(BaseModel): ...
class FilterRuleRequest(BaseModel): ...
class AutomationRuleRequest(BaseModel): ...
class FollowedArtistsSyncRequest(BaseModel): ...
```

**Why separate file?**
- Avoid circular imports
- Reusable across multiple routers
- Cleaner test mocking

---

### Phase 2: Create Router Subdirectory (2-3 hours)

#### 2.1 watchlists.py (~270 lines)

**Endpoints:**
```python
POST   /automation/watchlist
GET    /automation/watchlist
GET    /automation/watchlist/{watchlist_id}
POST   /automation/watchlist/{watchlist_id}/check
DELETE /automation/watchlist/{watchlist_id}
```

**Dependencies:**
- `WatchlistService`
- DTOs from `api.schemas.automation`

**Line Range:** 86-323 from original file

---

#### 2.2 discography.py (~80 lines)

**Endpoints:**
```python
POST /automation/discography/check
GET  /automation/discography/missing
```

**Dependencies:**
- `DiscographyService`
- Spotify token dependency

**Line Range:** 324-400

---

#### 2.3 quality_upgrades.py (~100 lines)

**Endpoints:**
```python
POST /automation/quality-upgrades/identify
GET  /automation/quality-upgrades/unprocessed
```

**Dependencies:**
- `QualityUpgradeService`

**Line Range:** 401-503

---

#### 2.4 filters.py (~330 lines)

**Endpoints:**
```python
POST   /automation/filters
GET    /automation/filters
GET    /automation/filters/{filter_id}
POST   /automation/filters/{filter_id}/enable
POST   /automation/filters/{filter_id}/disable
PATCH  /automation/filters/{filter_id}
DELETE /automation/filters/{filter_id}
```

**Dependencies:**
- `FilterService` (needs to be created from existing logic)

**Line Range:** 504-830

---

#### 2.5 rules.py (~320 lines)

**Endpoints:**
```python
POST   /automation/rules
GET    /automation/rules
GET    /automation/rules/{rule_id}
POST   /automation/rules/{rule_id}/enable
POST   /automation/rules/{rule_id}/disable
DELETE /automation/rules/{rule_id}
```

**Dependencies:**
- `AutomationRuleService` (needs extraction)

**Line Range:** 831-1152

---

#### 2.6 followed_artists.py (~210 lines)

**Endpoints:**
```python
POST /automation/followed-artists/sync
POST /automation/followed-artists/watchlists/bulk
GET  /automation/followed-artists/preview
```

**Dependencies:**
- `FollowedArtistsService`
- Spotify token dependency

**Line Range:** 1153-1366

---

### Phase 3: Create Aggregator __init__.py (15 min)

**File:** `src/soulspot/api/routers/automation/__init__.py`

```python
"""Automation API routers aggregation."""

from fastapi import APIRouter

from . import (
    discography,
    filters,
    followed_artists,
    quality_upgrades,
    rules,
    watchlists,
)

# Hey future me, this aggregates all automation sub-routers under /automation prefix!
# Each sub-router defines its own sub-paths (e.g., /watchlist, /filters, /rules).
# Final URLs: /api/automation/watchlist, /api/automation/filters, etc.
# The main api/routers/__init__.py includes THIS router, not the individual ones.

router = APIRouter(prefix="/automation", tags=["Automation"])

# Include all sub-routers (no additional prefix, they define their own)
router.include_router(watchlists.router)
router.include_router(discography.router)
router.include_router(quality_upgrades.router)
router.include_router(filters.router)
router.include_router(rules.router)
router.include_router(followed_artists.router)

__all__ = ["router"]
```

---

### Phase 4: Update Main Router Registration (5 min)

**File:** `src/soulspot/api/routers/__init__.py`

```python
# BEFORE
from soulspot.api.routers import automation
api_router.include_router(automation.router, tags=["Automation"])

# AFTER
from soulspot.api.routers.automation import router as automation_router
api_router.include_router(automation_router)  # Tags already set in automation/__init__.py
```

---

### Phase 5: Update Tests (1-2 hours)

**Test Files to Update:**

1. **`tests/unit/api/test_automation_router.py`** → Split into:
   - `tests/unit/api/automation/test_watchlists_router.py`
   - `tests/unit/api/automation/test_discography_router.py`
   - `tests/unit/api/automation/test_quality_upgrades_router.py`
   - `tests/unit/api/automation/test_filters_router.py`
   - `tests/unit/api/automation/test_rules_router.py`
   - `tests/unit/api/automation/test_followed_artists_router.py`

2. **Import updates in all test files:**
   ```python
   # BEFORE
   from soulspot.api.routers.automation import router
   
   # AFTER
   from soulspot.api.routers.automation.watchlists import router
   ```

---

### Phase 6: Update API Documentation (30 min)

**File:** `docs/api/automation-watchlists.md`

**Update router references:**
```markdown
# BEFORE
**Related Router:** `src/soulspot/api/routers/automation.py`

# AFTER
**Related Routers:**
- `src/soulspot/api/routers/automation/watchlists.py`
- `src/soulspot/api/routers/automation/discography.py`
- `src/soulspot/api/routers/automation/quality_upgrades.py`
- `src/soulspot/api/routers/automation/filters.py`
- `src/soulspot/api/routers/automation/rules.py`
- `src/soulspot/api/routers/automation/followed_artists.py`
```

---

## Implementation Checklist

### Pre-Refactoring
- [ ] Create git feature branch: `refactor/split-automation-router`
- [ ] Run full test suite to establish baseline
- [ ] Verify all 25 endpoints accessible via `/api/automation/*`
- [ ] Document current test coverage percentage

### Execution
- [ ] Create `api/schemas/automation.py` with all DTOs
- [ ] Create `api/routers/automation/` directory
- [ ] Implement `watchlists.py` router
- [ ] Implement `discography.py` router
- [ ] Implement `quality_upgrades.py` router
- [ ] Implement `filters.py` router
- [ ] Implement `rules.py` router
- [ ] Implement `followed_artists.py` router
- [ ] Create aggregator `automation/__init__.py`
- [ ] Update main `routers/__init__.py`
- [ ] Delete old `automation.py`

### Testing
- [ ] Split test file into 6 focused test modules
- [ ] Update all imports in test files
- [ ] Run full test suite - verify all tests pass
- [ ] Manual API testing with Postman/curl for each endpoint
- [ ] Verify OpenAPI docs still generate correctly (`/docs`)
- [ ] Check test coverage matches or exceeds baseline

### Documentation
- [ ] Update `docs/api/automation-watchlists.md`
- [ ] Update `docs/project/architecture.md` if routing structure mentioned
- [ ] Add entry to `CHANGELOG.md` (Internal: Router refactoring)
- [ ] Update this document status to COMPLETED

### Post-Merge
- [ ] Monitor production logs for any routing errors
- [ ] Verify no performance degradation
- [ ] Check API response times haven't increased

---

## Rollback Plan

If issues arise after merge:

1. **Immediate Rollback:**
   ```bash
   git revert <commit-hash>
   ```

2. **Restore old automation.py:**
   ```bash
   git checkout main~1 -- src/soulspot/api/routers/automation.py
   git checkout main~1 -- src/soulspot/api/routers/__init__.py
   ```

3. **Emergency Fix:**
   - Restore backups from pre-refactoring commit
   - Redeploy previous working version
   - File critical bug report

---

## Benefits After Refactoring

✅ **Maintainability:** Each router < 350 lines (vs 1366)  
✅ **Clarity:** Single Responsibility Principle enforced  
✅ **Testing:** Isolated test files per concern  
✅ **Navigation:** Easier to find specific endpoints  
✅ **Scalability:** Simple to add new automation features  

---

## Alternative Approach (If Refactoring Too Risky)

**Lightweight Option:** Keep single file, add section markers:

```python
# automation.py

# ========== WATCHLIST ENDPOINTS ==========
@router.post("/watchlist")
...

# ========== DISCOGRAPHY ENDPOINTS ==========
@router.post("/discography/check")
...

# ========== QUALITY UPGRADE ENDPOINTS ==========
...
```

**Pros:** Zero risk, quick to implement  
**Cons:** File still large, doesn't address core issues

---

## Decision Point

**Recommendation:** ⚠️ **Defer to next sprint** unless:
- Dedicated testing time available
- No critical features in pipeline
- Automation endpoints have high test coverage (>80%)

**Current Risk:** 🟡 Medium - requires 4-6 hours + thorough testing

---

## Notes

- Router split maintains API URLs (no breaking changes)
- OpenAPI/Swagger docs should work unchanged
- Consider this pattern for `ui.py` (26 endpoints) and `library.py` (35 endpoints) if successful
