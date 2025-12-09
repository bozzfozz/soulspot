# Authentication & OAuth API Reference

> **Version:** 2.0  
> **Last Updated:** 9. Dezember 2025  
> **Status:** ✅ Active  
> **Related Router:** `src/soulspot/api/routers/auth.py`

---

## Overview

The Authentication API handles **Spotify OAuth 2.0 PKCE flow** and **session management**. It provides secure authentication with CSRF protection and persistent sessions across restarts.

**Key Features:**
- 🔐 **OAuth 2.0 PKCE** - Secure authorization code flow
- 🍪 **Session Management** - HttpOnly cookies, database persistence
- 🔄 **Token Refresh** - Automatic background token refresh
- 🛡️ **CSRF Protection** - OAuth state verification
- 📱 **Onboarding Integration** - First-time setup flow

---

## Endpoints

### 1. GET `/api/auth/authorize`

**Purpose:** Start Spotify OAuth authorization flow.

**Response:**
```json
{
  "authorization_url": "https://accounts.spotify.com/authorize?client_id=...&state=xyz&code_challenge=...",
  "message": "Visit the authorization_url to grant access. Your session is stored securely."
}
```

**Behavior:**
1. Generates OAuth state (CSRF token) + PKCE code verifier
2. Creates session in database
3. Sets `session_id` HttpOnly cookie
4. Returns Spotify authorization URL

**Security:**
- HttpOnly cookie prevents XSS
- SameSite=lax allows Spotify redirect
- Secure flag based on `settings.api.secure_cookies`

**Code Reference:**
```python
# src/soulspot/api/routers/auth.py (lines 27-87)
@router.get("/authorize")
async def authorize(...) -> dict[str, Any]:
    """Start OAuth authorization flow with session management."""
    ...
```

---

### 2. GET `/api/auth/callback`

**Purpose:** Handle Spotify OAuth callback (redirect after user authorization).

**Query Parameters:**
- `code` (string, required) - Authorization code from Spotify
- `state` (string, required) - OAuth state for CSRF verification
- `redirect_to` (string, default: `/`) - Redirect URL after success

**Response:**
- **302 Redirect** to `redirect_to` on success
- **400 Bad Request** if state mismatch (CSRF protection)
- **404 Not Found** if session invalid

**Security Checks:**
1. Session cookie exists and valid
2. OAuth state matches stored state (CSRF protection)
3. Code verifier exists (PKCE requirement)

**Behavior:**
1. Exchanges authorization code for access/refresh tokens
2. Updates session with tokens
3. Stores tokens in `DatabaseTokenManager` (for background workers)
4. Clears state+verifier (one-time use)
5. Redirects user to `redirect_to`

**Code Reference:**
```python
# src/soulspot/api/routers/auth.py (lines 88-196)
@router.get("/callback")
async def callback(code: str, state: str, ...) -> RedirectResponse | dict[str, Any]:
    """Handle OAuth callback from Spotify with session verification."""
    ...
```

---

### 3. POST `/api/auth/refresh`

**Purpose:** Manually refresh access token (normally happens automatically).

**Request:** None (uses session cookie)

**Response:**
```json
{
  "message": "Token refreshed successfully",
  "expires_at": "2025-12-09T16:30:00Z"
}
```

**Behavior:**
1. Checks session exists and has refresh token
2. Exchanges refresh token for new access token
3. Updates session and `DatabaseTokenManager`

**Use Cases:**
- Manual token refresh before long operation
- Testing token refresh logic

**Code Reference:**
```python
# src/soulspot/api/routers/auth.py (lines 197-269)
@router.post("/refresh")
async def refresh_token(...) -> dict[str, Any]:
    """Refresh Spotify access token."""
    ...
```

---

### 4. GET `/api/auth/session`

**Purpose:** Get current session info.

**Response:**
```json
{
  "session_id": "abc123...",
  "authenticated": true,
  "token_expires_at": "2025-12-09T16:30:00Z",
  "created_at": "2025-12-09T10:00:00Z",
  "last_accessed_at": "2025-12-09T15:30:00Z"
}
```

**Response (Unauthenticated):**
```json
{
  "session_id": null,
  "authenticated": false,
  "token_expires_at": null,
  "created_at": null,
  "last_accessed_at": null
}
```

**Use Cases:**
- Check if user is authenticated
- Show token expiry time
- Debug session issues

**Code Reference:**
```python
# src/soulspot/api/routers/auth.py (lines 270-308)
@router.get("/session")
async def get_session(...) -> dict[str, Any]:
    """Get current session information."""
    ...
```

---

### 5. POST `/api/auth/logout`

**Purpose:** Logout user (clear session).

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

**Behavior:**
1. Deletes session from database
2. Clears `session_id` cookie

**Note:** Tokens remain in `DatabaseTokenManager` for background workers.

**Code Reference:**
```python
# src/soulspot/api/routers/auth.py (lines 309-340)
@router.post("/logout")
async def logout(...) -> dict[str, Any]:
    """Logout and clear session."""
    ...
```

---

### 6. GET `/api/auth/spotify/status`

**Purpose:** Check Spotify connection status.

**Response:**
```json
{
  "connected": true,
  "authenticated": true,
  "token_valid": true,
  "token_expires_at": "2025-12-09T16:30:00Z",
  "user_display_name": "John Doe",
  "user_id": "johndoe123"
}
```

