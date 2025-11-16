# HTMX Patterns in SoulSpot Bridge

> **Version:** 1.0  
> **Last Updated:** 2025-11-16  
> **Audience:** Developers

---

## 📖 Overview

This document catalogs all HTMX patterns and interactions used throughout SoulSpot Bridge's frontend. It serves as a reference for understanding how dynamic content updates, form submissions, and real-time features are implemented.

---

## 🎯 Core HTMX Attributes Used

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
| `hx-swap` | Define swap strategy | All pages |
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
| `hx-params` | Filter sent parameters | Forms |

---

## 📋 Pattern Catalog

### Pattern 1: Dynamic Content Loading

**Use Case:** Load content when page loads without JavaScript

**Implementation:**
```html
<div id="session-status" 
     hx-get="/api/auth/session" 
     hx-trigger="load"
     hx-swap="innerHTML">
    <!-- Loading placeholder -->
    <div class="spinner"></div>
</div>
```

**Backend Response:**
```html
<div class="card bg-success-50">
    <p>✅ Spotify Connected</p>
</div>
```

**Pages Using:** Dashboard, Playlists, Downloads

**Benefits:**
- Content loads after page renders (faster initial load)
- Progressive enhancement (works without JS if endpoint serves full HTML)
- Graceful degradation

---

### Pattern 2: Form Submission with Inline Feedback

**Use Case:** Submit forms without page reload, show feedback

**Implementation:**
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

**Pages Using:** Import Playlist, Settings, Auth

**Benefits:**
- No page reload
- Instant feedback
- Loading indicator automatically shown/hidden
- Error handling in HTML

---

### Pattern 3: Action Buttons with Swap Entire Element

**Use Case:** Buttons that replace themselves or parent element

**Implementation:**
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

**Pages Using:** Downloads (pause/resume/retry), Playlists (sync)

**Benefits:**
- Element updates with new state
- No JavaScript state management needed
- Server controls the UI state

---

### Pattern 4: Polling for Real-time Updates

**Use Case:** Auto-refresh content at intervals

**Implementation:**
```html
<div id="active-downloads"
     hx-get="/api/downloads/active"
     hx-trigger="every 5s"
     hx-swap="innerHTML">
    <!-- Current downloads list -->
</div>
```

**Backend Response:**
```html
<!-- Partial with updated download items -->
<div class="download-item">...</div>
<div class="download-item">...</div>
```

**Pages Using:** Downloads (progress updates), Dashboard (stats)

**Optimization:**
- Use `every 5s` or longer to avoid server overload
- Consider Server-Sent Events (SSE) for high-frequency updates (future)
- Only poll visible elements (use `hx-trigger="every 5s & revealed"`)

**Benefits:**
- Real-time feel without WebSockets
- Simple implementation
- Fallback when SSE not available

---

### Pattern 5: Autocomplete with Debouncing

**Use Case:** Search suggestions as user types

**Implementation:**
```html
<input type="text" 
       name="search" 
       hx-get="/api/search/suggestions"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#search-suggestions"
       hx-swap="innerHTML"
       placeholder="Search tracks...">

<div id="search-suggestions"></div>
```

**Backend Response:**
```html
<div class="suggestions-list">
    <a href="#" class="suggestion-item">Track 1</a>
    <a href="#" class="suggestion-item">Track 2</a>
    <a href="#" class="suggestion-item">Track 3</a>
</div>
```

**Pages Using:** Search (autocomplete)

**Key Points:**
- `delay:300ms`: Wait 300ms after last keystroke (debouncing)
- `changed`: Only trigger if value actually changed
- `keyup`: Trigger on key up event

**Benefits:**
- Reduces API calls
- Smooth user experience
- No custom JavaScript needed

---

### Pattern 6: Confirmation Dialog

**Use Case:** Ask user before destructive action

**Implementation:**
```html
<button hx-delete="/api/downloads/123"
        hx-confirm="Are you sure you want to cancel this download?"
        hx-target="closest .download-item"
        hx-swap="outerHTML swap:1s">
    ❌ Cancel
</button>
```

**Backend Response:**
```html
<!-- Element removed (empty response) or replacement content -->
```

**Pages Using:** Downloads (cancel), Settings (reset)

**Benefits:**
- Built-in confirmation
- No custom JavaScript dialog
- Browser-native behavior

---

### Pattern 7: Batch Operations

**Use Case:** Select multiple items and perform action

