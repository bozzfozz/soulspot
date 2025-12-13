# Code Cleanup Tasks - Manual Execution Required

**Generated:** 2025-12-12  
**Last Updated:** 2025-12-13  
**Status:** ✅ **COMPLETED** - All high and medium priority tasks executed successfully

---

## Summary

| Category | Items | Priority | Impact |
|----------|-------|----------|--------|
| Widget System | 4 items | 🔴 High | Clean dead code |
| Unused Provider | 1 file | 🔴 High | Removed from code |
| CSS Files | 11 files | 🟡 Medium | Reduce bundle size |
| Templates | 1 file | 🟡 Medium | Clean dead code |
| Router Refactoring | 3 routers | 🟢 Low | Maintainability |

---

## Unused Email Provider 🔴 HIGH PRIORITY (NEW)

### Background
Email notification provider was removed from the notification system (decision: webhooks + in-app are sufficient).
Code references removed, but file still exists.

### File to Remove

```bash
# Remove unused email provider
rm src/soulspot/infrastructure/notifications/email_provider.py

# Verify removal
ls src/soulspot/infrastructure/notifications/  # Should show only __init__.py, inapp_provider.py, webhook_provider.py
```

---

## Widget System Cleanup 🔴 HIGH PRIORITY

### Background
Widget system was deprecated and removed via migration `ee19001hhj49_remove_widget_system.py`. Database tables dropped, but template files and documentation references remain.

### Files to Remove (verified 2025-12-13)

```bash
# Remove widget template directory (1 file)
rm -rf src/soulspot/templates/widget_templates/

# Verify removal
ls src/soulspot/templates/widget_templates/  # Should fail
```

### Test to Remove

**`tests/integration/api/test_endpoint_accessibility.py`** (line 255):
```python
# REMOVE THIS TEST (widget endpoint no longer exists)
async def test_list_widget_templates_endpoint_accessible(
    ...
)
```

### Documentation to Mark as DEPRECATED

| File | Line | Action |
|------|------|--------|
| `docs/development/frontend-roadmap.md` | 240, 537 | Add DEPRECATED header |
| `docs/guides/developer/widget-development-guide.md` | Entire file | Add DEPRECATED header or delete |
| `docs/implementation/dashboard-implementation.md` | 148 | Remove widget reference |

---

## CSS Cleanup 🟡 MEDIUM PRIORITY

### Current State (verified 2025-12-13)

**Main Production CSS:**
- `base.html` → `/static/new-ui/css/main.css` (Tailwind build) ✅ KEEP

**Old CSS Files - ONLY used by `ui-demo.html`:**
```bash
# These can be removed if ui-demo.html is deleted
rm src/soulspot/static/css/variables.css
rm src/soulspot/static/css/layout.css
rm src/soulspot/static/css/components.css
```

**Completely Unreferenced CSS Files:**
```bash
# Safe to delete - no references found anywhere
rm src/soulspot/static/css/enhancements.css
rm src/soulspot/static/css/input.css
rm src/soulspot/static/css/modern-ui.css
rm src/soulspot/static/css/style.css
rm src/soulspot/static/css/theme.css
rm src/soulspot/static/css/ui-components.css
rm src/soulspot/static/css/ui-layout.css
rm src/soulspot/static/css/ui-theme.css
```

### Verification Commands

```bash
# Check which CSS files are referenced
grep -rh "\.css" src/soulspot/templates/*.html | grep -v "cdn\|new-ui" | sort -u

# List all CSS files
ls -la src/soulspot/static/css/
```

---

## Template Cleanup 🟡 MEDIUM PRIORITY

### Analysis (verified 2025-12-13)

| Template | Status | Evidence |
|----------|--------|----------|
| `styleguide.html` | ✅ KEEP | Active route at `/styleguide` (ui.py:656) |
| `ui-demo.html` | 🗑️ DELETE | Standalone, only uses old CSS |
| `theme-sample.html` | ✅ ALREADY DELETED | Confirmed in test_theme.py:9 |

### Action

```bash
# Remove ui-demo.html (standalone demo, not needed)
rm src/soulspot/templates/ui-demo.html
```

---

## Router Refactoring 🟢 LOW PRIORITY (Optional)

### Large Routers Analysis

| Router | Lines | Endpoints | Suggested Split |
|--------|-------|-----------|-----------------|
| `automation.py` | ~1366 | 25 | `watchlists.py`, `discography.py`, `filters.py`, `rules.py` |
| `ui.py` | ~800+ | 26 | `ui_pages.py`, `ui_library.py`, `ui_spotify.py` |
| `library.py` | ~600+ | 15 | `library_scan.py`, `library_duplicates.py`, `library_import.py` |

**Rationale:** Improves maintainability, reduces cognitive load.

**Action:** Optional - only if team decides to refactor.

---

## Execution Checklist

### Phase 1: Widget System (Safe - No Production Impact) ✅ COMPLETED 2025-12-13
- [x] Remove `src/soulspot/templates/widget_templates/`
- [x] Remove test `test_list_widget_templates_endpoint_accessible` in test_endpoint_accessibility.py
- [x] Mark 3 widget docs as DEPRECATED

### Phase 2: Dead CSS (Safe - Test After) ✅ COMPLETED 2025-12-13
- [x] Remove 8 unreferenced CSS files
- [x] Remove `ui-demo.html`
- [x] Remove 3 CSS files used only by ui-demo.html
- [x] Run full test suite to verify

### Phase 3: Email Provider Cleanup ✅ ALREADY REMOVED
- [x] Email provider was already removed - confirmed no file exists

### Phase 4: Router Refactoring (Optional) ⏸️ DEFERRED
- [ ] Split `automation.py` into 4 routers
- [ ] Split `ui.py` into 3 routers
- [ ] Split `library.py` into 3 routers

**Note:** Router refactoring marked as optional - deferred for future improvement.

---

## Post-Cleanup Verification

```bash
# Run tests
pytest tests/ -v

# Check for broken imports
mypy --config-file mypy.ini src/

# Verify CSS bundle size reduced
ls -la src/soulspot/static/css/
```

---

## Notes

- **Virtual Environment Limitation:** File deletion requires local environment
- **Backup First:** Create backup branch before cleanup
- **Test Coverage:** Run full test suite after each phase
