# Authentication Patterns

**Category:** Architecture  
**Last Updated:** 2024-01-XX  
**Related Docs:** [Configuration](./configuration.md) | [Worker Patterns](./worker-patterns.md) | [Plugin System](./plugin-system.md)

---

## Overview

SoulSpot uses **OAuth 2.0** for authenticating with external music services. Authentication tokens are stored in the database (not environment variables) and managed separately for user sessions and background workers.

**Key Principles:**
- Database-first: All credentials and tokens stored in `app_settings` and session tables
- Dual storage: User tokens (session tables) + Worker tokens (DatabaseTokenManager)
- Service-specific: Each provider has unique OAuth flow and token lifecycle
- CSRF protection: State parameter validation for all OAuth callbacks

---

## Service Comparison

| Service | OAuth Type | Token Lifetime | Refresh | Session Table |
|---------|-----------|----------------|---------|---------------|
| **Spotify** | OAuth 2.0 + PKCE | 1 hour | ✅ Yes (automatic) | `spotify_sessions` |
| **Deezer** | OAuth 2.0 (simple) | ~30 days | ❌ No (long-lived) | `deezer_sessions` |
| **Tidal** | OAuth 2.0 + PKCE | TBD | ✅ Yes | `tidal_sessions` (future) |

**Critical Difference:**
- **Spotify**: Short-lived tokens require background refresh (TokenRefreshWorker)
- **Deezer**: Long-lived tokens, re-authentication required on expiry
- **Tidal**: Similar to Spotify (planned)

---

## OAuth Flow Architecture

### Spotify OAuth 2.0 (with PKCE)

```
┌──────────┐                     ┌──────────┐                     ┌──────────┐
│ Browser  │                     │ SoulSpot │                     │ Spotify  │
└────┬─────┘                     └────┬─────┘                     └────┬─────┘
     │                                │                                │
     │ 1. GET /api/auth/spotify/login │                                │
     │ ───────────────────────────────>                                │
     │                                │                                │
     │           2. Generate:                                          │
     │           - session_id (cookie)                                 │
     │           - oauth_state (CSRF protection)                       │
     │           - code_verifier (PKCE)                                │
     │           - code_challenge = SHA256(verifier)                   │
     │                                │                                │
     │ 3. Set-Cookie + Redirect       │                                │
     │ <───────────────────────────────                                │
     │                                │                                │
     │ 4. GET /authorize?code_challenge=...&state=...                  │
     │ ────────────────────────────────────────────────────────────────>
     │                                │                                │
     │               5. User grants access                             │
     │                                │                                │
     │ 6. Redirect to /callback?code=AUTH_CODE&state=STATE_VALUE      │
     │ <────────────────────────────────────────────────────────────────
     │                                │                                │
     │ 7. GET /api/auth/spotify/callback?code=...&state=...           │
     │ ───────────────────────────────>                                │
     │                                │                                │
     │           8. Verify state matches stored value                  │
     │           9. POST /api/token                                    │
     │              (code + code_verifier)                             │
     │              ───────────────────────────────────────────────────>
     │                                │                                │
     │           10. {access_token, refresh_token, expires_in: 3600}  │
     │              <───────────────────────────────────────────────────
     │                                │                                │
     │           11. Store in:                                         │
     │               - spotify_sessions (user token)                   │
     │               - spotify_tokens (worker token)                   │
     │                                │                                │
     │ 12. Redirect to /              │                                │
     │ <───────────────────────────────                                │
```

**Source References:**
- OAuth flow: `src/soulspot/api/routers/auth.py` (login/callback endpoints)
- PKCE generation: `src/soulspot/infrastructure/plugins/spotify_plugin.py`
- Token storage: `src/soulspot/infrastructure/persistence/models.py` (SpotifySessionModel)

---

## Credential Storage

**⚠️ CRITICAL: OAuth credentials NEVER go in `.env` files!**

All OAuth credentials stored in `app_settings` table:

```python
# Save credentials (via Settings UI)
from soulspot.application.services.credentials_service import CredentialsService

async with session_scope() as session:
    credentials_service = CredentialsService(session)
    await credentials_service.save_spotify_credentials(
        client_id="abc123...",
        client_secret="xyz789...",
        redirect_uri="http://localhost:8000/api/auth/spotify/callback",
    )

# Load credentials (in services/plugins)
credentials = await credentials_service.get_spotify_credentials()
# Returns: SpotifyCredentials(client_id, client_secret, redirect_uri)
```