**Implementation:**
```html
<!-- Checkboxes -->
<input type="checkbox" class="download-checkbox" value="123">
<input type="checkbox" class="download-checkbox" value="456">

<!-- Batch action button -->
<button onclick="batchAction('pause')">Pause Selected</button>

<script>
function batchAction(action) {
    const selected = Array.from(document.querySelectorAll('.download-checkbox:checked'))
        .map(cb => cb.value);
    
    // Use HTMX to send batch request
    htmx.ajax('POST', `/api/downloads/batch/${action}`, {
        target: '#downloads-list',
        swap: 'innerHTML',
        values: { ids: selected }
    });
}
</script>
```

**Backend Response:**
```html
<!-- Updated download items list -->
```

**Pages Using:** Downloads (batch pause/resume/cancel)

**Note:** This pattern uses minimal JavaScript for checkbox state management, as HTMX doesn't natively support multi-select operations.

---

### Pattern 8: Toast Notifications on Success/Error

**Use Case:** Show feedback without replacing content

**Implementation:**
```html
<button hx-post="/api/downloads"
        hx-vals='{"track_id": "abc123"}'
        hx-swap="none"
        hx-on::after-request="showToast('Track added to queue', 'success')">
    Download
</button>
```

**JavaScript Helper:**
```javascript
function showToast(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} toast`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Auto-remove after 3 seconds
    setTimeout(() => toast.remove(), 3000);
}
```

**Pages Using:** All pages (download actions, form submissions)

**Benefits:**
- Non-intrusive feedback
- Doesn't replace content
- Can stack multiple toasts

---

### Pattern 9: Infinite Scroll / Lazy Loading

**Use Case:** Load more content when scrolling near bottom

**Implementation:**
```html
<div id="track-list">
    <!-- Initial tracks -->
    <div class="track-item">...</div>
    <div class="track-item">...</div>
</div>

<div hx-get="/api/tracks?page=2"
     hx-trigger="revealed"
     hx-swap="afterend"
     hx-target="previous div">
    <div class="loading-spinner"></div>
</div>
```

**Backend Response:**
```html
<!-- More track items -->
<div class="track-item">...</div>
<div class="track-item">...</div>

<!-- Next page trigger -->
<div hx-get="/api/tracks?page=3"
     hx-trigger="revealed"
     hx-swap="afterend"
     hx-target="previous div">
    <div class="loading-spinner"></div>
</div>
```

**Pages Using:** Search (infinite results), Library (track lists)

**Benefits:**
- Progressive loading
- Better performance with large lists
- Smooth scrolling experience

---

### Pattern 10: Modal with HTMX Content

**Use Case:** Load modal content dynamically

**Implementation:**
```html
<!-- Trigger button -->
<button hx-get="/api/tracks/123/details"
        hx-target="#modal-content"
        hx-swap="innerHTML"
        onclick="showModal()">
    View Details
</button>

<!-- Modal container -->
<div id="track-modal" class="modal hidden">
    <div class="modal-container">
        <div id="modal-content">
            <!-- Content loaded here -->
        </div>
    </div>
</div>

<script>
function showModal() {
    document.getElementById('track-modal').classList.remove('hidden');
}
</script>
```

**Backend Response:**
```html
<div class="modal-header">
    <h3>Track Details</h3>
</div>
<div class="modal-body">
    <p>Artist: John Doe</p>
    <p>Album: Great Album</p>
</div>
```

**Pages Using:** Search (track details), Downloads (error details)

**Benefits:**
- Modal content loaded on-demand
- Reduces initial page load
- Content always fresh

---

## 🔧 HTMX Event Handlers

SoulSpot Bridge uses HTMX events for custom behavior:

### Common Events

```javascript
// Handle all HTMX requests globally
document.body.addEventListener('htmx:beforeRequest', function(evt) {
    console.log('Request starting:', evt.detail);
    // Add CSRF token, auth headers, etc.
});

// Handle successful responses
document.body.addEventListener('htmx:afterSwap', function(evt) {
    console.log('Content swapped:', evt.detail);
    // Re-initialize components, update counters, etc.
});

// Handle errors
document.body.addEventListener('htmx:responseError', function(evt) {
    console.error('HTMX error:', evt.detail);
    showToast('An error occurred', 'error');
});

// Handle timeout
document.body.addEventListener('htmx:timeout', function(evt) {
    console.error('Request timeout:', evt.detail);
    showToast('Request timed out, please try again', 'warning');
});
```

**Event Catalog:**

| Event | When Fired | Use Case |
|-------|------------|----------|
| `htmx:configRequest` | Before request sent | Add headers, modify URL |
| `htmx:beforeRequest` | About to send request | Show global loading |
| `htmx:afterRequest` | Request completed | Hide global loading |
| `htmx:beforeSwap` | Before content swap | Validate response |
| `htmx:afterSwap` | After content swap | Re-init components |
| `htmx:responseError` | HTTP error (4xx, 5xx) | Show error message |
| `htmx:timeout` | Request timeout | Retry or notify user |

---

## 🎨 HTMX + TailwindCSS Integration

### Styling HTMX States

**Loading State:**
```css
.htmx-request .htmx-indicator {
    display: inline-block; /* Show spinner */
}

