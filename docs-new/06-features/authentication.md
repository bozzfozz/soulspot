# Authentication

**Category:** Features  
**Last Updated:** 2025-01-06  
**Related Docs:** [Auth Patterns](../04-architecture/auth-patterns.md) | [Setup Guide](../01-guides/setup-guide.md)

---

## Overview

SoulSpot uses **OAuth 2.0** for secure authentication with streaming services. Users connect their accounts via Settings page, granting SoulSpot permission to access their music library.

**Supported Services:**

| Service | Auth Type | Status | Use Case |
|---------|-----------|--------|----------|
| **Spotify** | OAuth 2.0 PKCE | ✅ Active | User library sync, followed artists, playlists |
| **Deezer** | OAuth 2.0 + Public API | ✅ Active | Browse (no auth), user favorites (auth required) |

---

## Quick Start

### Connecting Spotify

1. **Open Settings** → Navigate to `/settings?tab=spotify`
2. **Click "Connect Spotify"** → Redirects to Spotify login
3. **Authorize SoulSpot** → Grant requested permissions:
   - Read private playlists
   - Read liked songs
   - Read followed artists
   - Read user profile
4. **Done!** → Redirected back to SoulSpot with active session

### Connecting Deezer

1. **Open Settings** → Navigate to `/settings?tab=deezer`
2. **Click "Connect Deezer"** → Redirects to Deezer login
3. **Authorize SoulSpot** → Grant permissions
4. **Done!** → Long-lived token stored (no refresh needed)

**Note:** Deezer's public API (browse, search, new releases) works **without authentication**. OAuth only needed for user-specific features (favorites, playlists).

---

## Session Management

### How Sessions Work

**Architecture:**
```
Browser Cookie (session_id)
    ↓
Database Session (spotify_sessions / deezer_sessions)
    ↓
OAuth Tokens (access_token, refresh_token)
```

**Session Lifecycle:**

1. **Login:** User authorizes → OAuth callback → Tokens stored in database
2. **Session Cookie:** HttpOnly cookie with unique `session_id` set in browser
3. **Token Refresh:** Background worker refreshes Spotify tokens before expiry (1h lifetime)
4. **Persistence:** Sessions survive page refreshes, browser restarts, app restarts

**Sessions Expire When:**
- ❌ User clicks "Disconnect" in Settings
- ❌ Refresh token revoked by service
- ❌ Session inactive for 30+ days (auto-cleanup)

**Source:** `src/soulspot/infrastructure/persistence/models.py` (SpotifySessionModel, DeezerSessionModel)

---

## Security Features

### PKCE (Proof Key for Code Exchange)

SoulSpot uses **PKCE** for Spotify OAuth (most secure flow):

**How it works:**
1. Generate random `code_verifier` (64-byte string)
2. Calculate `code_challenge = SHA256(code_verifier)`
3. Send `code_challenge` to Spotify in authorization URL
4. Store `code_verifier` in session (database)
5. Exchange authorization code + `code_verifier` for tokens

**Benefits:**
- ✅ No client secret in browser
- ✅ One-time verifier per authorization
- ✅ Prevents authorization code interception attacks

**Source:** `src/soulspot/infrastructure/plugins/spotify_plugin.py` (get_auth_url, handle_callback)

---

### CSRF Protection

**State Parameter Validation:**
- Random `oauth_state` generated on login
- Stored in session database
- Verified on callback (must match!)
- Prevents cross-site request forgery

**Implementation:**
```python
# Login: generate state
oauth_state = secrets.token_urlsafe(32)
session.oauth_state = oauth_state

# Callback: verify state
if session.oauth_state != state:
    raise HTTPException(400, "Invalid OAuth state - possible CSRF attack")
```

**Source:** `src/soulspot/api/routers/auth.py` (lines 52-145)

---

### Secure Cookies

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `HttpOnly` | true | JavaScript cannot access cookie (prevents XSS) |
| `SameSite` | Lax | Allows OAuth redirects, blocks CSRF |
| `Secure` | true (production) | HTTPS only (not in dev mode) |
| `Path` | / | Available site-wide |

**Example:**
```python
response.set_cookie(
    key="session_id",
    value=session.session_id,
    httponly=True,
    secure=True,  # Production only
    samesite="lax",
)
```

---

## Permission Scopes

### Spotify Scopes

SoulSpot requests these permissions:

| Scope | Purpose | Used For |
|-------|---------|----------|
| `user-read-private` | Basic profile info | User identification |
| `user-read-email` | Email address | User account linking |
| `user-library-read` | Liked Songs | Track import |
| `user-follow-read` | Followed Artists | Artist sync |
| `playlist-read-private` | Private playlists | Playlist import |
| `playlist-read-collaborative` | Collaborative playlists | Playlist import |

**Why these scopes?**
- Read-only access (SoulSpot never modifies Spotify data)
- Minimum required for core features
- User controls what data is synced

---

### Deezer Scopes

| Scope | Purpose | Used For |
|-------|---------|----------|
| `basic_access` | Public profile | User identification |
| `email` | Email address | Account linking |
| `manage_library` | User library access | Favorites import |
| `offline_access` | Long-lived token | Background sync |

**Key Difference:** Deezer tokens are long-lived (~30 days), no automatic refresh.

