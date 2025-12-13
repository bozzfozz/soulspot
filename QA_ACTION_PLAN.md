# 🚀 QA Quick Action Plan

**Goal:** Fix blocking issues and get tests passing

---

## ⚡ Fix 1: Import Error (5 minutes)

**Problem:** `notifications.py` imports non-existent `get_session` function

**Location:** `src/soulspot/api/routers/notifications.py:25`

**Current Code:**
```python
from soulspot.infrastructure.persistence.database import get_session
```

**Fix:**
```python
from soulspot.api.dependencies import get_db_session
```

**Also update usage in the same file:**
```python
# Find and replace:
# FROM: session: AsyncSession = Depends(get_session)
# TO:   session: AsyncSession = Depends(get_db_session)
```

**Command:**
```bash
# Quick fix (Linux/Mac):
sed -i 's/from soulspot.infrastructure.persistence.database import get_session/from soulspot.api.dependencies import get_db_session/' \
  src/soulspot/api/routers/notifications.py

sed -i 's/Depends(get_session)/Depends(get_db_session)/g' \
  src/soulspot/api/routers/notifications.py
```

**Verify:**
```bash
pytest tests/unit/api/test_playlist_import.py -v
```

**Impact:** Unblocks 3+ test files

---

## ⚡ Fix 2: DTO Constructor Mismatches (30-60 minutes)

**Problem:** `deezer_plugin.py` passes wrong keyword arguments to DTO constructors

**Location:** `src/soulspot/infrastructure/plugins/deezer_plugin.py`

**Affected DTOs:**
- `UserProfileDTO` (line 335)
- `ArtistDTO` (lines 554, ...)
- `PlaylistDTO` (lines 971, 1069, ...)
- `AlbumDTO` (line 1187, ...)
- `PaginatedResponse` (lines 485, 570, 644, ...)

**Strategy:**

1. **Review DTO definitions:**
   ```bash
   # Check what fields each DTO expects
   grep -A20 "class UserProfileDTO" src/soulspot/domain/entities/
   grep -A20 "class ArtistDTO" src/soulspot/domain/entities/
   grep -A20 "class PlaylistDTO" src/soulspot/domain/entities/
   ```

2. **Common issues:**
   - Using `id` instead of actual field name
   - Using `external_url` instead of `external_urls` (plural)
   - Using `has_more` instead of correct pagination field
   - Adding extra fields like `service` that don't exist

3. **Fix pattern:**
   ```python
   # WRONG:
   ArtistDTO(
       id=deezer_id,
       service="deezer",
       external_url=url,
   )
   
   # RIGHT (example - check actual DTO definition):
   ArtistDTO(
       artist_id=deezer_id,
       external_urls={"deezer": url},
   )
   ```

**Verify:**
```bash
mypy src/soulspot/infrastructure/plugins/deezer_plugin.py
```

**Impact:** Fixes ~50 mypy errors, prevents runtime crashes

---

## ⚡ Fix 3: Method Name Errors (15 minutes)

**Problem:** Code uses `get_str()` but method is named `get_string()`

**Locations:**
- `src/soulspot/application/services/credentials_service.py` (multiple lines)
- `src/soulspot/infrastructure/notifications/webhook_provider.py` (3 lines)

**Strategy:**

1. **Check actual method name:**
   ```bash
   grep -n "def get_str\|def get_string" \
     src/soulspot/application/services/app_settings_service.py
   ```

2. **If method is `get_string()`:**
   ```bash
   # Replace all occurrences
   sed -i 's/\.get_str(/.get_string(/g' \
     src/soulspot/application/services/credentials_service.py
   
   sed -i 's/\.get_str(/.get_string(/g' \
     src/soulspot/infrastructure/notifications/webhook_provider.py
   ```

3. **OR if method is `get_str()`:**
   - Add type stub or alias in AppSettingsService
   - OR: Suppress mypy errors with `# type: ignore[attr-defined]`

**Verify:**
```bash
mypy src/soulspot/application/services/credentials_service.py
mypy src/soulspot/infrastructure/notifications/webhook_provider.py
```

**Impact:** Fixes ~15 mypy errors

---

## ⚡ Fix 4: Duplicate Function Definitions (5 minutes)