.htmx-request {
    opacity: 0.5; /* Dim content while loading */
    pointer-events: none; /* Prevent interaction */
}
```

**Swapping Animation:**
```css
.htmx-swapping {
    opacity: 0;
    transition: opacity 200ms ease-out;
}

.htmx-settling {
    opacity: 1;
    transition: opacity 200ms ease-in;
}
```

**Error State:**
```html
<!-- Use HTMX error classes or custom JavaScript -->
<div class="htmx-error-state" style="display: none;">
    Error occurred
</div>
```

---

## 📚 Best Practices

### 1. Progressive Enhancement

✅ **Do:**
```html
<!-- Form works without HTMX -->
<form action="/api/search" method="get" hx-get="/api/search" hx-target="#results">
    <input name="q" type="text">
    <button type="submit">Search</button>
</form>
```

❌ **Don't:**
```html
<!-- Only works with HTMX -->
<div hx-get="/api/search" hx-include="[name='q']">
    <input name="q" type="text">
    <button>Search</button>
</div>
```

### 2. Semantic HTML Targets

✅ **Do:**
```html
<button hx-post="/api/downloads/123/pause"
        hx-target="closest .download-item"
        hx-swap="outerHTML">
```

❌ **Don't:**
```html
<button hx-post="/api/downloads/123/pause"
        hx-target="#download-123-parent-container-wrapper"
        hx-swap="outerHTML">
```

### 3. Meaningful Loading States

✅ **Do:**
```html
<button hx-post="/api/submit" hx-indicator="#spinner">
    Submit
</button>
<span id="spinner" class="htmx-indicator">Processing...</span>
```

❌ **Don't:**
```html
<!-- No loading feedback -->
<button hx-post="/api/submit">Submit</button>
```

### 4. Debounce User Input

✅ **Do:**
```html
<input hx-get="/api/search" 
       hx-trigger="keyup changed delay:300ms">
```

❌ **Don't:**
```html
<!-- Fires on every keystroke -->
<input hx-get="/api/search" 
       hx-trigger="keyup">
```

### 5. Use Appropriate Swap Strategies

| Scenario | Recommended Swap |
|----------|------------------|
| Replace entire card | `outerHTML` |
| Update card content | `innerHTML` |
| Append search results | `beforeend` |
| Prepend notifications | `afterbegin` |
| Remove element | `outerHTML` (empty response) |

---

## 🐛 Common Issues & Solutions

### Issue: Content Not Swapping

**Symptom:** HTMX request succeeds but content doesn't update

**Solutions:**
1. Check `hx-target` selector is correct
2. Verify backend returns HTML (not JSON)
3. Check `hx-swap` strategy matches your intent
4. Look for JavaScript errors blocking swap

### Issue: Polling Too Frequent

**Symptom:** Server overloaded with requests

**Solutions:**
1. Increase polling interval (`every 10s` instead of `every 1s`)
2. Use `revealed` modifier to only poll visible elements
3. Consider Server-Sent Events for high-frequency updates

### Issue: Forms Submitting Twice

**Symptom:** Double submissions on form submit

**Solutions:**
1. Remove `onclick` handler if using `hx-post`
2. Use `hx-disabled-elt="this"` to disable button during submit
3. Check for duplicate event listeners

---

## 🔮 Future Enhancements

### Planned HTMX Features

1. **Server-Sent Events (SSE)**
   - Real-time download progress without polling
   - Implementation: `hx-ext="sse"` with backend SSE endpoint

2. **WebSocket Support**
   - Bidirectional real-time updates
   - Implementation: `hx-ext="ws"` with WebSocket backend

3. **Optimistic UI Updates**
   - Immediately update UI before server response
   - Rollback on error

4. **Request Queuing**
   - Queue multiple requests to avoid race conditions
   - Useful for rapid filter changes

---

## 📖 Additional Resources

- [HTMX Official Docs](https://htmx.org/docs/)
- [HTMX Examples](https://htmx.org/examples/)
- [Hypermedia Systems Book](https://hypermedia.systems/)
- [Frontend Development Roadmap](../frontend-development-roadmap.md)

---

**Version:** 1.0  
**Last Updated:** 2025-11-16  
**Maintained by:** Frontend Team
