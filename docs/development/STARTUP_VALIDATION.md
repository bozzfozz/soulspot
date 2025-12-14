# Startup Validation Protocol

## Agent Rule: ALWAYS Validate App Startup After Code Changes

**Mandatory Step**: After ANY code change that affects:
- Service initialization
- Dependency injection
- Worker startup
- Database connections
- External integrations

**MUST run startup validation** before marking task as complete.

## Validation Methods

### 1. Quick Validation (Preferred - Fast!)

**Import Check**: Test if main modules can be imported without errors.

```bash
# Validate main app initialization
python3 -c "from soulspot.main import create_app; print('✅ App module imports successfully')"

# Validate lifecycle initialization
python3 -c "from soulspot.infrastructure.lifecycle import lifespan; print('✅ Lifecycle imports successfully')"

# Validate critical services
python3 -c "from soulspot.application.services.auto_import import AutoImportService; print('✅ AutoImportService imports successfully')"
```

**Expected**: All imports succeed without `ImportError` or `AttributeError`.

### 2. Syntax Validation

```bash
# Check Python syntax for modified files
python3 -m py_compile src/soulspot/path/to/modified_file.py
```

### 3. Type Checking (mypy)

```bash
# Run mypy on modified files
mypy --config-file mypy.ini src/soulspot/path/to/modified_file.py
```

### 4. Full Startup Test (Comprehensive - Slow!)

**Docker Dry-Run**: Start app in test mode to verify full initialization.

```bash
# Build and start services
docker compose -f docker/docker-compose.yml up -d

# Wait for app to start
sleep 10

# Check if app is running
curl -f http://localhost:5000/health || echo "❌ App failed to start"

# Check logs for errors
docker logs soulspot 2>&1 | grep -i "error\|exception\|failed" | head -20

# Cleanup
docker compose -f docker/docker-compose.yml down
```

## Validation Checklist

After code changes, **ALWAYS run these checks**:

- [ ] **Import Check**: All modified modules import successfully
- [ ] **Syntax Check**: No syntax errors (`py_compile`)
- [ ] **Type Check**: mypy passes (if `mypy.ini` exists)
- [ ] **Error Check**: Use `get_errors` tool for real-time diagnostics
- [ ] **Dependency Check**: New imports added to requirements/pyproject.toml
- [ ] **Test Check**: Unit tests pass (`pytest tests/unit/` for modified modules)

**Optional (for critical changes):**
- [ ] **Docker Build**: `docker compose build` succeeds
- [ ] **Startup Test**: App starts without errors in Docker
- [ ] **Health Check**: `/health` endpoint responds

## Integration with TaskSync Protocol

**Updated Task Completion Flow:**

```
1. Implement code changes
2. Run import/syntax validation ← NEW!
3. Check for errors with get_errors tool ← NEW!
4. Fix any startup issues ← NEW!
5. Mark task as complete
6. Request next task
```

**Example Agent Response:**

```markdown
✅ Task completed!

**Validation Results:**
- ✅ Import check: All modules import successfully
- ✅ Syntax check: No errors found
- ✅ Type check: mypy passes
- ✅ Error check: No errors in VS Code diagnostics

Task completed. Requesting next task from terminal.
```

## Critical Services to Validate

When modifying these, **ALWAYS** run startup validation:

### Core Infrastructure
- `src/soulspot/main.py` - App factory
- `src/soulspot/infrastructure/lifecycle.py` - Startup/shutdown logic
- `src/soulspot/api/dependencies.py` - Dependency injection

### Services (Workers)
- `application/services/auto_import.py`
- `application/services/spotify_sync_service.py`
- `application/workers/*_worker.py`

### Database
- `infrastructure/persistence/repositories.py`
- `infrastructure/persistence/models.py`
- `alembic/versions/*.py`

### Configuration
- `config/settings.py`
- `pyproject.toml`
- `requirements.txt`

## Error Patterns to Watch For

Common startup failures after code changes:

### 1. Missing Dependency Injection
```python
# ❌ Added parameter but didn't update initialization
def __init__(self, new_param: NewType): ...

# ✅ Fix: Update all places where service is instantiated
```

### 2. Import Errors
```python
# ❌ Added new import but module doesn't exist
from soulspot.nonexistent import Something

# ✅ Fix: Create module or fix import path
```

### 3. Circular Dependencies
```python
# ❌ Module A imports B, B imports A
# Result: ImportError at startup

# ✅ Fix: Use TYPE_CHECKING or defer imports
```

### 4. Missing Database Columns
```python
# ❌ Code expects new column but migration not applied
track.new_field  # AttributeError!

# ✅ Fix: Run alembic upgrade head
```

## Quick Validation Script

Create this helper script for automated validation:

```bash
#!/bin/bash
# scripts/validate-startup.sh

set -e

echo "🔍 Validating application startup..."

# 1. Import check
echo "Checking imports..."
python3 -c "from soulspot.main import create_app; print('✅ Main app')"
python3 -c "from soulspot.infrastructure.lifecycle import lifespan; print('✅ Lifecycle')"

# 2. Syntax check for all Python files
echo "Checking syntax..."
find src/soulspot -name "*.py" -exec python3 -m py_compile {} \;
echo "✅ Syntax valid"

# 3. Type check
echo "Running mypy..."
mypy --config-file mypy.ini src/soulspot/ || echo "⚠️ Type errors found (non-blocking)"

# 4. Error diagnostics
echo "Checking for errors..."
# Note: This would need VS Code integration

echo ""
echo "✅ Validation complete!"
```

## When to Skip Full Docker Test

**Quick validation is sufficient for:**
- Adding new methods to existing services
- Fixing bugs in isolated functions
- Documentation changes
- Test updates

**Full Docker test required for:**
- Changing service initialization
- Adding new workers
- Modifying database schema
- Changing configuration structure
- Adding new dependencies

## Example Validation Output

```
🔍 Validating startup after Task #19...

Import Check:
✅ soulspot.main imports successfully
✅ soulspot.infrastructure.lifecycle imports successfully
✅ soulspot.application.services.auto_import imports successfully

Syntax Check:
✅ auto_import.py - No syntax errors
✅ repositories.py - No syntax errors
✅ lifecycle.py - No syntax errors

Type Check (mypy):
✅ No type errors found

Error Diagnostics:
✅ No errors in VS Code workspace

Dependency Check:
✅ All imports exist in pyproject.toml

Test Check:
✅ tests/unit/application/services/test_auto_import.py passes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ STARTUP VALIDATION PASSED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task #19 completed successfully!
```

## Integration with Copilot Instructions

**Add to `.github/copilot-instructions.md`:**

```markdown
## 19. Startup Validation (MANDATORY!)

After ANY code change affecting services, workers, or initialization:

1. **Run Import Check**: Verify modified modules can be imported
2. **Run get_errors Tool**: Check VS Code diagnostics for errors
3. **Fix Startup Issues**: Resolve any import/initialization errors
4. **Document Results**: Include validation status in task completion

**Example**:
```
✅ Task completed!
Validation: ✅ Import check passed, ✅ No errors in diagnostics
```

See: `docs/development/STARTUP_VALIDATION.md` for full protocol.
```

---

**Status**: 📋 **PROTOCOL DEFINED**  
**Next**: Add this to agent instructions and apply to all future code changes
