# Authentication Feature

> **Version:** 2.0  
> **Last Updated:** 2025-01-06

---

## Overview

SoulSpot uses OAuth 2.0 for secure authentication with streaming services. Currently supported:

| Service | Auth Type | Status |
|---------|-----------|--------|
| **Spotify** | OAuth 2.0 PKCE | ✅ Full support |
| **Deezer** | OAuth 2.0 + Public API | ✅ Full support |

---

## Quick Start

### Connecting Spotify

1. **Open Settings** → Navigate to `/settings?tab=spotify`
2. **Click "Connect Spotify"** → Opens Spotify login page
3. **Authorize SoulSpot** → Grant requested permissions
4. **Done!** → You're redirected back to SoulSpot

### Connecting Deezer

1. **Open Settings** → Navigate to `/settings?tab=deezer`
2. **Click "Connect Deezer"** → Opens Deezer login page
3. **Authorize SoulSpot** → Grant requested permissions
4. **Done!** → You're redirected back to SoulSpot

**Note:** Deezer's public API (browse, search) works without authentication. OAuth is only needed for user-specific features (favorites, playlists).

---

## Session Management

### How Sessions Work

1. **Session Cookie** - A unique `session_id` stored in your browser (HttpOnly, secure)
2. **Database Storage** - Sessions are persisted in the database, surviving app restarts
3. **Token Refresh** - Background worker automatically refreshes tokens before expiry

### Session Persistence

Sessions survive across:
- ✅ Page refreshes
- ✅ Browser restarts
- ✅ App restarts (Docker container restarts)
- ✅ Multiple browser tabs (shared session)

Sessions expire when:
- ❌ User explicitly disconnects
- ❌ Refresh token revoked by service
- ❌ Session inactive for 30+ days

---

## Security Features

### PKCE (Proof Key for Code Exchange)

SoulSpot uses PKCE, the most secure OAuth flow:
- No client secret stored in browser
- One-time code verifier per authorization
- Prevents authorization code interception attacks

### CSRF Protection

- OAuth state parameter verified on callback
- Prevents cross-site request forgery

### Secure Cookies

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `HttpOnly` | true | Prevents JavaScript access |
| `SameSite` | Lax | Allows service redirects |
| `Secure` | true (production) | HTTPS only |
| `Path` | / | Available site-wide |

---

## Permission Scopes

### Spotify Scopes

| Scope | Purpose |
|-------|---------|
| `user-read-private` | Basic profile info |
| `user-read-email` | Email for user identification |
| `user-library-read` | Access Liked Songs |
| `user-follow-read` | Access Followed Artists |
| `playlist-read-private` | Access private playlists |
| `playlist-read-collaborative` | Access collaborative playlists |

### Deezer Scopes

| Scope | Purpose |
|-------|---------|
| `basic_access` | Basic profile info |
| `offline_access` | Long-lived refresh tokens |

---

## Troubleshooting

### "Not authenticated" Error

**Symptoms:** Features requiring authentication show "Not authenticated" error.

**Solutions:**
1. Check if session cookie exists (DevTools → Application → Cookies)
2. Re-connect your account (Settings → Disconnect → Connect)
3. Clear browser cookies and re-authenticate

### Token Refresh Failures

**Symptoms:** Authentication stops working after some time.

**Solutions:**
1. Check Token Refresh Worker status (bottom of sidebar)
2. If worker shows error, check logs: `/logs`
3. Re-connect account to get fresh tokens

### CSRF State Mismatch

**Symptoms:** Error "Session invalid or state mismatch" on callback.

**Causes:**
- Browser blocked cookies (privacy settings)
- Session expired during auth flow
- Direct link to callback URL (without starting auth flow)

**Solutions:**
1. Enable cookies for localhost:8765
2. Start fresh from Settings page
3. Don't bookmark or share callback URLs

---

## Multi-Browser Support

Each browser gets its own session:
- Safari on Mac → Session A
- Chrome on Mac → Session B
- Firefox on Phone → Session C

All sessions can be authenticated independently with the same or different accounts.

---

## Developer Information

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/authorize` | GET | Start OAuth flow |
| `/api/auth/callback` | GET | Handle OAuth callback |
| `/api/auth/spotify/status` | GET | Check auth status |
| `/api/auth/spotify/disconnect` | POST | Disconnect account |

See [Auth API Reference](../api/auth-api.md) for full details.

### Session Storage

Sessions are stored in `spotify_sessions` and `deezer_sessions` tables:

```sql
CREATE TABLE spotify_sessions (
    id UUID PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE,  -- Cookie value
    user_id VARCHAR(255),            -- Spotify user ID
    access_token TEXT,               -- Encrypted
    refresh_token TEXT,              -- Encrypted
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## Related Documentation

- [Auth API Reference](../api/auth-api.md)
- [Settings Feature](./settings.md)
- [Onboarding API](../api/onboarding-api.md)
- [Deezer Integration](./deezer-integration.md)
