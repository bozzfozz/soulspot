# SoulSpot Authentication Patterns

> **PFLICHTLEKTÜRE** für alle, die OAuth oder Session-Management implementieren.

---

## 1. Authentication Übersicht

SoulSpot verwendet **OAuth 2.0** für externe Services:

| Service | OAuth Type | Token Refresh | Session Table |
|---------|------------|---------------|---------------|
| **Spotify** | OAuth 2.0 + PKCE | ✅ Ja (1h expiry) | `spotify_sessions` |
| **Deezer** | OAuth 2.0 (kein PKCE) | ❌ Nein (long-lived) | `deezer_sessions` |
| **Tidal** | OAuth 2.0 + PKCE | ✅ Ja | `tidal_sessions` (future) |

**Key Difference:**
- **Spotify**: Access Token läuft nach 1 Stunde ab → TokenRefreshWorker refreshed automatisch
- **Deezer**: Access Token ist long-lived (~30 Tage) → Kein automatischer Refresh

---

## 2. OAuth Flow - Spotify (mit PKCE)

```
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│ Browser │                    │ SoulSpot│                    │ Spotify │
└────┬────┘                    └────┬────┘                    └────┬────┘
     │                              │                              │
     │ 1. GET /api/auth/login       │                              │
     │ ─────────────────────────────>                              │
     │                              │                              │
     │              2. Generate:                                   │
     │              - session_id                                   │
     │              - oauth_state (CSRF)                           │
     │              - code_verifier (PKCE)                         │
     │                              │                              │
     │ 3. Set-Cookie + Redirect     │                              │
     │ <─────────────────────────────                              │
     │                              │                              │
     │ 4. GET /authorize?...&code_challenge=...                    │
     │ ────────────────────────────────────────────────────────────>
     │                              │                              │
     │              5. User grants access                          │
     │                              │                              │
     │ 6. Redirect to /callback?code=...&state=...                 │
     │ <────────────────────────────────────────────────────────────
     │                              │                              │
     │ 7. GET /api/auth/callback    │                              │
     │ ─────────────────────────────>                              │
     │                              │                              │
     │              8. Verify state (CSRF protection)              │
     │              9. POST /token (code + verifier)               │
     │              ───────────────────────────────────────────────>
     │                              │                              │
     │              10. {access_token, refresh_token, expires_in}  │
     │              <───────────────────────────────────────────────
     │                              │                              │
     │              11. Store tokens in:                           │
     │                  - SpotifySessionModel (user requests)      │
     │                  - DatabaseTokenManager (workers)           │
     │                              │                              │
     │ 12. Redirect to /           │                              │
     │ <─────────────────────────────                              │
```

---

## 3. Credential Storage

**KRITISCH: Credentials NIEMALS in .env!**

Alle OAuth Credentials werden in der `app_settings` Tabelle gespeichert:

```python
# Speichern (via Settings UI)
credentials_service = CredentialsService(session)
await credentials_service.save_spotify_credentials(
    client_id="...",
    client_secret="...",
    redirect_uri="http://localhost:8000/api/auth/callback",
)

# Laden (in Services)
credentials = await credentials_service.get_spotify_credentials()
# Returns: SpotifyCredentials(client_id, client_secret, redirect_uri)
```

**app_settings Keys:**

| Key | Beschreibung |
|-----|--------------|
| `spotify.client_id` | Spotify OAuth Client ID |
| `spotify.client_secret` | Spotify OAuth Client Secret |
| `spotify.redirect_uri` | OAuth Redirect URI |
| `deezer.app_id` | Deezer OAuth App ID |
| `deezer.secret` | Deezer OAuth Secret |
| `deezer.redirect_uri` | OAuth Redirect URI |

---

## 4. Session Models

### SpotifySessionModel

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
    created_at: Mapped[datetime]
    last_accessed_at: Mapped[datetime]
```

### DeezerSessionModel

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
    created_at: Mapped[datetime]
    last_accessed_at: Mapped[datetime]
```

---

## 5. Token Storage Architecture

### Dual Storage Pattern

SoulSpot speichert Tokens an **zwei Orten**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER REQUESTS (API Routes)                    │
│                                                                  │
│  Browser Cookie (session_id)                                     │
│         │                                                        │
│         ▼                                                        │
│  SpotifySessionModel / DeezerSessionModel                        │
│  - Access Token für User-initiierte Requests                     │
│  - Refresh Token für Token-Erneuerung                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    BACKGROUND WORKERS                            │
│                                                                  │
│  DatabaseTokenManager                                            │
│  - Single token für alle Background Workers                      │
│  - TokenRefreshWorker refreshed automatisch                      │
│  - spotify_tokens Tabelle (separate von sessions!)               │
└─────────────────────────────────────────────────────────────────┘
```

**Warum zwei Speicherorte?**
1. **User Sessions**: Können mehrere Browser haben, jeder mit eigenem Session Cookie
2. **Background Workers**: Brauchen genau einen Token, unabhängig von User Sessions

---

## 6. OAuth Implementation Pattern

### 6.1 Login Endpoint

```python
# src/soulspot/api/routers/auth.py