**app_settings Keys:**

| Key | Value | Used By |
|-----|-------|---------|
| `spotify.client_id` | Spotify OAuth Client ID | SpotifyPlugin, auth router |
| `spotify.client_secret` | Spotify OAuth Client Secret | Token exchange |
| `spotify.redirect_uri` | OAuth callback URL | Authorization URL generation |
| `deezer.app_id` | Deezer OAuth App ID | DeezerPlugin, auth router |
| `deezer.secret` | Deezer OAuth Secret | Token exchange |
| `deezer.redirect_uri` | OAuth callback URL | Authorization URL generation |

**Source:** `src/soulspot/application/services/credentials_service.py`

---

## Session Models

### SpotifySessionModel

Stores OAuth tokens for **user-initiated requests** (per-browser session):

```python
# src/soulspot/infrastructure/persistence/models.py

class SpotifySessionModel(Base):
    __tablename__ = "spotify_sessions"
    
    # Primary key: session_id from browser cookie
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    
    # OAuth tokens (SENSITIVE!)
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # OAuth flow state (temporary, cleared after callback)
    oauth_state: Mapped[str | None] = mapped_column(String(64))
    code_verifier: Mapped[str | None] = mapped_column(String(128))  # PKCE
    
    # Session lifecycle
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

**Usage:**
- One session per browser (cookie-based)
- Supports multiple simultaneous users
- Tokens refreshed by TokenRefreshWorker before expiry

---

### DeezerSessionModel

Stores OAuth tokens for **Deezer user sessions**:

```python
class DeezerSessionModel(Base):
    __tablename__ = "deezer_sessions"
    
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    
    # OAuth token (no refresh_token - Deezer tokens are long-lived!)
    access_token: Mapped[str | None] = mapped_column(Text)
    
    # Deezer user info
    deezer_user_id: Mapped[str | None] = mapped_column(String(50))
    deezer_username: Mapped[str | None] = mapped_column(String(100))
    
    # OAuth flow state (temporary)
    oauth_state: Mapped[str | None] = mapped_column(String(64))
    # NO code_verifier - Deezer doesn't use PKCE!
    
    # Session lifecycle
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

**Key Difference:** Deezer doesn't use PKCE or refresh tokens.

---

## Dual Token Storage Architecture

SoulSpot stores tokens in **two separate locations** for different use cases:

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER REQUESTS (API Routes)                    │
│                                                                  │
│  Browser Cookie (session_id)                                     │
│         │                                                        │
│         ▼                                                        │
│  {Service}SessionModel (e.g., spotify_sessions)                  │
│  - Access Token for user-initiated requests                      │
│  - Refresh Token for token renewal                               │
│  - Per-browser session                                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    BACKGROUND WORKERS                            │
│                                                                  │
│  DatabaseTokenManager                                            │
│  - Single token for all background workers                       │
│  - TokenRefreshWorker refreshes automatically                    │
│  - spotify_tokens table (separate from sessions!)                │
│  - No user context                                               │
└─────────────────────────────────────────────────────────────────┘
```

**Why Two Storage Locations?**
1. **User Sessions**: Multiple users with multiple browsers, each with own token
2. **Background Workers**: Single shared token for automated tasks (playlists sync, new releases, etc.)

**Source:** `src/soulspot/infrastructure/integrations/database_token_manager.py`

---

## OAuth Implementation Patterns

### Login Endpoint (Start OAuth Flow)

```python
# src/soulspot/api/routers/auth.py

from secrets import token_urlsafe

@router.get("/spotify/login")
async def spotify_login(
    request: Request,
    response: Response,
    session_store: DatabaseSessionStore = Depends(get_session_store),
    spotify_plugin: SpotifyPlugin = Depends(get_spotify_plugin),
) -> RedirectResponse:
    """Start Spotify OAuth flow - creates session and redirects to Spotify."""
    
    # 1. Generate PKCE code_verifier (random 64-byte string)
    code_verifier = token_urlsafe(64)
    
    # 2. Generate oauth_state for CSRF protection (random 32-byte string)
    oauth_state = token_urlsafe(32)
    
    # 3. Create session with OAuth parameters
    session = await session_store.create_session(
        oauth_state=oauth_state,
        code_verifier=code_verifier,
    )
    
    # 4. Get Spotify authorization URL (with code_challenge from verifier)
    auth_url = await spotify_plugin.get_auth_url(
        state=oauth_state,
        code_verifier=code_verifier,
    )
    
    # 5. Set httponly cookie with session_id
    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key="session_id",
        value=session.session_id,
        httponly=True,  # JavaScript can't access
        secure=True,    # HTTPS only in production
        samesite="lax", # CSRF protection
    )
    
    return response
