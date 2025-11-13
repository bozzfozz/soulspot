# Inventory: Root UI Mount & API Prefix Change

## Scan Date
2025-11-13

## Goal
- Mount UI at root (`/`) instead of `/ui`
- Move all API routes from `/api/v1` to `/api` prefix
- Update all dependent references

## Summary Statistics
- **Backend files**: 2 (main.py, routers/__init__.py)
- **Template files**: 7 HTML files with references
- **JavaScript files**: 1 (search.js)
- **Test files**: 1 (test_theme.py)
- **Documentation files**: ~10 files

---

## Backend Changes

### 1. src/soulspot/main.py
**Lines 177, 180, 339-340**

**Current:**
```python
app.include_router(api_router, prefix="/api/v1")
app.include_router(ui.router, prefix="/ui", tags=["UI"])
```

**Change to:**
```python
app.include_router(api_router, prefix="/api")
# UI router mounted at root (handled separately)
```

**Root endpoint (lines 329-341):**
- Remove the JSON root endpoint at `/`
- Replace with UI index page redirect/mount

**Decision:** CHANGE - Core requirement

---

### 2. src/soulspot/api/routers/ui.py
**All routes currently under /ui**

**Strategy:**
- Keep the router as-is
- Mount at root in main.py instead of /ui prefix
- All UI routes automatically become root-relative

**Decision:** CHANGE - Update mounting point in main.py

---

## Frontend Template Changes

### 3. src/soulspot/templates/base.html
**Lines 23, 30, 35, 40, 45, 50**

**Current UI navigation links:**
```html
<a href="/ui/">SoulSpot</a>
<a href="/ui/search">Search</a>
<a href="/ui/playlists">Playlists</a>
<a href="/ui/downloads">Downloads</a>
<a href="/ui/settings">Settings</a>
<a href="/ui/auth">Auth</a>
```

**Change to:**
```html
<a href="/">SoulSpot</a>
<a href="/search">Search</a>
<a href="/playlists">Playlists</a>
<a href="/downloads">Downloads</a>
<a href="/settings">Settings</a>
<a href="/auth">Auth</a>
```

**Decision:** CHANGE - Required for navigation

---

### 4. src/soulspot/templates/index.html
**Lines 30, 57, 81, 93, 96, 125, 146, 167, 191**

**API calls to update:**
- `hx-get="/api/v1/auth/session"` → `hx-get="/api/auth/session"`
- `href="/api/v1/auth/logout"` → `href="/api/auth/logout"`

**UI links to update:**
- `/ui/playlists` → `/playlists`
- `/ui/downloads` → `/downloads`
- `/ui/playlists/import` → `/playlists/import`
- `/ui/auth` → `/auth`

**Decision:** CHANGE - All references

---

### 5. src/soulspot/templates/import_playlist.html
**Lines 18, 33, 66, 132, 169**

**Updates needed:**
- `hx-get="/api/v1/auth/session"` → `hx-get="/api/auth/session"`
- `hx-post="/api/v1/playlists/import"` → `hx-post="/api/playlists/import"`
- `href="/ui/auth"` → `href="/auth"` (3 occurrences)

**Decision:** CHANGE

---

### 6. src/soulspot/templates/auth.html
**Lines 27, 58**

**Updates needed:**
- `hx-get="/api/v1/auth/authorize"` → `hx-get="/api/auth/authorize"`
- `hx-get="/api/v1/auth/callback"` → `hx-get="/api/auth/callback"`

**Decision:** CHANGE

---

### 7. src/soulspot/templates/settings.html
**Lines 125, 375, 462, 485, 492**

**Updates needed:**
- Default redirect URI value: `http://localhost:8000/api/v1/auth/callback` → `http://localhost:8000/api/auth/callback`
- `fetch('/api/v1/settings/')` → `fetch('/api/settings/')` (2 occurrences)
- `fetch('/api/v1/settings/reset')` → `fetch('/api/settings/reset')`
- `fetch('/api/v1/settings/defaults')` → `fetch('/api/settings/defaults')`

**Decision:** CHANGE

---

### 8. src/soulspot/templates/playlists.html
**Lines 11, 40, 61**

**Updates needed:**
- `href="/ui/playlists/import"` → `href="/playlists/import"` (2 occurrences)
- `hx-post="/api/v1/playlists/{{ playlist.id }}/sync"` → `hx-post="/api/playlists/{{ playlist.id }}/sync"`

**Decision:** CHANGE

---

### 9. src/soulspot/templates/downloads.html
**Lines 15, 21, 203, 213, 223, 233, 304, 326, 384**

