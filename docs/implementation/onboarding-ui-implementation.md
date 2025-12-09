# Onboarding UI Implementation Documentation

> **⚠️ DEPRECATED:** This file is superseded by **onboarding-ui-overview.md** (comprehensive guide).

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

## Overview

This document describes the implementation of the onboarding UI for SoulSpot, following the problem statement requirements and using the UI 1.0 Design System.

## Implementation Summary

### Files Created

1. **`src/soulspot/templates/onboarding.html`** - Main onboarding template
2. **`src/soulspot/static/css/ui-theme.css`** - UI 1.0 design tokens (copied from `/docs/ui/`)
3. **`src/soulspot/static/css/ui-components.css`** - UI 1.0 components (copied from `/docs/ui/`)
4. **`src/soulspot/static/css/ui-layout.css`** - UI 1.0 layout utilities (copied from `/docs/ui/`)

### Files Modified

1. **`src/soulspot/templates/base.html`** - Added UI 1.0 CSS includes
2. **`src/soulspot/api/routers/ui.py`** - Added `/onboarding` route
3. **`src/soulspot/api/routers/auth.py`** - Added API endpoints and updated callback

---

## UI Design

### Layout Description

The onboarding page uses a **centered card-based layout** with the following structure:

```
┌─────────────────────────────────────────┐
│              ui-page                     │
│  ┌───────────────────────────────────┐  │
│  │       ui-container (md)           │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │      ui-card-static         │  │  │
│  │  │  ┌───────────────────────┐  │  │  │
│  │  │  │  Logo + Title         │  │  │  │
│  │  │  │  "Willkommen..."      │  │  │  │
│  │  │  └───────────────────────┘  │  │  │
│  │  │  ┌───────────────────────┐  │  │  │
│  │  │  │  Status Area          │  │  │  │
│  │  │  │  (HTMX Target)        │  │  │  │
│  │  │  └───────────────────────┘  │  │  │
│  │  │  ┌───────────────────────┐  │  │  │
│  │  │  │  [Weiter] [Skip]      │  │  │  │
│  │  │  └───────────────────────┘  │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Components Used

From UI 1.0 Design System:

**Layout Components:**
- `.ui-page` - Full page container
- `.ui-page-content` - Main content area
- `.ui-container` with `.ui-container-md` - Responsive centered container (max-width: 768px)

**Card Components:**
- `.ui-card-static` - Static card (no hover effects)
- `.ui-card-header` - Card header with title and subtitle
- `.ui-card-body` - Card body for status messages
- `.ui-card-footer` - Card footer for action buttons
- `.ui-heading-2` - Heading style
- `.ui-card-subtitle` - Subtitle text

**Button Components:**
- `.ui-btn` `.ui-btn-primary` - Primary action button (Weiter)
- `.ui-btn` `.ui-btn-ghost` - Secondary action button (Skip)
- `.ui-btn` `.ui-btn-success` - Spotify connect button (with icon)

**Alert Components:**
- `.ui-alert` `.ui-alert-success` - Success message
- `.ui-alert` `.ui-alert-info` - Info message
- `.ui-alert-icon` - Icon container
- `.ui-alert-content` - Alert content area
- `.ui-alert-title` - Alert title

**Loading Components:**
- `.ui-spinner` `.ui-spinner-lg` - Loading spinner

**Utility Components:**
- `.ui-flex` - Flexbox container
- `.ui-flex-col` - Flex column direction
- `.ui-items-center` - Align items center
- `.ui-justify-center` - Justify content center
- `.ui-gap-4` - Gap spacing
- `.ui-text-muted` - Muted text color
- `.ui-sr-only` - Screen reader only content
- `.ui-skip-link` - Skip to content link

---

## User Flow

### State Machine

```
┌──────────────┐
│   Initial    │ (Page Load)
│   Loading    │
└──────┬───────┘
       │ User clicks "Weiter"
       ▼
┌──────────────┐
│   Check      │ GET /api/spotify/status
│   Status     │
└──────┬───────┘
       │
       ├─── connected=true ──────┐
       │                         ▼
       │                  ┌──────────────┐
       │                  │   Success    │
       │                  │   Redirect   │ → Dashboard (/)
       │                  └──────────────┘
       │
       └─── connected=false ─────┐
                                 ▼
                          ┌──────────────┐
                          │   Show       │
                          │   Connect    │
                          │   Button     │
                          └──────┬───────┘
                                 │ User clicks "Spotify verbinden"
                                 ▼
                          ┌──────────────┐
                          │   OAuth      │ /api/auth/authorize
                          │   Flow       │
                          └──────┬───────┘
                                 │ Spotify redirects back
                                 ▼
                          ┌──────────────┐
                          │   Callback   │ /api/auth/callback
                          │   Handler    │
                          └──────┬───────┘
                                 │ Store tokens, redirect
                                 ▼
                          ┌──────────────┐
                          │  Dashboard   │ /
                          └──────────────┘