```

**PKCE Flow:**
1. Generate `code_verifier` (random string)
2. Calculate `code_challenge = BASE64URL(SHA256(code_verifier))`
3. Send `code_challenge` to Spotify in authorization URL
4. Store `code_verifier` in session (needed for token exchange)
5. Exchange code with `code_verifier` in callback

**Source:** `src/soulspot/api/routers/auth.py` (lines 52-95)

---

### Callback Endpoint (Exchange Code for Token)

```python
@router.get("/spotify/callback")
async def spotify_callback(
    request: Request,
    code: str,
    state: str,
    session_store: DatabaseSessionStore = Depends(get_session_store),
    spotify_plugin: SpotifyPlugin = Depends(get_spotify_plugin),
    session_id: str | None = Cookie(None),
) -> RedirectResponse:
    """Handle Spotify OAuth callback - exchange code for tokens."""
    
    # 1. Get session from cookie
    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(401, "Session not found - please log in again")
    
    # 2. Verify oauth_state matches (CSRF protection!)
    if session.oauth_state != state:
        raise HTTPException(400, "Invalid OAuth state - possible CSRF attack")
    
    # 3. Exchange authorization code for access_token + refresh_token
    token_result = await spotify_plugin.handle_callback(
        code=code,
        code_verifier=session.code_verifier,  # PKCE verification
    )
    
    # 4. Store tokens in USER session
    await session_store.update_session(
        session_id=session.session_id,
        access_token=token_result.access_token,
        refresh_token=token_result.refresh_token,
        token_expires_at=token_result.expires_at,
        oauth_state=None,       # Clear temporary state
        code_verifier=None,     # Clear temporary verifier
    )
    
    # 5. ALSO store in DatabaseTokenManager for WORKERS!
    if hasattr(request.app.state, "db_token_manager"):
        await request.app.state.db_token_manager.store_from_oauth(
            access_token=token_result.access_token,
            refresh_token=token_result.refresh_token,
            expires_in=token_result.expires_in,
        )
    
    return RedirectResponse(url="/", status_code=302)
```

**Security Checks:**
- ✅ Verify `oauth_state` matches stored value (prevents CSRF)
- ✅ Require `session_id` cookie (prevents unauthorized callbacks)
- ✅ Clear temporary OAuth parameters after use
- ✅ Use `code_verifier` for PKCE verification

**Source:** `src/soulspot/api/routers/auth.py` (lines 98-145)

---

## Token Access Patterns

### In API Routes (User Token)

```python
# src/soulspot/api/routers/playlists.py

@router.get("/playlists")
async def get_user_playlists(
    request: Request,
    session_store: DatabaseSessionStore = Depends(get_session_store),
    spotify_plugin: SpotifyPlugin = Depends(get_spotify_plugin),
    session_id: str = Cookie(...),  # Required
) -> list[PlaylistDTO]:
    """Get user's Spotify playlists using their session token."""
    
    # 1. Get user's session from cookie
    session = await session_store.get_session(session_id)
    if not session or not session.access_token:
        raise HTTPException(401, "Not authenticated - please log in")
    
    # 2. Check token expiry (optional - TokenRefreshWorker should handle)
    if session.is_token_expired():
        raise HTTPException(401, "Token expired - please re-authenticate")
    
    # 3. Use user's token for API call
    spotify_plugin.set_access_token(session.access_token)
    return await spotify_plugin.get_user_playlists()
```

**Pattern:** Each user request uses their own session token.

---

### In Background Workers (Shared Token)

```python
# src/soulspot/application/services/workers/watchlist_worker.py

class WatchlistWorker:
    def __init__(
        self,
        token_manager: DatabaseTokenManager | None = None,
        spotify_plugin: SpotifyPlugin = ...,
        ...
    ):
        self._token_manager = token_manager
        self._spotify_plugin = spotify_plugin
    
    async def _do_work(self) -> None:
        """Check watchlists for new releases using shared worker token."""
        
        # 1. Check if token manager available
        if self._token_manager is None:
            logger.warning("No token manager - skipping watchlist check")
            return
        
        # 2. Get shared worker token (None if invalid/expired)
        token = await self._token_manager.get_token_for_background()
        if token is None:
            logger.debug("No valid token - skipping watchlist check")
            return
        
        # 3. Use shared token for work
        self._spotify_plugin.set_access_token(token)
        artists = await self._spotify_plugin.get_followed_artists()
        # ... process artists for new releases
