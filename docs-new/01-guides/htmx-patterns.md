# HTMX Patterns in SoulSpot

**Category:** Developer Guide  
**Version:** 1.0  
**Last Updated:** 2025-01  
**Audience:** Developers

---

## Overview

Catalog of all HTMX patterns and interactions used in SoulSpot's frontend.

---

## Core HTMX Attributes

### Request Attributes

| Attribute | Usage | Example Pages |
|-----------|-------|---------------|
| `hx-get` | Load content dynamically | Dashboard (session status), Search (autocomplete) |
| `hx-post` | Submit forms, trigger actions | Downloads (pause/resume), Playlists (sync) |
| `hx-delete` | Delete resources | Downloads (cancel) |
| `hx-patch` | Update resources | Settings (save) |

### Response Handling

| Attribute | Usage | Example Pages |
|-----------|-------|---------------|
| `hx-target` | Specify where to swap content | All pages |
| `hx-swap="innerHTML"` | Replace inner content (default) | Dashboard stats |
| `hx-swap="outerHTML"` | Replace entire element | Download items |
| `hx-swap="beforeend"` | Append to end | Search results |
| `hx-swap="afterbegin"` | Prepend to start | Notifications |

### Triggers

| Attribute | Usage | Example Pages |
|-----------|-------|---------------|
| `hx-trigger="load"` | Trigger on page load | Dashboard (session check) |
| `hx-trigger="click"` | Trigger on click (default) | Buttons |
| `hx-trigger="change"` | Trigger on input change | Filters |
| `hx-trigger="every 5s"` | Poll every N seconds | Downloads (status updates) |
| `hx-trigger="revealed"` | Trigger when scrolled into view | Infinite scroll |

### Additional Attributes

| Attribute | Usage | Example Pages |
|-----------|-------|---------------|
| `hx-vals` | Send additional JSON data | Downloads (track_id) |
| `hx-headers` | Custom request headers | CSRF tokens |
| `hx-confirm` | Confirmation dialog | Delete actions |
| `hx-indicator` | Show loading spinner | Form submissions |
| `hx-push-url` | Update browser URL | Navigation |

---

## Common Patterns

### Pattern 1: Dynamic Content Loading

**Use Case:** Load content when page loads without JavaScript

```html
<div id="session-status" 
     hx-get="/api/auth/session" 
     hx-trigger="load"
     hx-swap="innerHTML">
    <div class="spinner"></div>
</div>
```

**Backend Response:**
```html
<div class="card bg-success-50">
    <p>✅ Spotify Connected</p>
</div>
```

**Pages:** Dashboard, Playlists, Downloads

---

### Pattern 2: Form Submission with Inline Feedback

**Use Case:** Submit forms without page reload, show feedback

```html
<form hx-post="/api/playlists/import"
      hx-target="#import-result"
      hx-swap="innerHTML"
      hx-indicator="#import-spinner">
    <input type="text" name="playlist_url" required>
    <button type="submit">Import</button>
    <span id="import-spinner" class="htmx-indicator spinner"></span>
</form>

<div id="import-result"></div>
```

**Backend Response (Success):**
```html
<div class="alert alert-success">
    ✅ Playlist imported successfully!
</div>
```

**Backend Response (Error):**
```html
<div class="alert alert-danger">
    ❌ Invalid playlist URL
</div>
```

**Pages:** Import Playlist, Settings, Auth

---

### Pattern 3: Action Buttons with Element Swap

**Use Case:** Buttons that replace themselves or parent element

```html
<div class="download-item" id="download-123">
    <p>Downloading: Track.mp3</p>
    <button hx-post="/api/downloads/123/pause"
            hx-target="closest .download-item"
            hx-swap="outerHTML">
        ⏸️ Pause
    </button>
</div>
```

**Backend Response:**
```html
<div class="download-item" id="download-123">
    <p>Paused: Track.mp3</p>
    <button hx-post="/api/downloads/123/resume"
            hx-target="closest .download-item"
            hx-swap="outerHTML">
        ▶️ Resume
    </button>
</div>
```

**Pages:** Downloads

---

### Pattern 4: Real-time Polling

**Use Case:** Auto-update content every N seconds

```html
<div id="downloads-queue"
     hx-get="/api/downloads/queue"
     hx-trigger="load, every 5s"
     hx-swap="innerHTML">
    Loading...
</div>
```