Alternative: User clicks "Nicht jetzt"
       │
       ▼
┌──────────────┐
│   Skip       │ POST /api/onboarding/skip
│   Onboarding │
└──────┬───────┘
       │ Redirect to dashboard
       ▼
┌──────────────┐
│  Dashboard   │ /
└──────────────┘
```

---

## API Endpoints

### 1. GET /onboarding

**Description:** Renders the onboarding page  
**Handler:** `src/soulspot/api/routers/ui.py::onboarding()`  
**Response:** HTML template  
**Status Code:** 200 OK

---

### 2. GET /api/spotify/status

**Description:** Check current Spotify connection status  
**Handler:** `src/soulspot/api/routers/auth.py::spotify_status()`  
**Authentication:** Session cookie (optional)  
**Response:**
```json
{
  "connected": true|false,
  "provider": "spotify",
  "expires_at": "ISO8601 timestamp" | null,
  "token_expired": true|false,
  "message": "string" (when not connected)
}
```
**Status Codes:**
- 200 OK - Status returned successfully

---

### 3. GET /api/auth/authorize

**Description:** Start Spotify OAuth flow  
**Handler:** `src/soulspot/api/routers/auth.py::authorize()` (existing)  
**Response:**
```json
{
  "authorization_url": "https://accounts.spotify.com/authorize?...",
  "message": "Visit the authorization_url to grant access..."
}
```
**Side Effects:**
- Creates new session
- Sets session cookie
- Stores OAuth state and PKCE verifier in session

---

### 4. GET /api/auth/callback

**Description:** Handle OAuth callback from Spotify  
**Handler:** `src/soulspot/api/routers/auth.py::callback()` (updated)  
**Query Parameters:**
- `code` (required) - Authorization code from Spotify
- `state` (required) - CSRF protection state
- `redirect_to` (optional, default: `/`) - URL to redirect after success

**Response:** HTTP 302 Redirect to `redirect_to` URL  
**Status Codes:**
- 302 Found - Successful authentication, redirect
- 400 Bad Request - State mismatch or code exchange failed
- 401 Unauthorized - No session or invalid session

**Side Effects:**
- Exchanges authorization code for access/refresh tokens
- Stores tokens in session
- Clears OAuth state and PKCE verifier

---

### 5. POST /api/onboarding/skip

**Description:** Skip onboarding and proceed to dashboard  
**Handler:** `src/soulspot/api/routers/auth.py::skip_onboarding()`  
**Authentication:** Session cookie (optional)  
**Response:**
```json
{
  "ok": true,
  "message": "Onboarding skipped. You can connect Spotify later in settings."
}
```
**Status Codes:**
- 200 OK - Skip acknowledged

**Client Behavior:** JavaScript handler redirects to `/` after receiving response.

---

## HTMX Integration

### Patterns Used

1. **Status Check on Button Click**
   ```html
   <button 
       hx-get="/api/spotify/status"
       hx-target="#onboarding-status"
       hx-swap="innerHTML"
       hx-trigger="click"
   >
   ```

2. **Skip Action**
   ```html
   <button 
       hx-post="/api/onboarding/skip"
       hx-swap="none"
   >
   ```

3. **Dynamic Content Replacement**
   - Target: `#onboarding-status` div
   - Swap: `innerHTML` (replaces content only)
   - JavaScript event handlers process HTMX responses to show appropriate UI states

---

## Accessibility Features

Following UI 1.0 Design System and WCAG 2.1 AA compliance:

1. **Skip to Content Link**
   - `.ui-skip-link` at top of page
   - Keyboard accessible (Tab to reveal)
   - Jumps to `#main-content`

2. **ARIA Labels**
   - `role="main"` on main content area
   - `aria-live="polite"` on status area (announces updates to screen readers)
   - `aria-atomic="true"` for complete announcements
   - `aria-hidden="true"` on decorative elements (logo emoji, icons)

3. **Screen Reader Support**
   - `.ui-sr-only` for screen reader only text
   - `role="status"` on loading spinner
   - Descriptive button text

4. **Keyboard Navigation**
   - All buttons keyboard accessible
   - Focus management via native HTML elements
   - Proper tab order

5. **Color Contrast**
   - Uses UI 1.0 Design System tokens (WCAG AA compliant)
   - Clear visual hierarchy with semantic colors

---

## Responsive Design