@router.get("/login")
async def login(
    request: Request,
    response: Response,
    session_store: DatabaseSessionStore = Depends(get_session_store),
    auth_service: SpotifyAuthService = Depends(get_spotify_auth_service),
) -> RedirectResponse:
    """Start OAuth flow - creates session and redirects to Spotify."""
    
    # 1. Generate PKCE verifier
    code_verifier = secrets.token_urlsafe(64)
    
    # 2. Generate state for CSRF protection
    oauth_state = secrets.token_urlsafe(32)
    
    # 3. Create session with OAuth params
    session = await session_store.create_session(
        oauth_state=oauth_state,
        code_verifier=code_verifier,
    )
    
    # 4. Get authorization URL
    auth_url = await auth_service.generate_auth_url(
        state=oauth_state,
        code_verifier=code_verifier,
    )
    
    # 5. Set session cookie
    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(
        key="session_id",
        value=session.session_id,
        httponly=True,
        secure=True,  # HTTPS only in production
        samesite="lax",
    )
    
    return response
```

### 6.2 Callback Endpoint

```python
@router.get("/callback")
async def callback(
    request: Request,
    code: str,
    state: str,
    session_store: DatabaseSessionStore = Depends(get_session_store),
    auth_service: SpotifyAuthService = Depends(get_spotify_auth_service),
    session_id: str | None = Cookie(None),
) -> RedirectResponse:
    """Handle OAuth callback - exchange code for tokens."""
    
    # 1. Get session from cookie
    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(401, "Session not found")
    
    # 2. Verify state (CSRF protection!)
    if session.oauth_state != state:
        raise HTTPException(400, "Invalid OAuth state")
    
    # 3. Exchange code for tokens
    token_result = await auth_service.exchange_code(
        code=code,
        code_verifier=session.code_verifier,
    )
    
    # 4. Store in user session
    await session_store.update_session(
        session_id=session.session_id,
        access_token=token_result.access_token,
        refresh_token=token_result.refresh_token,
        token_expires_at=token_result.expires_at,
        oauth_state=None,  # Clear
        code_verifier=None,  # Clear
    )
    
    # 5. ALSO store in DatabaseTokenManager for workers!
    if hasattr(request.app.state, "db_token_manager"):
        await request.app.state.db_token_manager.store_from_oauth(
            access_token=token_result.access_token,
            refresh_token=token_result.refresh_token,
            expires_in=token_result.expires_in,
        )
    
    return RedirectResponse(url="/", status_code=302)
```

---

## 7. Token Access Pattern

### 7.1 In API Routes (User Token)

```python
@router.get("/playlists")
async def get_playlists(
    request: Request,
    session_store: DatabaseSessionStore = Depends(get_session_store),
    session_id: str = Cookie(...),
) -> list[PlaylistDTO]:
    """Get user's playlists using their session token."""
    
    # Get user's session
    session = await session_store.get_session(session_id)
    if not session or not session.access_token:
        raise HTTPException(401, "Not authenticated")
    
    # Check token expiry (optional - should be refreshed by worker)
    if session.is_token_expired():
        raise HTTPException(401, "Token expired - please re-authenticate")
    
    # Use token for API call
    plugin = SpotifyPlugin(access_token=session.access_token, ...)
    return await plugin.get_user_playlists()
```

### 7.2 In Background Workers

```python
class WatchlistWorker:
    async def _do_work(self) -> None:
        """Check watchlists for new releases."""
        
        # 1. Check if token manager is available
        if self._token_manager is None:
            logger.warning("No token manager - skipping")
            return
        
        # 2. Get token (None if invalid/expired)
        token = await self._token_manager.get_token_for_background()
        if token is None:
            logger.debug("No valid token - skipping watchlist check")
            return
        
        # 3. Use token for work
        plugin = SpotifyPlugin(access_token=token, ...)
        artists = await plugin.get_followed_artists()
        # ... process artists
```

---

## 8. Token Refresh Pattern

### Spotify (automatic refresh)

```python
# TokenRefreshWorker runs every 5 minutes
class TokenRefreshWorker:
    async def _do_work(self) -> None:
        """Proactively refresh tokens before expiry."""
        
        # Refresh if expires within 10 minutes
        refreshed = await self.token_manager.refresh_expiring_tokens(
            threshold_minutes=10
        )
        
        if refreshed:
            logger.info("Token refreshed by background worker")