**Backend Response:**
```html
<div class="download-list">
    <!-- Updated download items -->
</div>
```

**Pages:** Downloads (queue status)

---

### Pattern 5: Autocomplete Search

**Use Case:** Show suggestions as user types

```html
<input type="text"
       name="query"
       hx-get="/api/search/autocomplete"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#autocomplete-results"
       placeholder="Search...">

<div id="autocomplete-results"></div>
```

**Backend Response:**
```html
<ul class="autocomplete-list">
    <li>Bohemian Rhapsody - Queen</li>
    <li>Stairway to Heaven - Led Zeppelin</li>
</ul>
```

**Pages:** Search

---

### Pattern 6: Confirmation Dialogs

**Use Case:** Confirm destructive actions

```html
<button hx-delete="/api/downloads/123"
        hx-confirm="Are you sure you want to cancel this download?"
        hx-target="closest .download-item"
        hx-swap="outerHTML">
    ❌ Cancel
</button>
```

**Pages:** Downloads (cancel), Playlists (delete)

---

### Pattern 7: Infinite Scroll

**Use Case:** Load more content when scrolling to bottom

```html
<div class="track-list">
    <!-- Existing tracks -->
</div>

<div hx-get="/api/tracks?page=2"
     hx-trigger="revealed"
     hx-swap="afterend">
    Loading more...
</div>
```

**Backend Response:**
```html
<div class="track-list">
    <!-- New tracks -->
</div>

<div hx-get="/api/tracks?page=3"
     hx-trigger="revealed"
     hx-swap="afterend">
    Loading more...
</div>
```

**Pages:** Library (tracks list)

---

### Pattern 8: Bulk Actions

**Use Case:** Perform actions on multiple selected items

```html
<form hx-post="/api/downloads/bulk/pause"
      hx-vals='js:{"track_ids": getSelectedTrackIds()}'
      hx-target="#bulk-result">
    
    <div class="track-list">
        <input type="checkbox" name="track_id" value="123">
        <input type="checkbox" name="track_id" value="456">
    </div>
    
    <button type="submit">Pause Selected</button>
</form>

<div id="bulk-result"></div>
```

**Backend Response:**
```html
<div class="alert alert-success">
    ✅ Paused 2 downloads
</div>
```

**Pages:** Downloads, Library Tracks

---

## Best Practices

### 1. Always Provide Loading Indicators

```html
<button hx-post="/api/action"
        hx-indicator="#spinner">
    Submit
</button>
<span id="spinner" class="htmx-indicator">⏳ Processing...</span>
```

### 2. Use Correlation IDs for Debugging

```html
<div hx-get="/api/data"
     hx-headers='{"X-Correlation-ID": "unique-id"}'>
</div>
```

### 3. Progressive Enhancement

Ensure forms work without JavaScript (submit to same endpoint):

```html
<form action="/api/playlists/import" method="post"
      hx-post="/api/playlists/import"
      hx-target="#result">
    <!-- Works with or without HTMX -->
</form>
```

### 4. Error Handling

Return HTML error messages for HTMX to display:

```python
@router.post("/import")
async def import_playlist(url: str):
    try:
        # Import logic
        return templates.TemplateResponse("success.html", ...)
    except ValidationError:
        return templates.TemplateResponse(
            "error.html",
            {"message": "Invalid playlist URL"},
            status_code=400
        )
```

---

## Troubleshooting

### HTMX Request Not Firing

**Check:**
- Element has `hx-*` attribute
- Target element exists with correct ID
- Network tab shows request (F12 → Network)
- Browser console for JavaScript errors

### Response Not Swapping

**Check:**
- `hx-target` selector is correct
- `hx-swap` strategy matches expected behavior
- Backend returns HTML (not JSON)
- Response status code is 2xx

### Polling Not Working

**Check:**
- `hx-trigger="every Xs"` syntax correct
- Network tab shows periodic requests
- Backend responds within timeout

---

## Related Documentation

- [Testing Guide](./testing-guide.md) - Manual testing strategies
- [UI/UX Visual Guide](./ui-ux-visual-guide.md) - Component showcase
- [User Guide](/guides/user-guide.md) - End-user features

---

**Version:** 1.0  
**Last Updated:** 2025-01