```

**Pattern:** All workers share single token from DatabaseTokenManager.

**Source:** `src/soulspot/application/services/workers/watchlist_worker.py`

---

## Token Refresh Patterns

### Spotify (Automatic Background Refresh)

```python
# src/soulspot/application/services/workers/token_refresh_worker.py

class TokenRefreshWorker:
    """Proactively refreshes Spotify tokens before expiry."""
    
    async def _do_work(self) -> None:
        """Check and refresh tokens expiring within 10 minutes."""
        
        # Refresh if expires_at < (now + 10 minutes)
        refreshed = await self._token_manager.refresh_expiring_tokens(
            threshold_minutes=10
        )
        
        if refreshed:
            logger.info("Spotify token refreshed by background worker")
```

**Strategy:**
- Worker runs every 5 minutes
- Refreshes tokens expiring within 10 minutes
- Uses refresh_token to get new access_token
- Updates both spotify_sessions AND spotify_tokens tables

**Source:** `src/soulspot/application/services/workers/token_refresh_worker.py`

---

### Deezer (No Refresh - Re-auth Required)

```python
# src/soulspot/infrastructure/plugins/deezer_plugin.py

class DeezerPlugin:
    async def get_auth_status(self) -> AuthStatus:
        """Check if Deezer token is still valid."""
        
        if not self._access_token:
            return AuthStatus(is_authenticated=False)
        
        # Verify token by calling API
        try:
            await self._client.get_user_me(self._access_token)
            return AuthStatus(is_authenticated=True)
        except DeezerUnauthorizedError:
            # Token expired - user MUST re-authenticate
            return AuthStatus(
                is_authenticated=False,
                error="Token expired - please re-authenticate via Settings",
            )
```

**Strategy:**
- Deezer tokens are long-lived (~30 days)
- No automatic refresh available
- User must re-authenticate when token expires

**Source:** `src/soulspot/infrastructure/plugins/deezer_plugin.py`

---

## Authentication Status API

Endpoints for UI authentication status display:

```python
# src/soulspot/api/routers/auth.py

@router.get("/status")
async def get_auth_status(
    request: Request,
    session_id: str | None = Cookie(None),
    spotify_plugin: SpotifyPlugin = Depends(get_spotify_plugin),
    deezer_plugin: DeezerPlugin = Depends(get_deezer_plugin),
) -> AuthStatusResponse:
    """Get authentication status for all services."""
    
    return AuthStatusResponse(
        spotify=await _get_spotify_status(spotify_plugin, session_id),
        deezer=await _get_deezer_status(deezer_plugin, session_id),
    )

@dataclass
class AuthStatusResponse:
    spotify: ServiceAuthStatus
    deezer: ServiceAuthStatus

@dataclass
class ServiceAuthStatus:
    is_authenticated: bool
    user_name: str | None = None
    expires_at: datetime | None = None
    needs_reauth: bool = False
```

**UI Usage:**
```javascript
// Check auth status on settings page load
const status = await fetch('/api/auth/status');
if (!status.spotify.is_authenticated) {
    showSpotifyLoginButton();
}
```

**Source:** `src/soulspot/api/routers/auth.py` (lines 200-250)

---

## Session Cleanup

```python
# src/soulspot/application/services/session_cleanup_service.py

