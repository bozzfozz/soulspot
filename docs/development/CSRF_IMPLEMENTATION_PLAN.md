# CSRF Protection Implementation Plan

> **⚠️ DEPRECATED - PARTIALLY IMPLEMENTED:** OAuth CSRF protection is complete (2025, see `auth.py` lines 134-137). General form CSRF protection (X-CSRF-Token headers) remains as future enhancement.

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

## Overview
Cross-Site Request Forgery (CSRF) protection is needed for state-changing operations (POST, PUT, DELETE, PATCH).

## Current State
- OAuth flow has CSRF protection via `state` parameter
- Regular POST/PUT/DELETE endpoints have NO CSRF protection
- HTMX requests need CSRF tokens embedded

## Implementation Strategy

### 1. CSRF Token Generation & Storage
- Generate cryptographically secure tokens using `secrets.token_urlsafe()`
- Store tokens in session (already have SessionStore)
- Tokens should be short-lived (default: 1 hour)

### 2. CSRF Token Distribution
- Set CSRF token as a cookie (separate from session cookie)
- Cookie should be:
  - `httponly=False` (JavaScript needs to read it)
  - `secure=True` in production
  - `samesite="strict"` or `"lax"`

### 3. CSRF Token Validation
- Create FastAPI dependency `verify_csrf_token()`
- Check token from:
  1. Header: `X-CSRF-Token` (for AJAX/HTMX)
  2. Form field: `csrf_token` (for regular forms)
- Compare with session-stored token
- Raise 403 if mismatch or missing

### 4. Integration Points

#### Backend (FastAPI)
```python
# src/soulspot/infrastructure/security/csrf.py
- CSRFProtection class
- generate_csrf_token()
- verify_csrf_token() dependency
```

#### Frontend (HTMX)
```html
<!-- All HTMX POST/PUT/DELETE requests -->
<button hx-post="/api/endpoint" 
        hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'>
</button>

<!-- Regular forms -->
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
</form>
```

### 5. Exempt Endpoints
- OAuth callback (already has state parameter)
- Public read-only endpoints (GET, HEAD, OPTIONS)
- Webhook endpoints (if any) - use different authentication

### 6. Affected Endpoints
Priority order for implementation:

**Critical (data modification):**
- `/playlists/import` (POST)
- `/tracks/{track_id}/download` (POST)
- `/downloads/{download_id}/cancel` (PUT/DELETE)
- `/library/scan` (POST)

**High (configuration changes):**
- `/settings` (POST/PUT)
- `/widgets` (POST/PUT/DELETE)
- `/auth/logout` (POST)

**Medium (user preferences):**
- `/dashboards/{id}` (PUT/DELETE)
- `/watchlist` (POST/DELETE)

### 7. Testing Requirements
- Unit tests for CSRF token generation/validation
- Integration tests for protected endpoints:
  - Request without token → 403
  - Request with invalid token → 403
  - Request with valid token → Success
  - Token reuse prevention
  - Token expiration

### 8. Alternative: Double Submit Cookie Pattern
Simpler implementation without session storage:
1. Generate random token
2. Set as cookie AND include in request
3. Validate they match
4. No server-side storage needed

## Recommended Libraries
- `starlette-csrf` - Lightweight, FastAPI-compatible
- Custom implementation - Full control, learn by doing

## Implementation Steps
1. Create CSRF module in `infrastructure/security/`
2. Add CSRF dependency to affected endpoints
3. Update templates to include CSRF tokens
4. Add JavaScript for HTMX CSRF header injection
5. Write comprehensive tests
6. Document usage in README

## Rollout Strategy
1. Implement core CSRF module
2. Apply to auth endpoints first (logout)
3. Apply to high-risk endpoints (playlists, downloads)
4. Gradually roll out to all POST/PUT/DELETE endpoints
5. Add to all HTMX templates

## Monitoring
- Log CSRF validation failures
- Alert on high failure rates (potential attack)
- Track token generation/validation metrics

## Documentation
- Update API documentation (OpenAPI)
- Add developer guide for CSRF
- Frontend integration examples

---

**Status:** Ready for implementation  
**Estimated Effort:** 4-6 hours  
**Priority:** High (Security)
