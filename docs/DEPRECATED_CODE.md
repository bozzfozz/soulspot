# Deprecated Code Tracking

**Purpose:** Tracks all deprecated code scheduled for removal to prevent accidental usage.

---

## 🚫 Currently Deprecated

### 1. Widget Template Registry
**File:** `src/soulspot/application/services/widget_template_registry.py`  
**Deprecated:** November 2025  
**Reason:** Widget system removed (DB tables dropped)  
**Migration:** `alembic/versions/ee19001hhj49_remove_widget_system.py`  
**Replacement:** Use SSE endpoints (`/api/sse/*`) for live updates  
**Action:** DELETE file (kept for backwards compat warning only)

---

### 2. Followed Artists Route (Old)
**Route:** `GET /automation/followed-artists`  
**Deprecated:** December 2025  
**Reason:** Moved to better auto-sync experience  
**Migration:** None needed (HTTP 410 redirect)  
**Replacement:** Use `GET /spotify/artists` instead  
**Action:** Returns HTTP 410 Gone with redirect header

---

## ✅ Recently Removed

### SpotifyBatchProcessor
**File:** `src/soulspot/application/services/batch_processor.py`  
**Removed:** December 2025  
**Reason:** Dead code (stub never implemented)  
**Replacement:** Implement in `plugins/spotify/_batch_processor.py` if needed

---

## 📋 Deprecation Workflow

When deprecating code:

1. **Mark as DEPRECATED** with clear warning:
   ```python
   # ⚠️ DEPRECATED - DO NOT USE
   raise DeprecationWarning("Use XYZ instead")
   ```

2. **Update this file** with:
   - Deprecation date
   - Reason
   - Migration path
   - Replacement
   - Action required

3. **Set removal date** (typically next major version)

4. **Document in CHANGELOG.md**

5. **Remove in next major version**

---

## 🔍 Finding Deprecated Code

```bash
# Search for deprecated markers
grep -r "DEPRECATED" src/

# Check for DeprecationWarning
grep -r "DeprecationWarning" src/

# Find HTTP 410 routes (deprecated endpoints)
grep -r "status_code=410" src/
```

---

## 📚 References

- **Migration History:** `alembic/versions/ee19001hhj49_remove_widget_system.py`
- **Architecture Decisions:** `docs/architecture/`
- **Changelog:** `CHANGELOG.md`
