# Page Reference - SoulSpot Bridge

> **Version:** 1.0  
> **Last Updated:** 2025-11-16  
> **Status:** Complete

---

## 📖 Overview

This document provides a comprehensive reference for every page in SoulSpot Bridge, including URLs, features, components used, and HTMX interactions.

---

## 📄 Page Inventory

| Page | URL | Status | HTMX | Components | Description |
|------|-----|--------|------|------------|-------------|
| **Dashboard** | `/` | ✅ Complete | Yes | Stats cards, Session status | Main overview page |
| **Search** | `/search` | ✅ Complete | Yes | Filters, Autocomplete, Bulk actions | Advanced track search |
| **Playlists** | `/playlists` | ✅ Complete | Yes | Grid, Cards, Empty state | Browse all playlists |
| **Import Playlist** | `/playlists/import` | ✅ Complete | Yes | Form | Import Spotify playlists |
| **Downloads** | `/downloads` | ✅ Complete | Yes | Queue, Progress bars, Batch ops | Download queue management |
| **Auth** | `/auth` | ✅ Complete | Yes | OAuth flow | Spotify authentication |
| **Settings** | `/settings` | ⚠️ Partial | Minimal | Tabs, Forms | Configuration interface |
| **Onboarding** | `/onboarding` | ✅ Complete | Yes | Wizard | First-run setup |
| **Theme Sample** | `/theme-sample` | ✅ Complete | No | Component showcase | UI component demo |

---

## 🏠 Dashboard (`/`)

### Purpose
Main landing page showing system overview and quick actions.

### Key Features
- **Statistics Cards**: Display counts for playlists, tracks, downloads, queue size
- **Session Status Check**: Dynamic Spotify connection status via HTMX
- **Quick Actions**: Links to common tasks

### Components Used
- Card component (stats)
- Spinner component (loading)
- Alert component (session status)
- Button component

### HTMX Interactions
- **Session Status Check**:
  - `hx-get="/api/auth/session"`
  - `hx-trigger="load"`
  - `hx-swap="innerHTML"`
  - Dynamically shows connection status on page load

### Data Requirements
```python
{
    "stats": {
        "playlists": int,
        "tracks": int,
        "downloads": int,
        "queue_size": int
    }
}
```

### Accessibility
- Skip link to main content
- All stats have semantic labels
- Action buttons have aria-labels

### Performance
- Stats loaded server-side (fast initial render)
- Session check via HTMX (non-blocking)

---

## 🔍 Search (`/search`)

### Purpose
Advanced search interface for finding tracks to download.

### Key Features
- **Search Bar**: Text input with autocomplete
- **Advanced Filters**: Collapsible filter panel
  - Quality (FLAC, 320kbps, 256kbps+, any)
  - Artist filter
  - Album filter
  - Duration range
- **Search Results**: Expandable track cards
- **Bulk Actions**: Multi-select with checkbox
- **Search History**: Recent searches (localStorage)

### Components Used
- Form input (search bar)
- Collapsible sections (filters)
- Track cards (results)
- Checkbox (multi-select)
- Button group (bulk actions)
- Badge (quality indicators)

### HTMX Interactions
- **Autocomplete**:
  - `hx-get="/api/search/suggestions"`
  - `hx-trigger="keyup changed delay:300ms"`
  - `hx-target="#search-suggestions"`
  - Debounced suggestions
- **Search Submit**:
  - `hx-get="/api/search"`
  - `hx-target="#search-results"`
  - `hx-swap="innerHTML"`
- **Download Action**:
  - `hx-post="/api/downloads"`
  - `hx-vals='{"track_id": "..."}'`
  - `hx-swap="none"`
  - Toast notification on success

### JavaScript Features
- **SearchManager** module (~700 lines):
  - Client-side filtering
  - Search history management (localStorage, max 10)
  - Filter collapsing
  - Bulk selection