**Updates needed:**
- `hx-post="/api/v1/downloads/pause"` → `hx-post="/api/downloads/pause"`
- `hx-post="/api/v1/downloads/resume"` → `hx-post="/api/downloads/resume"`
- `hx-post="/api/v1/downloads/{{ download.id }}/..."` → `hx-post="/api/downloads/{{ download.id }}/..."`
- `fetch('/api/v1/downloads/batch-action')` → `fetch('/api/downloads/batch-action')` (2 occurrences)
- `fetch(/api/v1/downloads/${downloadId}/priority)` → `fetch(/api/downloads/${downloadId}/priority)`

**Decision:** CHANGE

---

### 10. src/soulspot/templates/theme-sample.html
**Line 299**

**Updates needed:**
- `href="/ui/"` → `href="/"`

**Decision:** CHANGE

---

## JavaScript Changes

### 11. src/soulspot/static/js/search.js
**Lines 94, 186, 388, 422**

**Updates needed:**
- `fetch(/api/v1/tracks/search?...)` → `fetch(/api/tracks/search?...)` (2 occurrences)
- `fetch(/api/v1/tracks/${trackId}/download...)` → `fetch(/api/tracks/${trackId}/download...)` (2 occurrences)

**Decision:** CHANGE

---

## Test Changes

### 12. tests/integration/test_theme.py
**Lines 114, 120, 132**

**Current:**
```python
response = client.get("/ui/theme-sample")
```

**Change to:**
```python
response = client.get("/theme-sample")
```

**Decision:** CHANGE - Update test expectations

---

## Documentation Changes

### 13. Documentation Files
Multiple files reference `/ui` and `/api/v1`:
- docs/ui-screenshots.md
- docs/ui-ux-testing-report.md
- docs/history/PR10_SUMMARY.md
- docs/history/PHASE5_SUMMARY.md
- docs/analysis/initial-assessment.md
- docs/download-queue-enhancements.md
- docs/frontend-development-roadmap-archived-gridstack.md

**Strategy:**
- Update active documentation (README.md, setup guides)
- Mark historical docs with note about path changes
- Update examples and URLs

**Decision:** CHANGE - Update active docs, annotate historical docs

---

### 14. src/soulspot/api/routers/playlists.py
**Line 34**

Comment reference to `/ui/auth`:
```python
# and need to authenticate at /ui/auth first.
```

**Change to:**
```python
# and need to authenticate at /auth first.
```

**Decision:** CHANGE - Update comment

---

## Files NOT Requiring Changes

### Static Assets
- `/static` mount remains unchanged
- CSS/images paths unaffected

### Health Endpoints
- `/health`, `/ready`, `/live` remain at root level

### Database & Infrastructure
- No database schema changes
- No migration needed
- No config file changes (except examples in docs)

---

## Risk Assessment

### Low Risk
- Template URL changes (straightforward find/replace)
- Test updates (minimal tests affected)
- Documentation updates

### Medium Risk
- Backend routing changes (need careful testing)
- JavaScript fetch calls (ensure all caught)

### No Breaking Changes Expected
- Static files remain at `/static`
- Health checks remain at root
- OAuth callback URL needs updating in Spotify Developer Console (external)

---

## Estimated Effort
- Backend changes: 30 minutes
- Frontend template changes: 45 minutes
- JavaScript changes: 15 minutes
- Test updates: 15 minutes
- Documentation updates: 30 minutes
- Testing & validation: 45 minutes

**Total: ~3 hours**

---

## Testing Strategy

### Manual Testing
1. Start server: `uvicorn soulspot.main:app --reload --port 8765`
2. Test UI at `http://localhost:8765/` (should load dashboard)
3. Test navigation: Search, Playlists, Downloads, Settings, Auth pages
4. Test API endpoints: `curl http://localhost:8765/api/health`
5. Test HTMX interactions: Auth check, playlist sync, download actions
6. Test JavaScript: Search functionality, batch actions

### Automated Testing
1. Run existing tests: `pytest tests/ -v`
2. Fix any test failures related to path changes
3. Verify integration tests pass

---

## Breaking Changes Notice

**For Users/Integrations:**
- UI is now at `http://localhost:8765/` instead of `http://localhost:8765/ui`
- API endpoints are now at `/api/*` instead of `/api/v1/*`
- Update bookmarks and integrations accordingly
- Spotify OAuth redirect URI must be updated to `http://localhost:8765/api/auth/callback`

**No Compatibility Layer:**
- No redirects from old paths to new paths
- Clean break as per requirements

---

## Commit Strategy

1. **Commit 1:** Add inventory document (this file)
2. **Commit 2:** Backend routing changes (main.py, routers)
3. **Commit 3:** Template HTMX/link updates (all HTML files)
4. **Commit 4:** JavaScript API call updates
5. **Commit 5:** Test updates
6. **Commit 6:** Documentation updates

Each commit will be atomic and include only related changes.