---

## Token Storage

### Dual Storage Architecture

SoulSpot stores tokens in **two separate locations**:

**1. User Sessions (`spotify_sessions` / `deezer_sessions` tables):**
- Per-browser session
- Supports multiple users
- Used for user-initiated requests (UI actions)

**2. Background Worker Tokens (`spotify_tokens` table):**
- Single shared token
- Used by all background workers
- Managed by DatabaseTokenManager
- Auto-refreshed by TokenRefreshWorker

**Why separate?**
- Users can have multiple browsers → each needs own session
- Workers need single reliable token → shared token store

**Source:** `src/soulspot/infrastructure/integrations/database_token_manager.py`

---

## Authentication Flow

### Spotify OAuth Flow (with PKCE)

```
1. User clicks "Connect Spotify"
   ↓
2. Generate: session_id, oauth_state, code_verifier
   ↓
3. Redirect to Spotify authorization URL
   (includes: code_challenge, state, scopes)
   ↓
4. User authorizes on Spotify
   ↓
5. Spotify redirects to callback with: code, state
   ↓
6. Verify state matches stored value
   ↓
7. Exchange code + code_verifier for tokens
   ↓
8. Store tokens in:
   - spotify_sessions (user token)
   - spotify_tokens (worker token)
   ↓
9. Set session_id cookie
   ↓
10. Redirect to /
```

**Source:** `src/soulspot/api/routers/auth.py` (spotify_login, spotify_callback)

---

### Deezer OAuth Flow (simple)

```
1. User clicks "Connect Deezer"
   ↓
2. Generate: session_id, oauth_state (no PKCE!)
   ↓
3. Redirect to Deezer authorization URL
   (includes: state, scopes)
   ↓
4. User authorizes on Deezer
   ↓
5. Deezer redirects to callback with: code, state
   ↓
6. Verify state matches
   ↓
7. Exchange code for access_token (long-lived, no refresh_token)
   ↓
8. Store token in deezer_sessions
   ↓
9. Set session_id cookie
   ↓
10. Redirect to /
```

**Key Difference:** Deezer doesn't use PKCE or refresh tokens.

---

## Token Refresh

### Spotify (Automatic)

**TokenRefreshWorker** runs every 5 minutes:
- Checks all tokens expiring within 10 minutes
- Uses `refresh_token` to get new `access_token`
- Updates both user sessions and worker tokens
- Logs refresh status

**Implementation:**
```python
# TokenRefreshWorker._do_work()
refreshed = await token_manager.refresh_expiring_tokens(
    threshold_minutes=10
)
```

**Source:** `src/soulspot/application/services/workers/token_refresh_worker.py`

---

### Deezer (Manual Re-auth)

**No automatic refresh:**
- Deezer tokens are long-lived (~30 days)
- When token expires → User must re-authenticate
- UI shows "Token expired - please reconnect" message

**Check token validity:**
```python
# DeezerPlugin.get_auth_status()
try:
    await client.get_user_me(access_token)
    return AuthStatus(is_authenticated=True)
except DeezerUnauthorizedError:
    return AuthStatus(
        is_authenticated=False,
        error="Token expired - please re-authenticate"
    )
```

**Source:** `src/soulspot/infrastructure/plugins/deezer_plugin.py`

---

## Authentication Status API

**Endpoint:** `GET /api/auth/status`

**Response:**
```json
{
  "spotify": {
    "is_authenticated": true,
    "user_name": "john_doe",
    "expires_at": "2025-01-06T15:30:00Z",
    "needs_reauth": false
  },
  "deezer": {
    "is_authenticated": true,
    "user_name": "johndoe123",
    "expires_at": null,
    "needs_reauth": false
  }
}
```

**UI Usage:**
- Settings page checks auth status on load
- Shows "Connected" or "Disconnected" badge
- Displays username when authenticated
- Shows "Reconnect" button if token expired

**Source:** `src/soulspot/api/routers/auth.py` (lines 200-250)

---

## Troubleshooting

### "Invalid OAuth state" Error

**Cause:** CSRF protection detected mismatch between stored and returned state

**Solutions:**
1. Clear browser cookies and try again
2. Check redirect URI matches OAuth app configuration
3. Ensure session_id cookie is being set

### "Token expired" Error

**Cause:** Access token expired and refresh failed

**Solutions:**
1. **Spotify:** Wait 5 minutes for TokenRefreshWorker to run
2. **Deezer:** Click "Reconnect" button (no auto-refresh)
3. Check logs for refresh errors

### "No session found" Error

**Cause:** session_id cookie missing or invalid

**Solutions:**
1. Enable cookies in browser
2. Check if browser blocking third-party cookies
3. Clear site data and re-authenticate

---

## Related Documentation

- **[Auth Patterns](../04-architecture/auth-patterns.md)** - Technical OAuth implementation details
- **[Setup Guide](../01-guides/setup-guide.md)** - Initial configuration steps
- **[Spotify Auth Troubleshooting](../01-guides/spotify-auth-troubleshooting.md)** - Detailed OAuth debugging
- **[Worker Patterns](../04-architecture/worker-patterns.md)** - TokenRefreshWorker architecture

---

**Last Validated:** 2025-01-06 (against current source code)  
**Implementation Status:** ✅ Production-ready
