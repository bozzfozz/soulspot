# Startup Validation Scripts

Quick validation tools to check if code changes break app initialization.

## Quick Usage

```bash
# Run full validation
./scripts/validate-startup.sh

# Or use direct Python checks
python3 -c "from soulspot.main import create_app; print('✅ App OK')"
python3 -c "from soulspot.infrastructure.lifecycle import lifespan; print('✅ Lifecycle OK')"
```

## What Gets Validated

### 1. Import Check ✅
Tests if critical modules can be imported without errors:
- `soulspot.main` - Main app factory
- `soulspot.infrastructure.lifecycle` - Startup/shutdown logic
- `soulspot.application.services.*` - Service modules

**Catches:**
- Missing imports
- Circular dependencies
- Missing dependencies
- Syntax errors in module scope

### 2. Syntax Check ✅
Validates Python syntax for all `.py` files:
```bash
python3 -m py_compile src/soulspot/**/*.py
```

**Catches:**
- Syntax errors
- Invalid indentation
- Missing brackets/parentheses

### 3. Error Diagnostics ✅
Uses VS Code diagnostics (via `get_errors` tool):
```python
get_errors(filePaths=["path/to/modified_file.py"])
```

**Catches:**
- Type errors (mypy)
- Linter warnings (ruff)
- Import errors
- Undefined variables

## When to Run

**ALWAYS run after changes to:**

### Critical Services
- ✅ Service initialization (`__init__` methods)
- ✅ Worker startup logic
- ✅ Dependency injection (`api/dependencies.py`)
- ✅ Database models/repositories

### Configuration
- ✅ Settings (`config/settings.py`)
- ✅ Dependencies (`pyproject.toml`, `requirements.txt`)
- ✅ Environment variables (`.env.example`)

### Infrastructure
- ✅ Database migrations (`alembic/versions/*.py`)
- ✅ Lifecycle management (`infrastructure/lifecycle.py`)
- ✅ Main app factory (`main.py`)

## Example Output

### Success ✅
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 STARTUP VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  Import Check
─────────────────────────────────────────────────────────
✅ soulspot.main imports successfully
✅ soulspot.infrastructure.lifecycle imports successfully
✅ soulspot.application.services.auto_import imports successfully

2️⃣  Syntax Check
─────────────────────────────────────────────────────────
✅ No syntax errors found

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 VALIDATION SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Passed: 4
❌ Failed: 0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ STARTUP VALIDATION PASSED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Failure ❌
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 STARTUP VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  Import Check
─────────────────────────────────────────────────────────
❌ soulspot.application.services.auto_import FAILED to import
   ModuleNotFoundError: No module named 'soulspot.domain.ports'

2️⃣  Syntax Check
─────────────────────────────────────────────────────────
✅ No syntax errors found

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 VALIDATION SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Passed: 3
❌ Failed: 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ STARTUP VALIDATION FAILED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 TIP: Run with verbose error output:
   python3 -c "import sys; sys.path.insert(0, '/path/to/src'); from soulspot.application.services.auto_import import AutoImportService"
```

## Integration with CI/CD

Add to GitHub Actions workflow:

```yaml
# .github/workflows/ci.yml
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Validate startup
        run: ./scripts/validate-startup.sh
```

## Agent Protocol Integration

**TaskSync agents MUST run validation before task completion:**

```markdown
✅ Task #N completed: [Description]

**Changes:**
- Modified `service_name.py` to add new feature
- Updated `lifecycle.py` to initialize service

**Validation Results:**
- ✅ Import check: All modules import successfully
- ✅ Error check: No errors in VS Code diagnostics
- ✅ Syntax check: No syntax errors found

Files modified: [list files]

Task completed. Requesting next task from terminal.
```

See: `docs/development/STARTUP_VALIDATION.md` for full protocol.

## Troubleshooting

### Import Errors
```bash
# Check Python path
python3 -c "import sys; print('\n'.join(sys.path))"

# Check if module exists
find . -name "auto_import.py"

# Validate imports manually
python3 -c "from soulspot.application.services.auto_import import AutoImportService"
```

### Circular Dependencies
```bash
# Find circular imports
python3 -m py_compile src/soulspot/problematic_module.py
```

### Missing Dependencies
```bash
# Install missing dependencies
pip install -r requirements.txt
poetry install --with dev
```

## Advanced: Full Docker Validation

For critical changes (workers, lifecycle, migrations):

```bash
# Build and start services
docker compose -f docker/docker-compose.yml up -d

# Wait for startup
sleep 10

# Check health
curl -f http://localhost:5000/health

# Check logs for errors
docker logs soulspot 2>&1 | grep -i "error\|exception\|failed" | head -20

# Cleanup
docker compose -f docker/docker-compose.yml down
```

## Related Documentation

- `docs/development/STARTUP_VALIDATION.md` - Full validation protocol
- `.github/copilot-instructions.md` § 16.5 - Agent validation rules
- `pyproject.toml` - Dependency definitions
- `docker/docker-compose.yml` - Docker configuration

---

**Last Updated**: 2025-12-14  
**Maintainer**: GitHub Copilot (TaskSync V4)