### Data Requirements
```python
{
    "query": str,
    "filters": {
        "quality": str,
        "artist": str,
        "album": str,
        "duration_min": int,
        "duration_max": int
    },
    "results": [
        {
            "id": str,
            "title": str,
            "artist": str,
            "album": str,
            "duration": str,
            "quality": str,
            "year": int,
            "album_art": str
        }
    ]
}
```

### Accessibility
- Filter sections have `aria-expanded` and `aria-controls`
- Checkbox selection accessible via keyboard
- Focus management for autocomplete
- Screen reader announcements for result count

### Performance
- Debounced autocomplete (300ms)
- Client-side filtering for instant response
- Lazy loading for large result sets (future)

---

## 🎵 Playlists (`/playlists`)

### Purpose
Browse and manage imported Spotify playlists.

### Key Features
- **Playlist Grid**: Card-based layout
- **Playlist Info**: Name, description, track count, source
- **Sync Action**: Update playlist from Spotify
- **Empty State**: Helpful message when no playlists

### Components Used
- Card component (playlist cards)
- Badge component (source)
- Button component (sync, import)
- Empty state component
- Skeleton loader (while loading)

### HTMX Interactions
- **Sync Playlist**:
  - `hx-post="/api/playlists/{id}/sync"`
  - `hx-swap="outerHTML"`
  - Updates card with new data

### Data Requirements
```python
{
    "playlists": [
        {
            "id": str,
            "name": str,
            "description": str,
            "track_count": int,
            "source": str,  # "spotify"
            "created_at": str  # ISO format
        }
    ]
}
```

### Accessibility
- Cards have semantic structure
- Sync buttons have descriptive aria-labels
- Grid uses responsive columns

### Performance
- Playlists loaded server-side
- Lazy image loading for playlist covers (future)

---

## ➕ Import Playlist (`/playlists/import`)

### Purpose
Import Spotify playlists into SoulSpot Bridge.

### Key Features
- **URL Input**: Accept Spotify playlist URLs or URIs
- **Format Support**: `https://open.spotify.com/playlist/...` or `spotify:playlist:...`
- **Progress Indicator**: Loading state during import
- **Success/Error Feedback**: Toast notifications

### Components Used
- Form input
- Button component
- Alert component (feedback)
- Spinner component (loading)

### HTMX Interactions
- **Import Form**:
  - `hx-post="/api/playlists/import"`
  - `hx-target="#import-result"`
  - `hx-indicator="#import-spinner"`
  - Shows result message

### Data Requirements
```python
# Request
{
    "playlist_url": str
}

# Response
{
    "success": bool,
    "message": str,
    "playlist_id": str  # if success
}
```

### Accessibility
- Form has proper labels
- Loading indicator announced to screen readers
- Error messages linked to form field

### Validation
- Client-side: URL format check
- Server-side: Spotify API validation

---

## ⬇️ Downloads (`/downloads`)

### Purpose
Manage download queue with priority controls and batch operations.

### Key Features
- **Queue Display**: List of all downloads
- **Status Filters**: All, Queued, Downloading, Completed, Failed
- **Priority Management**: P0 (high), P1 (medium), P2 (low)
- **Progress Bars**: Real-time progress for active downloads
- **Batch Operations**: Select multiple, pause/resume/cancel
- **Individual Controls**: Per-download actions
- **Drag-and-Drop**: Reorder queue (planned)

### Components Used
- Download item cards
- Status indicator component
- Priority badge component
- Progress bar component
- Checkbox (multi-select)
- Button group (actions)
- Alert component (errors)

### HTMX Interactions
- **Pause Download**:
  - `hx-post="/api/downloads/{id}/pause"`
  - `hx-target="closest .download-item"`
  - `hx-swap="outerHTML"`
- **Resume Download**:
  - `hx-post="/api/downloads/{id}/resume"`
  - `hx-swap="outerHTML"`
- **Retry Failed**:
  - `hx-post="/api/downloads/{id}/retry"`
  - `hx-swap="outerHTML"`
