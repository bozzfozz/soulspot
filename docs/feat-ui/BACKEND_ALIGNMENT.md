# ⚠️ DEPRECATED - Backend Alignment & Integration Strategy

> **Status:** ❌ DEPRECATED  
> **Replaced By:** [SERVICE_AGNOSTIC_STRATEGY.md](./SERVICE_AGNOSTIC_STRATEGY.md) (database schema, API routes, client architecture) + `.github/copilot-instructions.md` Section 4 (Layered Architecture)  
> **Date Deprecated:** 9. Dezember 2025  
> **Reason:** Backend architecture now documented in SERVICE_AGNOSTIC_STRATEGY.md with ISRC-based cross-service matching and domain/infrastructure separation.  
> **Purpose:** ~~Bridge the gap between the new UI Prototype (`docs/feat-ui/prototype/`) and the existing Backend Architecture (`docs/implementation/`).~~ OUTDATED

**DO NOT USE THIS FILE. See [SERVICE_AGNOSTIC_STRATEGY.md](./SERVICE_AGNOSTIC_STRATEGY.md) for current backend architecture.**

---

<details>
<summary>Original Content (Archived)</summary>

---

## 1. Dashboard Architecture Gap

**Current Backend (`docs/implementation/dashboard-implementation.md`):**
- **Dynamic Widget System**: Database-driven layout (Widgets, Pages, Instances).
- **Endpoints**: `/api/ui/dashboard/canvas`, `/api/ui/widgets/{type}/content`.
- **Features**: Drag-and-drop builder, user-configurable layouts.

**New UI Prototype (`dashboard.html`):**
- **Static Layout**: Fixed grid with "Stats", "Recent Playlists", "Recent Activity".
- **Implementation**: Monolithic HTML template with HTMX polling for stats.

**Integration Strategy:**
1.  **Phase 1 (Static)**: Implement the new `dashboard.html` as the **Default Page**.
    - Map `GET /dashboard` to render the new template.
    - Create a simple `/api/stats` endpoint (or reuse existing aggregations) to feed the stats cards.
    - *Ignore* the dynamic widget system for the initial release of the new UI.
2.  **Phase 2 (Dynamic)**: Re-introduce the Widget System.
    - Refactor the "Stats Cards" and "Recent Activity" sections into independent Widget Templates (`partials/widgets/new-ui/stat-card.html`).
    - Update the `WidgetRepository` to serve these new templates.
    - Allow the frontend to load these widgets dynamically via HTMX.

---

## 2. Playlist Management API Mapping

The new `playlists.html` and `import.html` must connect to the existing API (`docs/features/playlist-management.md`).

| UI Action | Prototype Element | Target API Endpoint | Notes |
|-----------|-------------------|---------------------|-------|
| **Import** | `import.html` Form | `POST /api/playlists/import` | Payload: `{ playlist_id: "..." }` |
| **Sync Lib** | `import.html` Button | `POST /api/playlists/sync-library` | Triggers background job |
| **Sync One** | `playlist-detail.html` | `POST /api/playlists/{id}/sync` | |
| **Export** | `playlist-detail.html` | `GET /api/playlists/{id}/export/{fmt}` | Formats: m3u, csv, json |
| **Download**| `playlist-detail.html` | `POST /api/playlists/{id}/download-missing` | Triggers download manager |

---

## 3. Onboarding Flow Integration

The new `onboarding.html` is a standalone wizard. The backend needs to support this stateful flow.

**Requirements:**
- **State Persistence**: Store "Onboarding Completed" flag in User Settings / DB.
- **Endpoints Needed**:
    - `POST /api/setup/soulseek`: Validate and save credentials.
    - `POST /api/setup/spotify`: Initiate OAuth flow (redirect).
    - `POST /api/setup/finish`: Mark onboarding as done and redirect to Dashboard.

---

## 4. Component System Migration

**Legacy (`docs/guides/developer/component-library.md`):**
- Relied on `src/soulspot/templates/includes/_components.html`.
- Used Bootstrap-like classes.

**New System (`docs/feat-ui/prototype/templates/new-ui/includes/macros.html`):**
- Uses Tailwind CSS utility classes.
- **Action**: Deprecate the old `_components.html` and replace usages with new macros incrementally.

---

## 5. Next Steps for Backend Developers

1.  **Review `docs/feat-ui/prototype/static/new-ui/js/app.js`**:
    - Note the `SoulSpot` namespace and event delegation logic.
    - Ensure backend templates include this script.
2.  **Implement `/api/stats`**:
    - Return JSON or HTML fragment for the dashboard stats.
3.  **Update Routes**:
    - Point `/` and `/dashboard` to the new templates.
    - Ensure `base.html` context (User object, Sidebar stats) is populated.