**Response (Not Connected):**
```json
{
  "connected": false,
  "authenticated": false,
  "token_valid": false,
  "token_expires_at": null,
  "user_display_name": null,
  "user_id": null
}
```

**Use Cases:**
- Onboarding wizard (check connection step)
- Settings page (show Spotify account info)
- Dashboard widgets

**Code Reference:**
```python
# src/soulspot/api/routers/auth.py (lines 341-382)
@router.get("/spotify/status")
async def spotify_status(...) -> dict[str, Any]:
    """Get Spotify connection status."""
    ...
```

---

### 7. POST `/api/auth/onboarding/skip`

**Purpose:** Skip onboarding wizard (mark as skipped for dashboard banner).

**Response:**
```json
{
  "message": "Onboarding skipped - you can complete setup later from Dashboard"
}
```

**Behavior:**
- Sets `onboarding.skipped = true` in database
- Dashboard shows "Complete Setup" banner

**Use Cases:**
- User clicks "Skip" in onboarding wizard
- Resume setup later from dashboard

**Code Reference:**
```python
# src/soulspot/api/routers/auth.py (lines 383-433)
@router.post("/onboarding/skip")
async def skip_onboarding(...) -> dict[str, str]:
    """Skip onboarding wizard."""
    ...
```

---

### 8. GET `/api/auth/token-status`

**Purpose:** Get detailed token information (expiry, refresh status).

**Response:**
```json
{
  "valid": true,
  "expires_at": "2025-12-09T16:30:00Z",
  "expires_in_minutes": 55,
  "refresh_available": true,
  "last_refresh": "2025-12-09T15:25:00Z"
}
```

**Use Cases:**
- Debug token issues
- Monitor token refresh worker
- Show token expiry countdown

**Code Reference:**
```python
# src/soulspot/api/routers/auth.py (lines 434-516)
@router.get("/token-status")
async def get_token_status(...) -> dict[str, Any]:
    """Get detailed token status information."""
    ...
```

---

### 9. POST `/api/auth/token-invalidate`

**Purpose:** Manually invalidate current token (force re-login).

**Response:**
```json
{
  "message": "Token invalidated successfully"
}
```

**Use Cases:**
- Force user to re-authenticate
- Clear corrupted token
- Testing OAuth flow

**Code Reference:**
```python
# src/soulspot/api/routers/auth.py (lines 517-542)
@router.post("/token-invalidate")
async def invalidate_token(...) -> dict[str, str]:
    """Invalidate current token (force re-login)."""
    ...
```

---

## OAuth Flow Diagram

```
┌────────────┐
│   Client   │
└─────┬──────┘
      │
      │ 1. GET /api/auth/authorize
      ├──────────────────────────────────────┐
      │                                      │
      │ 2. Redirect to Spotify               │
      │    authorization_url                 │
      └─────────────────────────────────────►│
                                             │
┌──────────────────────────────────────────┐│
│          Spotify Accounts                ││
│  User authorizes SoulSpot                ││
└──────────────────────────────────────────┘│
      │                                      │
      │ 3. Redirect to /api/auth/callback    │
      │    ?code=xxx&state=yyy               │
      ◄─────────────────────────────────────┘
      │
      │ 4. Exchange code for tokens
      │    (access_token + refresh_token)
      │
      │ 5. Redirect to redirect_to (/)
      ├──────────────────────────────────────►
      │
      │ User is now authenticated
      │ Session persists across restarts
      └────────────────────────────────────────
```

---

## Security Features

### 1. CSRF Protection
- OAuth state parameter verified on callback
- Prevents attackers from replaying authorization codes

### 2. PKCE (Proof Key for Code Exchange)
- Code verifier stored in session
- Code challenge sent to Spotify
- Prevents authorization code interception attacks

### 3. Session Security
- HttpOnly cookies (prevent XSS)
- SameSite=lax (allow Spotify redirects)
- Secure flag in production (HTTPS only)
- Session persistence (database-backed)

### 4. Token Management
- Access tokens expire after 1 hour
- Refresh tokens stored securely
- Automatic background refresh (TokenRefreshWorker)
- Tokens stored separately for background workers

---

## Summary

**9 Endpoints** for authentication & session management:

| Endpoint | Method | Purpose | Security |
|----------|--------|---------|----------|
| `/auth/authorize` | GET | Start OAuth flow | Session + PKCE |
| `/auth/callback` | GET | Handle OAuth callback | CSRF + State verification |
| `/auth/refresh` | POST | Refresh access token | Session required |
| `/auth/session` | GET | Get session info | Public |
| `/auth/logout` | POST | Logout user | Session required |
| `/auth/spotify/status` | GET | Check Spotify connection | Public |
| `/auth/onboarding/skip` | POST | Skip onboarding | Database update |
| `/auth/token-status` | GET | Get token details | Session required |
| `/auth/token-invalidate` | POST | Force re-login | Session required |

**Best Practices:**
- ✅ Always use HTTPS in production (`secure_cookies=true`)
- ✅ Never log or expose access/refresh tokens
- ✅ Use `/auth/spotify/status` for connection checks (not `/auth/session`)
- ❌ Don't store tokens in localStorage (XSS vulnerable)
- ❌ Don't disable HttpOnly on session cookies