- **Cancel Download**:
  - `hx-delete="/api/downloads/{id}"`
  - `hx-confirm="Are you sure?"`
  - `hx-swap="outerHTML swap:1s"`

### JavaScript Features
- Batch selection management
- Filter by status
- Sort downloads (date, priority, status, progress)
- Drag-and-drop reordering (planned)

### Data Requirements
```python
{
    "downloads": [
        {
            "id": str,
            "track_id": str,
            "track_title": str,  # optional
            "artist": str,  # optional
            "status": str,  # queued, downloading, completed, failed, paused
            "priority": int,  # 0, 1, 2
            "progress_percent": float,
            "error_message": str,  # if failed
            "started_at": str,  # ISO format
            "created_at": str  # ISO format
        }
    ]
}
```

### Status Types
- **Queued** (📋): Waiting to start
- **Downloading** (⬇️): Currently downloading
- **Completed** (✓): Successfully downloaded
- **Failed** (✗): Download failed
- **Paused** (⏸️): Manually paused
- **Cancelled** (⊘): Cancelled by user

### Accessibility
- Each download item has proper ARIA labels
- Progress bars have `role="progressbar"`
- Batch operations keyboard accessible
- Drag handles have descriptive text

### Performance
- Polling for updates (every 5s)
- Only poll when page visible
- Efficient DOM updates via HTMX

---

## 🔐 Auth (`/auth`)

### Purpose
Spotify OAuth authentication and session management.

### Key Features
- **Login Button**: Initiate Spotify OAuth flow
- **Session Display**: Show current connection status
- **Disconnect**: Logout from Spotify
- **Token Info**: Expiration time, granted scopes

### Components Used
- Button component
- Alert component (status)
- Card component

### HTMX Interactions
- Minimal (OAuth handled via redirect)

### OAuth Flow
1. User clicks "Connect to Spotify"
2. Redirect to Spotify auth page
3. User grants permissions
4. Redirect back to `/auth/callback`
5. Token stored server-side
6. Return to dashboard

### Data Requirements
```python
{
    "session": {
        "has_access_token": bool,
        "token_expired": bool,
        "expires_at": str,  # ISO format
        "scopes": list[str]
    }
}
```

### Accessibility
- Clear button labels
- Status changes announced
- Error messages descriptive

---

## ⚙️ Settings (`/settings`)

### Purpose
Configure application preferences and integrations.

### Key Features
- **Tabbed Interface**: 5 categories (General, Integration, Downloads, Appearance, Advanced)
- **Form Validation**: Real-time validation
- **Save/Reset**: Persist settings or restore defaults
- **Show/Hide Secrets**: Toggle visibility for API keys

### Components Used
- Tabs component
- Form field component
- Button component
- Alert component (validation errors)

### Settings Categories

#### 1. General
- Application name
- Log level (DEBUG, INFO, WARNING, ERROR)
- Debug mode toggle

#### 2. Integration
- **Spotify**: Client ID, Secret, Redirect URI, Scopes
- **Soulseek (slskd)**: API URL, API Key, Timeout

#### 3. Downloads
- Download path
- File organization pattern
- Quality preferences
- Concurrent downloads
- Retry settings

#### 4. Appearance
- Theme (Light, Dark, Auto)
- Color scheme
- Layout density
- Font size

#### 5. Advanced
- Database settings
- Cache configuration
- API rate limiting
- Feature flags

### HTMX Interactions
- **Save Settings**:
  - `hx-post="/api/settings"`
  - `hx-swap="none"`
  - Toast notification on success
- **Reset Settings**:
  - `hx-post="/api/settings/reset"`
  - `hx-confirm="Are you sure?"`
  - Reloads form

### JavaScript Features
- Tab switching
- Show/hide password fields
- Form validation
- Unsaved changes warning (planned)