```

### Deezer (no refresh - re-auth needed)

```python
# Deezer tokens don't refresh - check expiry and warn user
class DeezerPlugin:
    async def get_auth_status(self) -> AuthStatus:
        """Check if Deezer auth is still valid."""
        
        if not self._access_token:
            return AuthStatus(is_authenticated=False, ...)
        
        # Verify token by calling API
        try:
            await self._client.get_user_me(self._access_token)
            return AuthStatus(is_authenticated=True, ...)
        except DeezerUnauthorizedError:
            # Token expired - user needs to re-auth
            return AuthStatus(
                is_authenticated=False,
                error="Token expired - please re-authenticate",
            )
```

---

## 9. Auth Status API

Endpoints für UI Auth-Status-Anzeige:

```python
@router.get("/status")
async def get_auth_status(
    request: Request,
    session_id: str | None = Cookie(None),
) -> AuthStatusResponse:
    """Get authentication status for all services."""
    
    return AuthStatusResponse(
        spotify=await _get_spotify_status(request, session_id),
        deezer=await _get_deezer_status(request, session_id),
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

---

## 10. Session Cleanup

```python
# Cleanup expired sessions (run periodically)
class SessionCleanupService:
    async def cleanup_expired_sessions(self) -> int:
        """Remove sessions that haven't been accessed in 24h."""
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        async with self._session_scope() as session:
            # Spotify sessions
            result = await session.execute(
                delete(SpotifySessionModel)
                .where(SpotifySessionModel.last_accessed_at < cutoff)
            )
            spotify_deleted = result.rowcount
            
            # Deezer sessions
            result = await session.execute(
                delete(DeezerSessionModel)
                .where(DeezerSessionModel.last_accessed_at < cutoff)
            )
            deezer_deleted = result.rowcount
            
            await session.commit()
        
        return spotify_deleted + deezer_deleted
```

---

## 11. Neuen Service hinzufügen (Checkliste)

Wenn du OAuth für einen neuen Service (z.B. Tidal) implementierst:

- [ ] **Model**: `{Service}SessionModel` in `models.py`
- [ ] **Migration**: `add_{service}_sessions_table.py`
- [ ] **Router**: `api/routers/{service}_auth.py` mit `/login`, `/callback`, `/status`
- [ ] **Client**: `infrastructure/integrations/{service}_client.py` mit OAuth Methoden
- [ ] **Plugin**: `infrastructure/plugins/{service}_plugin.py` mit `get_auth_url()`, `handle_callback()`
- [ ] **Settings**: `app_settings` Keys für Credentials
- [ ] **Dependencies**: `get_{service}_plugin()` in `dependencies.py`
- [ ] **Token Storage**: Entscheiden ob TokenManager nötig (wenn Refresh existiert)
- [ ] **UI**: Auth Button in Settings Page

---

## 12. Sicherheits-Regeln

### CSRF Protection
```python
# ✅ IMMER state Parameter prüfen
if session.oauth_state != state:
    raise HTTPException(400, "Invalid OAuth state")

# ❌ NIEMALS state ignorieren
token = await auth_service.exchange_code(code)  # Unsicher!
```

### Token Storage
```python
# ✅ Tokens in DB mit Encryption (falls möglich)
# ✅ httponly Cookies für Session IDs
# ✅ secure=True in Production

# ❌ NIEMALS Tokens in LocalStorage
# ❌ NIEMALS Tokens in Query Params loggen
# ❌ NIEMALS Tokens in Error Messages
```

### Session Management
```python
# ✅ Sessions mit Timeout
# ✅ Cleanup expired sessions
# ✅ Invalidate on logout

# ❌ NIEMALS Sessions ohne Expiry
# ❌ NIEMALS Session IDs erraten lassen (use secrets.token_urlsafe)
```

---

## 13. Zusammenfassung

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTH ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────┤
│  Credentials    │ app_settings table (NOT .env!)                │
│  User Sessions  │ {service}_sessions tables                     │
│  Worker Tokens  │ DatabaseTokenManager (spotify_tokens)         │
│  Session ID     │ httponly Cookie                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    OAUTH FLOW                                    │
├─────────────────────────────────────────────────────────────────┤
│  1. /login      │ Create session, generate state/verifier       │
│  2. /authorize  │ Redirect to provider                          │
│  3. /callback   │ Verify state, exchange code, store tokens     │
│  4. Use tokens  │ Sessions for users, TokenManager for workers  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    SERVICE DIFFERENCES                           │
├─────────────────────────────────────────────────────────────────┤
│  Spotify  │ PKCE, 1h token, auto-refresh via TokenRefreshWorker │
│  Deezer   │ Simple OAuth, long-lived token, no refresh          │
│  Tidal    │ PKCE, refresh_token, similar to Spotify (future)    │
└─────────────────────────────────────────────────────────────────┘
```