**Problem:** Functions defined twice in `downloads.py`

**Location:** `src/soulspot/api/routers/downloads.py`

**Duplicates:**
- `cancel_download` (line 510 vs line 965)
- `retry_download` (line 579 vs line 1007)
- `update_download_priority` (line 633 vs line 1054)

**Strategy:**

1. **Review both definitions:**
   ```bash
   # Check first definition
   sed -n '510,550p' src/soulspot/api/routers/downloads.py
   
   # Check duplicate
   sed -n '965,1005p' src/soulspot/api/routers/downloads.py
   ```

2. **Determine which to keep:**
   - If identical: Delete the second one
   - If different: Rename one (e.g., `cancel_download_v2`) or merge

3. **Remove duplicate:**
   ```python
   # Manually edit the file and remove lines 965-1054
   # OR use your editor's "Go to line" feature
   ```

**Verify:**
```bash
mypy src/soulspot/api/routers/downloads.py | grep "no-redef"
```

**Impact:** Fixes 3 mypy errors, improves code clarity

---

## ⚡ Quick Wins: Auto-Fixable Issues (2 minutes)

**Ruff auto-fixes:**
```bash
ruff check src/ tests/ --fix
```

**Expected:** Fixes 3 out of 136 ruff errors automatically

---

## 📊 Progress Tracking

After each fix, re-run the corresponding tool:

```bash
# After Fix 1 (Import):
pytest tests/ --co -q

# After Fix 2 (DTOs):
mypy src/soulspot/infrastructure/plugins/deezer_plugin.py

# After Fix 3 (Method names):
mypy src/soulspot/application/services/credentials_service.py

# After Fix 4 (Duplicates):
mypy src/soulspot/api/routers/downloads.py

# After all fixes:
pytest tests/ -v -m "not slow"
mypy src/soulspot
```

---

## 🎯 Success Criteria

**After all fixes:**

- ✅ Pytest: 0 collection errors, 960 tests collected
- ✅ Mypy: <200 errors (from 245)
- ✅ Ruff: <135 errors (from 136)
- ✅ All tests pass (or at least run)

**Then proceed to:**
1. Run full test suite with coverage
2. Address remaining mypy errors (type safety)
3. Clean up stub implementations (ruff warnings)

---

## 🛠️ Full Fix Script (Use with Caution!)

**WARNING:** Review changes before committing!

```bash
#!/bin/bash
set -e

echo "🔧 Applying QA fixes..."

# Fix 1: Import error
echo "Fix 1/4: Fixing import in notifications.py..."
sed -i 's/from soulspot.infrastructure.persistence.database import get_session/from soulspot.api.dependencies import get_db_session/' \
  src/soulspot/api/routers/notifications.py
sed -i 's/Depends(get_session)/Depends(get_db_session)/g' \
  src/soulspot/api/routers/notifications.py

# Fix 2: Method name (if get_string is correct)
echo "Fix 3/4: Fixing method names..."
sed -i 's/\.get_str(/.get_string(/g' \
  src/soulspot/application/services/credentials_service.py
sed -i 's/\.get_str(/.get_string(/g' \
  src/soulspot/infrastructure/notifications/webhook_provider.py

# Fix 3: Auto-fixable ruff issues
echo "Fix 4/4: Running ruff auto-fix..."
ruff check src/ tests/ --fix

echo "✅ Automated fixes applied!"
echo ""
echo "⚠️  Manual fixes still needed:"
echo "  - Fix 2: DTO constructor mismatches (deezer_plugin.py)"
echo "  - Fix 4: Remove duplicate function definitions (downloads.py)"
echo ""
echo "🧪 Verify with:"
echo "  pytest tests/ --co -q"
echo "  mypy src/soulspot"
```

**Usage:**
```bash
chmod +x fix_qa_issues.sh
./fix_qa_issues.sh
```

---

## 📚 Resources

- **Full QA Report:** `QA_REPORT_2025-12-13.md`
- **Command Reference:** `QA_RUN_SUMMARY.md`
- **Command Cheatsheet:** `QA_COMMANDS.md`

---

**Last Updated:** 2025-12-13  
**Estimated Time:** 1-2 hours for all fixes