### Data Requirements
```python
{
    "settings": {
        "general": {
            "app_name": str,
            "log_level": str,
            "debug": bool
        },
        "integration": {
            "spotify_client_id": str,
            "spotify_client_secret": str,
            "slskd_api_url": str,
            "slskd_api_key": str
        },
        "downloads": {
            "download_path": str,
            "organization_pattern": str,
            "quality_preference": str,
            "concurrent_downloads": int
        },
        "appearance": {
            "theme": str,
            "color_scheme": str,
            "layout_density": str,
            "font_size": str
        },
        "advanced": { ... }
    }
}
```

### Accessibility
- Tabs keyboard navigable
- Form fields properly labeled
- Validation errors linked to fields

### Validation
- Required fields marked
- Format validation (URLs, numbers)
- Custom validation rules

---

## 🚀 Onboarding (`/onboarding`)

### Purpose
First-run setup wizard for new users.

### Key Features
- **Multi-step Wizard**: 5 steps
- **Progress Indicator**: Visual step tracker
- **Skip Option**: Bypass onboarding
- **Configuration**: Quick setup for essential settings

### Steps
1. **Welcome**: Introduction and feature overview
2. **Connect Spotify**: OAuth authorization
3. **Configure Soulseek**: slskd connection
4. **Choose Preferences**: Download settings
5. **Complete**: Summary and navigation

### Components Used
- Card component (steps)
- Button group (navigation)
- Progress indicator
- Form inputs
- Alert component

### HTMX Interactions
- **Next Step**:
  - `hx-get="/api/onboarding/step/{n}"`
  - `hx-target="#onboarding-content"`
  - `hx-push-url="true"`

### Data Requirements
```python
{
    "current_step": int,
    "total_steps": int,
    "completed_steps": list[int],
    "settings": { ... }  # collected from previous steps
}
```

### Accessibility
- Step indicator has proper ARIA labels
- Focus management between steps
- Skip link available

---

## 🎨 Theme Sample (`/theme-sample`)

### Purpose
Showcase all UI components and design system elements.

### Key Features
- **Component Gallery**: All buttons, cards, alerts, etc.
- **Color Palette**: Display all colors
- **Typography**: Font styles and sizes
- **Interactive Examples**: Working components

### Components Used
- All components (showcase)

### Usage
- Reference for developers
- Design system documentation
- Visual regression testing

---

## 📊 Component Usage Matrix

| Component | Dashboard | Search | Playlists | Import | Downloads | Auth | Settings |
|-----------|-----------|--------|-----------|--------|-----------|------|----------|
| **Alert** | ✓ | ✓ | - | ✓ | ✓ | ✓ | ✓ |
| **Badge** | - | ✓ | ✓ | - | ✓ | - | - |
| **Button** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Card** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Checkbox** | - | ✓ | - | - | ✓ | - | ✓ |
| **Empty State** | - | ✓ | ✓ | - | ✓ | - | - |
| **Form Field** | - | ✓ | - | ✓ | - | - | ✓ |
| **Progress Bar** | - | - | - | - | ✓ | - | - |
| **Skeleton** | ✓ | ✓ | ✓ | - | ✓ | - | - |
| **Spinner** | ✓ | ✓ | - | ✓ | - | ✓ | - |
| **Status Indicator** | - | - | - | - | ✓ | ✓ | - |
| **Priority Badge** | - | - | - | - | ✓ | - | - |

---

## 🔗 Page Navigation Flow

```
Dashboard (/)
  ├─→ Search (/search)
  │   └─→ Download Track (adds to queue)
  ├─→ Playlists (/playlists)
  │   ├─→ Import Playlist (/playlists/import)
  │   └─→ Sync Playlist (HTMX)
  ├─→ Downloads (/downloads)
  │   └─→ Manage Queue
  ├─→ Settings (/settings)
  └─→ Auth (/auth)
      └─→ Spotify OAuth
```

---

## 📚 Additional Resources

- [User Guide](user-guide.md)
- [HTMX Patterns Guide](htmx-patterns.md)
- [Component Library Reference](component-library.md)
- [Keyboard Navigation Guide](keyboard-navigation.md)

---

**Version:** 1.0  
**Last Updated:** 2025-11-16  
**Maintained by:** Frontend Team
