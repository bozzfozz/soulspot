# Code Cleanup Tasks - Manual Execution Required

**Generated:** 2025-12-12  
**Status:** Identified for manual cleanup (virtual GitHub environment prevents file deletion)

---

## Widget System Cleanup

### Background
Widget system was deprecated and removed via migration `ee19001hhj49_remove_widget_system.py`. Database tables dropped, but template files and documentation references remain.

### Files to Remove

```bash
# Remove widget template directory (1 file)
rm -rf src/soulspot/templates/widget_templates/

# Verify no code references remain
grep -r "widget_templates" src/soulspot/
```

### Documentation to Update

Mark as DEPRECATED or remove widget references from:

1. **`docs/development/frontend-roadmap.md`** (line 240)
   - Remove widget_templates reference

2. **`docs/guides/developer/widget-development-guide.md`** (lines 120, 327)
   - Add DEPRECATED header
   - Or delete entire guide

3. **`docs/implementation/dashboard-implementation.md`** (line 148)
   - Remove widget auto-discovery reference

4. **`docs/project/CHANGELOG.md`** (line 90)
   - Already historical - no action needed

### Test Cleanup

**`tests/integration/api/test_endpoint_accessibility.py`** (line 255):
```python
# REMOVE THIS TEST (endpoint no longer exists)
async def test_list_widget_templates_endpoint_accessible(
    ...
)
```

---

## Obsolete CSS Files

### Investigation Needed

```bash
# List all CSS files
find src/soulspot/static/css -type f -name "*.css"

# Check which are referenced in templates
grep -r "\.css" src/soulspot/templates/
```

**Action:** Compare referenced CSS vs. existing files, remove unreferenced.

---

## Obsolete Templates

### Candidates for Review

Potentially unused templates (require manual verification):

1. **`theme-sample.html`** - Demo template, may be obsolete
2. **`ui-demo.html`** - Demo template, may be obsolete
3. **`styleguide.html`** - If no longer maintained

### Verification Steps

```bash
# Check if templates are referenced in routers
grep -r "theme-sample\|ui-demo\|styleguide" src/soulspot/api/

# Check if linked in any HTML
grep -r "href.*theme-sample\|href.*ui-demo\|href.*styleguide" src/soulspot/templates/
```

**Action:** If not referenced, mark as deprecated or remove.

---

## Router Refactoring (Optional - Low Priority)

### Large Routers to Split

| Router | Lines | Endpoints | Suggested Split |
|--------|-------|-----------|-----------------|
| `automation.py` | 1366 | 25 | `watchlists.py`, `discography.py`, `filters.py`, `rules.py`, `followed_artists.py` |
| `ui.py` | ~800+ | 26 | `ui_pages.py`, `ui_library.py`, `ui_spotify.py` |
| `library.py` | ~600+ | 15 | `library_scan.py`, `library_duplicates.py`, `library_import.py` |

**Rationale:** Improves maintainability, reduces file size, clearer responsibility separation.

**Action:** Optional refactoring - requires careful testing after split.

---

## Execution Checklist

- [ ] Remove `src/soulspot/templates/widget_templates/`
- [ ] Mark widget docs as DEPRECATED (3 files)
- [ ] Remove widget test in `test_endpoint_accessibility.py`
- [ ] Investigate obsolete CSS files
- [ ] Verify unused templates (theme-sample, ui-demo, styleguide)
- [ ] Optional: Refactor large routers

---

## Notes

- **Virtual Environment Limitation:** File deletion requires local environment with actual filesystem access
- **Testing Required:** After cleanup, run full test suite to ensure no broken references
- **Documentation Sync:** Update DOCS_STATUS.md after cleanup completion