class SessionCleanupService:
    async def cleanup_expired_sessions(self) -> int:
        """Remove sessions not accessed in 24 hours.
        
        Returns:
            Number of sessions deleted
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        async with self._session_scope() as session:
            # Cleanup Spotify sessions
            result = await session.execute(
                delete(SpotifySessionModel)
                .where(SpotifySessionModel.last_accessed_at < cutoff)
            )
            spotify_deleted = result.rowcount
            
            # Cleanup Deezer sessions
            result = await session.execute(
                delete(DeezerSessionModel)
                .where(DeezerSessionModel.last_accessed_at < cutoff)
            )
            deezer_deleted = result.rowcount
            
            await session.commit()
        
        logger.info(f"Cleaned up {spotify_deleted + deezer_deleted} expired sessions")
        return spotify_deleted + deezer_deleted
```

**Scheduled:** Run via background worker every 6 hours.

---

## Adding New OAuth Service

**Checklist for implementing OAuth for new service (e.g., Tidal):**

- [ ] **Model**: Create `{Service}SessionModel` in `src/soulspot/infrastructure/persistence/models.py`
  - session_id, access_token, refresh_token (if applicable), oauth_state, code_verifier (if PKCE)
- [ ] **Migration**: Create Alembic migration `add_{service}_sessions_table.py`
- [ ] **Router**: Create `src/soulspot/api/routers/{service}_auth.py` with:
  - `GET /{service}/login` - Start OAuth flow
  - `GET /{service}/callback` - Handle callback
  - `GET /{service}/status` - Auth status
- [ ] **Client**: Create `src/soulspot/infrastructure/integrations/{service}_client.py` with OAuth methods
- [ ] **Plugin**: Implement `src/soulspot/infrastructure/plugins/{service}_plugin.py` with:
  - `get_auth_url()` - Generate authorization URL
  - `handle_callback()` - Exchange code for token
  - `get_auth_status()` - Check authentication
- [ ] **Settings**: Add credential keys to `app_settings`:
  - `{service}.client_id`, `{service}.client_secret`, `{service}.redirect_uri`
- [ ] **Dependencies**: Add `get_{service}_plugin()` to `src/soulspot/api/dependencies.py`
- [ ] **Token Storage**: Decide if DatabaseTokenManager needed (if refresh tokens exist)
- [ ] **UI**: Add authentication button in Settings page

---

## Security Best Practices

### CSRF Protection

```python
# ✅ ALWAYS verify oauth_state parameter
if session.oauth_state != state:
    raise HTTPException(400, "Invalid OAuth state - possible CSRF attack")

# ❌ NEVER skip state verification
token = await plugin.handle_callback(code)  # Vulnerable to CSRF!
```

**Why:** The `state` parameter prevents attackers from tricking users into authorizing their own accounts.

---

### Token Storage

```python
# ✅ Store tokens in database with encryption (if possible)
# ✅ Use httponly cookies for session IDs
# ✅ Set secure=True in production (HTTPS only)

response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,  # JavaScript can't access
    secure=True,    # HTTPS only
    samesite="lax", # CSRF protection
)

# ❌ NEVER store tokens in LocalStorage (vulnerable to XSS)
# ❌ NEVER log tokens in error messages
# ❌ NEVER include tokens in query parameters (logged in server logs)
```

---

### Session Management

```python
# ✅ Sessions must have expiry (cleanup expired sessions)
# ✅ Use secrets.token_urlsafe() for session IDs (unpredictable)
# ✅ Invalidate sessions on logout

# ❌ NEVER use sequential/guessable session IDs
# ❌ NEVER create sessions without timeout
```

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTH ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────┤
│  Credentials    │ app_settings table (NOT .env!)                │
│  User Sessions  │ {service}_sessions tables (per-browser)       │
│  Worker Tokens  │ DatabaseTokenManager (shared token)           │
│  Session ID     │ httponly Cookie (secure, samesite=lax)        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    OAUTH FLOW                                    │
├─────────────────────────────────────────────────────────────────┤
│  1. /login      │ Create session, generate state/verifier       │
│  2. /authorize  │ Redirect to provider (Spotify/Deezer)         │
│  3. /callback   │ Verify state, exchange code, store tokens     │
│  4. Use tokens  │ Sessions for users, TokenManager for workers  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    SERVICE DIFFERENCES                           │
├─────────────────────────────────────────────────────────────────┤
│  Spotify  │ PKCE, 1h token, auto-refresh via TokenRefreshWorker │
│  Deezer   │ Simple OAuth, ~30d token, manual re-auth           │
│  Tidal    │ PKCE, refresh_token, similar to Spotify (future)   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- **[Configuration](./configuration.md)** - Database-first config architecture
- **[Worker Patterns](./worker-patterns.md)** - TokenRefreshWorker, background tasks
- **[Plugin System](./plugin-system.md)** - IMusicServicePlugin interface
- **[Error Handling](./error-handling.md)** - AuthenticationError, AuthorizationError

---

**Last Validated:** 2024-01-XX (against current source code)  
**Validation:** All code examples verified against actual implementation