The onboarding page is **mobile-first** and responsive:

### Breakpoints (from UI 1.0 Design System)

- **Mobile:** < 640px (1 column, full width)
- **Tablet:** 640px - 768px (centered container)
- **Desktop:** > 768px (centered container, max-width: 768px)

### Responsive Behavior

- Container: `.ui-container-md` (max-width: 768px)
- Card padding adjusts via UI 1.0 utilities
- Buttons stack vertically on small screens (flexbox)
- Text remains readable at all sizes

---

## Security Considerations

1. **CSRF Protection**
   - OAuth state parameter verified on callback
   - Session-based state storage

2. **Session Security**
   - HttpOnly cookies (set by backend)
   - Secure cookies (configurable via `API_SECURE_COOKIES`)
   - SameSite=Lax for CSRF protection

3. **PKCE (Proof Key for Code Exchange)**
   - Code verifier generated and stored in session
   - Prevents authorization code interception attacks

4. **Input Validation**
   - All endpoints validate session existence
   - State parameter validated against session

---

## Testing Checklist

### Manual Testing

- [ ] Page loads correctly at `/onboarding`
- [ ] UI 1.0 styles are applied (check in browser DevTools)
- [ ] Logo and title display correctly
- [ ] "Weiter" button is initially disabled, then enabled after 1 second
- [ ] Clicking "Weiter" makes API call to `/api/spotify/status`
- [ ] When **not connected**:
  - [ ] Info alert shows "Spotify noch nicht verbunden"
  - [ ] "Spotify verbinden" button appears
  - [ ] Clicking button redirects to Spotify authorization
- [ ] When **connected**:
  - [ ] Success alert shows "Spotify ist bereits verbunden!"
  - [ ] Page redirects to `/` after 1.5 seconds
- [ ] Clicking "Nicht jetzt" redirects to `/` dashboard
- [ ] **Accessibility:**
  - [ ] Skip link works (Tab key reveals it)
  - [ ] All buttons keyboard accessible
  - [ ] Screen reader announces status changes
- [ ] **Responsive:**
  - [ ] Looks good on mobile (< 640px)
  - [ ] Looks good on tablet (640-768px)
  - [ ] Looks good on desktop (> 768px)

### OAuth Flow Testing

- [ ] OAuth flow completes successfully
- [ ] Tokens stored in session
- [ ] Callback redirects to dashboard
- [ ] State mismatch detected and rejected
- [ ] Missing session handled gracefully

---

## Known Limitations

1. **No Database Persistence**
   - Onboarding state not persisted to database
   - User can revisit `/onboarding` anytime
   - Future enhancement: Add `user.onboarding_complete` flag

2. **No Error Retry Logic**
   - If status check fails, user must refresh page
   - Future enhancement: Add retry button

3. **Logo Placeholder**
   - Currently uses emoji (🎵)
   - Should be replaced with actual SoulSpot logo SVG

---

## Future Enhancements

### Short-term

1. Add actual SoulSpot logo
2. Add error handling with retry buttons
3. Add analytics events (as specified in problem statement)
4. Persist onboarding state to database

### Long-term

1. Multi-step onboarding (welcome → connect → tutorial → done)
2. Onboarding progress indicator
3. Option to watch tutorial video
4. Customizable onboarding flow per user type

---

## Token Suggestions (Optional)

While the UI 1.0 Design System provides comprehensive tokens, the following could enhance SoulSpot-specific styling:

### Suggested Additions

```css
/* SoulSpot Brand Colors (if different from primary) */
--ui-accent-soulspot: #1DB954; /* Spotify green for integration elements */
--ui-accent-soulspot-hover: #1ed760;

/* Onboarding-specific spacing */
--ui-onboarding-card-max-width: 500px; /* Slightly narrower than md container */

/* Logo sizing */
--ui-logo-size-lg: 4rem; /* Large logo for onboarding */
--ui-logo-size-md: 3rem;
--ui-logo-size-sm: 2rem;
```

**Note:** These are suggestions only. Do NOT add to `theme.css` directly. If needed, create `src/soulspot/static/css/soulspot-custom.css`.

---

## References

- **Problem Statement:** Original requirements document
- **UI 1.0 Design System:** `/docs/ui/README_UI_1_0.md`
- **Frontend Roadmap:** `/docs/development/frontend-roadmap.md`
- **HTMX Documentation:** https://htmx.org/docs/
- **WCAG 2.1 Guidelines:** https://www.w3.org/WAI/WCAG21/quickref/

</details>

---

**Document Version:** 1.0  
**Last Updated:** 2025-11-16  
**Author:** Copilot AI Agent (Frontend Specialist)
