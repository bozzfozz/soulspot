# Authentication & Settings Architecture

**Document Status**: Architecture Specification  
**Last Updated**: 2025-11-22  
**Target Audience**: Developers implementing authentication and settings persistence

---

## Overview

This document specifies the authentication architecture and settings persistence strategy for Version 3.0, designed for **single-user local deployment** without multi-user authentication.

**Key Principles:**
- ✅ No user authentication (single-user, local-only)
- ✅ Service authentication (Spotify OAuth, API keys)
- ✅ Settings persistence via Database Module
- ✅ Encrypted credential storage
- ✅ Token extraction and management

---

## 1. Authentication Architecture

### 1.1 No User Authentication

**System Design:**

```
┌─────────────────────────────────────────────┐
│         Local Machine (Host)                │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │   Browser                             │ │
│  │   http://localhost:8765               │ │
│  │   ✅ Direct access, no login         │ │
│  └───────────────────────────────────────┘ │
│              ↓ (no auth required)           │
│  ┌───────────────────────────────────────┐ │
│  │   SoulSpot FastAPI             │ │
│  │   ❌ No authentication middleware    │ │
│  │   ❌ No session management           │ │
│  │   ❌ No login/logout endpoints       │ │
│  └───────────────────────────────────────┘ │
│              ↓                              │
│  ┌───────────────────────────────────────┐ │
│  │   Database Module                     │ │
│  │   ✅ Service credentials (encrypted) │ │
│  │   ✅ User settings                   │ │
│  │   ✅ OAuth tokens (encrypted)        │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

**What This Means:**

- ✅ **No user entity** in database
- ✅ **No password hashing** (no user passwords)
- ✅ **No session tokens** (no need to track sessions)
- ✅ **No JWT/OAuth for UI** (UI is localhost-only)
- ✅ **No RBAC** (single user = all permissions)

### 1.2 Service Authentication

**We DO authenticate with external services:**

1. **Spotify OAuth 2.0**
2. **MusicBrainz API** (optional)
3. **Last.fm API** (optional)
4. **slskd API** (API key or username/password)

**Architecture:**

```python
# Each service module manages its own authentication
# via Database Module for credential storage

┌─────────────────────────────────────────────────────┐
│ Spotify Module (OAuth 2.0)                         │
│                                                     │
│  1. User clicks "Connect Spotify" in onboarding    │
│  2. Browser redirects to Spotify auth page         │
│  3. User grants permissions                        │
│  4. Spotify redirects back with auth code          │
│  5. Module exchanges code for tokens               │
│  6. Tokens stored encrypted via Database Module    │
│  7. Access token refreshed automatically           │
└─────────────────────────────────────────────────────┘
         ↓ (tokens)
┌─────────────────────────────────────────────────────┐
│ Database Module                                     │
│                                                     │
│  spotify_credentials:                               │
│    - client_id (encrypted)                          │
│    - client_secret (encrypted)                      │
│                                                     │
│  spotify_tokens:                                    │
│    - access_token (encrypted)                       │
│    - refresh_token (encrypted)                      │
│    - expires_at                                     │
│    - scope                                          │
└─────────────────────────────────────────────────────┘
```

---

## 2. Spotify Token Extraction & Management

### 2.1 OAuth 2.0 Flow (Authorization Code + PKCE)

**Complete Flow:**

```
┌──────────┐                                    ┌──────────────┐
│ Browser  │                                    │   Spotify    │
│          │                                    │   Auth API   │
└──────────┘                                    └──────────────┘
     │                                                   │
     │ 1. User clicks "Connect Spotify"                 │
     ├──────────────────────────────────────────────────┤
     │                                                   │
     │ 2. GET /spotify/auth/start                       │
     │    Generate PKCE code_verifier                   │
     │    Generate state parameter (CSRF protection)    │
     │    Redirect to Spotify auth URL                  │
     │    ──────────────────────────────────────────►   │
     │                                                   │
     │ 3. User grants permissions on Spotify            │
     │    ◄─────────────────────────────────────────    │
     │                                                   │
     │ 4. Redirect back with auth code                  │
     │    http://localhost:8765/spotify/auth/callback   │
     │    ?code=AUTH_CODE&state=STATE                   │
     │                                                   │
     │ 5. POST /spotify/auth/callback                   │
     │    Validate state parameter                      │
     │    Exchange auth code for tokens                 │
     │    ──────────────────────────────────────────►   │
     │                                                   │
     │ 6. Receive tokens                                │
     │    {                                             │
     │      access_token: "...",                        │
     │      refresh_token: "...",                       │
     │      expires_in: 3600,                           │
     │      scope: "..."                                │
     │    }                                             │
     │    ◄─────────────────────────────────────────    │
     │                                                   │
     │ 7. Store tokens encrypted via Database Module    │
     │                                                   │
     │ 8. Redirect to dashboard                         │
     │    ✅ Spotify connected                         │
     │                                                   │
```

### 2.2 Implementation: Auth Submodule

**Module Structure:**

```
modules/spotify/submodules/auth/
├── README.md
├── CHANGELOG.md
├── docs/
│   ├── oauth-flow.md
│   └── token-management.md
├── backend/
│   ├── api/
│   │   ├── routes.py              # OAuth endpoints
│   │   └── schemas.py             # Request/response models
│   ├── application/
│   │   ├── services/
│   │   │   ├── oauth_service.py   # OAuth flow orchestration
│   │   │   └── token_service.py   # Token refresh, validation
│   │   └── dto/
│   │       └── token_dto.py       # Token data transfer objects
│   ├── domain/
│   │   ├── entities/
│   │   │   └── oauth_token.py     # Token entity with expiry logic
│   │   └── ports/
│   │       └── token_storage.py   # Interface for token storage
│   └── infrastructure/
│       ├── spotify_oauth_client.py # HTTP client for OAuth
│       └── token_repository.py     # Database Module adapter
└── tests/
    ├── unit/
    │   ├── test_oauth_service.py
    │   └── test_token_service.py
    └── integration/
        └── test_oauth_flow.py
```

### 2.3 Code Example: OAuth Service

```python
# modules/spotify/submodules/auth/backend/application/services/oauth_service.py

"""
Spotify OAuth 2.0 Service

Handles complete OAuth flow with PKCE for secure token extraction.

**OAuth Flow:**
1. Generate PKCE code_verifier and code_challenge
2. Generate state parameter for CSRF protection
3. Redirect user to Spotify authorization URL
4. User grants permissions on Spotify
5. Spotify redirects back with authorization code
6. Exchange code for access_token + refresh_token
7. Store tokens encrypted via Database Module
8. Set up automatic token refresh

**Security:**
- PKCE (Proof Key for Code Exchange) prevents auth code interception
- State parameter prevents CSRF attacks
- Tokens stored encrypted via Database Module (Fernet)
- Client secret never sent to browser
- Tokens never logged or exposed in errors

**Token Refresh:**
- Access tokens expire after 1 hour
- Refresh tokens are long-lived (no expiry)
- Auto-refresh 5 minutes before expiry
- Background task checks every minute
- Failed refresh triggers re-authentication

**Related Docs:**
- OAuth 2.0 spec: https://oauth.net/2/
- Spotify docs: https://developer.spotify.com/documentation/web-api/tutorials/code-flow
- PKCE spec: https://oauth.net/2/pkce/
"""

import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx

from core.database import DatabaseService
from core.events import EventBus
from core.errors import ConfigurationError, AuthenticationError

# OAuth constants
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
REDIRECT_URI = "http://localhost:8765/spotify/auth/callback"

# PKCE parameters
CODE_VERIFIER_LENGTH = 128  # 43-128 chars (spec requirement)
CODE_CHALLENGE_METHOD = "S256"  # SHA-256 hash

# Token refresh timing
TOKEN_REFRESH_BUFFER = 300  # Refresh 5 minutes before expiry (avoid race conditions)

# Scopes required for SoulSpot features
SPOTIFY_SCOPES = [
    "user-read-private",          # Read user profile
    "user-read-email",            # Read user email
    "playlist-read-private",      # Read private playlists
    "playlist-read-collaborative",# Read collaborative playlists
    "user-library-read",          # Read saved tracks
]


class OAuthService:
    """
    Spotify OAuth 2.0 service.
    
    Hey future me – This service handles the complete OAuth flow.
    Key security: PKCE prevents auth code interception, state prevents CSRF.
    Tokens are stored encrypted via Database Module, never in memory long-term.
    
    The flow is complex but well-tested. Don't change security parameters
    (PKCE, state) without reviewing OAuth 2.0 best practices.
    
    Args:
        db_service: Database Module for credential/token storage
        event_bus: Event Bus for publishing auth events
        http_client: HTTP client for OAuth API calls
    """
    
    def __init__(
        self,
        db_service: DatabaseService,
        event_bus: EventBus,
        http_client: httpx.AsyncClient | None = None
    ):
        self.db = db_service
        self.events = event_bus
        self.http = http_client or httpx.AsyncClient(timeout=10.0)
        
    async def start_authorization(self) -> str:
        """
        Start OAuth authorization flow.
        
        Generates PKCE parameters and state, stores for validation,
        returns authorization URL for browser redirect.
        
        Returns:
            Spotify authorization URL (redirect user here)
            
        Raises:
            ConfigurationError: If Spotify client credentials not set
            
        Examples:
            >>> auth_url = await oauth_service.start_authorization()
            >>> # Redirect user to auth_url
            >>> return RedirectResponse(auth_url)
        """
        # Get client ID from Database Module
        credentials = await self.db.get("config", "spotify_credentials")
        
        if not credentials or not credentials.get("client_id"):
            raise ConfigurationError(
                code="SPOTIFY_CLIENT_ID_MISSING",
                message="Spotify Client ID not configured",
                resolution=(
                    "1. Go to Settings → Spotify\n"
                    "2. Enter Client ID from Spotify Developer Dashboard\n"
                    "3. Get Client ID: https://developer.spotify.com/dashboard\n"
                    "4. Save configuration"
                ),
                context={},
                docs_url="https://docs.soulspot.app/setup/spotify#client-id"
            )
        
        # Generate PKCE code_verifier (random 128 chars)
        code_verifier = self._generate_code_verifier()
        
        # Generate code_challenge from code_verifier (SHA256)
        code_challenge = self._generate_code_challenge(code_verifier)
        
        # Generate state for CSRF protection (random 32 chars)
        state = secrets.token_urlsafe(32)
        
        # Store PKCE params and state for validation in callback
        # Hey future me – We store these temporarily (5 min TTL) because
        # we need to validate them when Spotify redirects back.
        # Don't extend TTL too much (security risk if state leaks).
        await self.db.save(
            entity_type="oauth_session",
            entity_data={
                "id": state,  # Use state as ID for easy lookup
                "code_verifier": code_verifier,
                "state": state,
                "created_at": datetime.utcnow().isoformat(),
                "ttl": 300  # 5 minutes (enough for user to authorize)
            }
        )
        
        # Build authorization URL
        params = {
            "client_id": credentials["client_id"],
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "scope": " ".join(SPOTIFY_SCOPES),
            "code_challenge": code_challenge,
            "code_challenge_method": CODE_CHALLENGE_METHOD,
        }
        
        auth_url = f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"
        
        # Publish event
        await self.events.publish(
            "spotify.auth.started",
            {"redirect_uri": REDIRECT_URI}
        )
        
        return auth_url
    
    async def handle_callback(
        self,
        code: str,
        state: str
    ) -> dict:
        """
        Handle OAuth callback and exchange code for tokens.
        
        Validates state parameter (CSRF protection), exchanges authorization
        code for access/refresh tokens, stores tokens encrypted.
        
        Args:
            code: Authorization code from Spotify
            state: State parameter for CSRF validation
            
        Returns:
            Token data dict (for immediate use, also stored in DB)
            
        Raises:
            AuthenticationError: If state invalid or token exchange fails
            
        Examples:
            >>> # In FastAPI route
            >>> @router.get("/spotify/auth/callback")
            >>> async def callback(code: str, state: str):
            >>>     tokens = await oauth_service.handle_callback(code, state)
            >>>     return {"status": "connected"}
        """
        # Validate state parameter (CSRF protection)
        # Hey future me – This is CRITICAL. If state doesn't match,
        # someone might be trying CSRF attack. Reject immediately.
        session = await self.db.get("oauth_session", state)
        
        if not session:
            raise AuthenticationError(
                code="SPOTIFY_INVALID_STATE",
                message="Invalid or expired OAuth state parameter",
                resolution=(
                    "This may indicate a security issue (CSRF attack attempt).\n"
                    "Start the authorization flow again:\n"
                    "1. Go to Settings → Spotify\n"
                    "2. Click 'Connect Spotify'\n"
                    "3. Complete authorization within 5 minutes"
                ),
                context={"state": state},
                docs_url="https://docs.soulspot.app/troubleshooting/oauth-errors"
            )
        
        if session["state"] != state:
            raise AuthenticationError(
                code="SPOTIFY_STATE_MISMATCH",
                message="OAuth state parameter mismatch",
                resolution="Start authorization flow again from Settings",
                context={"expected": session["state"], "received": state},
                docs_url="https://docs.soulspot.app/troubleshooting/oauth-errors"
            )
        
        # Get credentials from Database Module
        credentials = await self.db.get("config", "spotify_credentials")
        
        if not credentials:
            raise ConfigurationError(
                code="SPOTIFY_CREDENTIALS_MISSING",
                message="Spotify credentials not configured",
                resolution="Configure Spotify credentials in Settings",
                context={},
                docs_url="https://docs.soulspot.app/setup/spotify"
            )
        
        # Exchange authorization code for tokens
        # Hey future me – We use code_verifier from session (PKCE).
        # This proves we're the same client that started the flow.
        # Don't skip code_verifier or PKCE is useless.
        try:
            response = await self.http.post(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                    "code_verifier": session["code_verifier"],  # PKCE proof
                }
            )
            
            response.raise_for_status()
            token_data = response.json()
            
        except httpx.HTTPStatusError as e:
            raise AuthenticationError(
                code=f"SPOTIFY_TOKEN_EXCHANGE_FAILED_{e.response.status_code}",
                message="Failed to exchange authorization code for tokens",
                resolution=(
                    "1. Verify Spotify credentials in Settings\n"
                    "2. Check Client ID and Client Secret are correct\n"
                    "3. Start authorization flow again\n"
                    "4. Contact support if issue persists"
                ),
                context={
                    "status_code": e.response.status_code,
                    "error": e.response.json().get("error", "unknown")
                },
                docs_url="https://docs.soulspot.app/troubleshooting/oauth-errors"
            )
        
        # Calculate token expiration
        expires_in = token_data["expires_in"]  # Seconds (usually 3600 = 1 hour)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Store tokens encrypted via Database Module
        # Hey future me – Database Module handles encryption automatically.
        # We mark access_token and refresh_token as sensitive.
        tokens = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_at": expires_at.isoformat(),
            "scope": token_data["scope"],
            "token_type": token_data["token_type"],
        }
        
        await self.db.save(
            entity_type="spotify_tokens",
            entity_data=tokens,
            sensitive_keys=["access_token", "refresh_token"]
        )
        
        # Clean up OAuth session (no longer needed)
        await self.db.delete("oauth_session", state)
        
        # Publish event
        await self.events.publish(
            "spotify.auth.completed",
            {
                "expires_at": expires_at.isoformat(),
                "scopes": token_data["scope"].split()
            }
        )
        
        return tokens
    
    async def refresh_token(self) -> dict:
        """
        Refresh access token using refresh token.
        
        Called automatically when access token expires or is about to expire.
        Updates stored tokens via Database Module.
        
        Returns:
            New token data with fresh access_token
            
        Raises:
            AuthenticationError: If refresh fails (user needs to re-authorize)
            
        Examples:
            >>> # Automatic refresh in background task
            >>> if token_expires_soon():
            >>>     await oauth_service.refresh_token()
        """
        # Get current tokens
        current_tokens = await self.db.get("config", "spotify_tokens")
        
        if not current_tokens or not current_tokens.get("refresh_token"):
            raise AuthenticationError(
                code="SPOTIFY_NO_REFRESH_TOKEN",
                message="No refresh token available",
                resolution=(
                    "Re-authorize with Spotify:\n"
                    "1. Go to Settings → Spotify\n"
                    "2. Click 'Reconnect Spotify'\n"
                    "3. Complete authorization"
                ),
                context={},
                docs_url="https://docs.soulspot.app/setup/spotify#reauthorize"
            )
        
        # Get credentials
        credentials = await self.db.get("config", "spotify_credentials")
        
        if not credentials:
            raise ConfigurationError(
                code="SPOTIFY_CREDENTIALS_MISSING",
                message="Spotify credentials not configured",
                resolution="Configure Spotify credentials in Settings",
                context={},
                docs_url="https://docs.soulspot.app/setup/spotify"
            )
        
        # Refresh token
        try:
            response = await self.http.post(
                SPOTIFY_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": current_tokens["refresh_token"],
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                }
            )
            
            response.raise_for_status()
            token_data = response.json()
            
        except httpx.HTTPStatusError as e:
            raise AuthenticationError(
                code=f"SPOTIFY_REFRESH_FAILED_{e.response.status_code}",
                message="Failed to refresh access token",
                resolution=(
                    "Re-authorize with Spotify:\n"
                    "1. Go to Settings → Spotify\n"
                    "2. Click 'Reconnect Spotify'\n"
                    "3. Complete authorization"
                ),
                context={
                    "status_code": e.response.status_code,
                    "error": e.response.json().get("error", "unknown")
                },
                docs_url="https://docs.soulspot.app/troubleshooting/oauth-errors"
            )
        
        # Calculate new expiration
        expires_in = token_data["expires_in"]
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Update tokens (refresh_token might be new or same)
        # Hey future me – Spotify sometimes returns new refresh_token,
        # sometimes reuses old one. Always use what they send back.
        new_tokens = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token", current_tokens["refresh_token"]),
            "expires_at": expires_at.isoformat(),
            "scope": token_data.get("scope", current_tokens["scope"]),
            "token_type": token_data["token_type"],
        }
        
        await self.db.update(
            entity_type="spotify_tokens",
            entity_id="current",  # Single user = single token set
            updates=new_tokens,
            sensitive_keys=["access_token", "refresh_token"]
        )
        
        # Publish event
        await self.events.publish(
            "spotify.token.refreshed",
            {"expires_at": expires_at.isoformat()}
        )
        
        return new_tokens
    
    def _generate_code_verifier(self) -> str:
        """
        Generate PKCE code_verifier (random 128-char string).
        
        Hey future me – This is cryptographically random. Don't use
        non-random generators or PKCE security is compromised.
        
        Returns:
            URL-safe base64 string (128 chars)
        """
        # Generate 96 random bytes → base64 → 128 chars
        random_bytes = secrets.token_bytes(96)
        code_verifier = base64.urlsafe_b64encode(random_bytes).decode('utf-8')
        
        # Remove padding (=) to get exactly 128 chars
        return code_verifier.rstrip('=')[:CODE_VERIFIER_LENGTH]
    
    def _generate_code_challenge(self, code_verifier: str) -> str:
        """
        Generate PKCE code_challenge from code_verifier (SHA256 hash).
        
        Hey future me – code_challenge = BASE64URL(SHA256(code_verifier))
        This is sent to Spotify in authorization URL. Later, we send
        code_verifier in token exchange. Spotify verifies they match.
        This proves we're the same client (prevents code interception).
        
        Args:
            code_verifier: Random 128-char string
            
        Returns:
            URL-safe base64 SHA256 hash
        """
        # SHA256 hash of code_verifier
        sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        
        # Base64 URL-safe encode
        code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8')
        
        # Remove padding
        return code_challenge.rstrip('=')
```

### 2.4 Background Token Refresh

```python
# modules/spotify/backend/application/tasks/token_refresh_task.py

"""
Background task for automatic token refresh.

Runs every minute, checks if access token expires soon (within 5 minutes),
refreshes automatically if needed.

This ensures uninterrupted Spotify API access without user intervention.
"""

import asyncio
from datetime import datetime, timedelta

from core.database import DatabaseService
from modules.spotify.submodules.auth.backend.application.services.oauth_service import (
    OAuthService,
    TOKEN_REFRESH_BUFFER
)


async def token_refresh_task(
    db_service: DatabaseService,
    oauth_service: OAuthService
):
    """
    Background task that refreshes Spotify token before expiry.
    
    Hey future me – This runs every minute and checks token expiry.
    We refresh 5 minutes before expiry to avoid race conditions
    (if user makes API call right when token expires).
    
    Args:
        db_service: Database Module
        oauth_service: OAuth service for refresh
    """
    while True:
        try:
            # Get current tokens
            tokens = await db_service.get("spotify_tokens", "current")
            
            if tokens and tokens.get("expires_at"):
                expires_at = datetime.fromisoformat(tokens["expires_at"])
                now = datetime.utcnow()
                
                # Refresh if expires within buffer time (5 minutes)
                time_until_expiry = (expires_at - now).total_seconds()
                
                if time_until_expiry <= TOKEN_REFRESH_BUFFER:
                    print(f"[Token Refresh] Token expires in {time_until_expiry:.0f}s, refreshing...")
                    await oauth_service.refresh_token()
                    print("[Token Refresh] Token refreshed successfully")
                else:
                    print(f"[Token Refresh] Token valid for {time_until_expiry:.0f}s")
            
        except Exception as e:
            # Don't crash background task on errors
            print(f"[Token Refresh] Error: {e}")
        
        # Sleep 60 seconds
        await asyncio.sleep(60)
```

---

## 3. Settings Persistence Strategy

### 3.1 Settings Architecture

**Storage via Database Module:**

```
All settings stored in Database Module with structured schema:

┌─────────────────────────────────────────────────────┐
│ Database Module                                     │
│                                                     │
│ Entity Type: "settings"                             │
│                                                     │
│ Global Settings:                                    │
│  {                                                  │
│    id: "global",                                    │
│    port: 8765,                                      │
│    log_level: "INFO",                               │
│    music_directory: "/music",                       │
│    download_directory: "/downloads",                │
│    theme: "dark",                                   │
│    language: "en"                                   │
│  }                                                  │
│                                                     │
│ Module Settings:                                    │
│  {                                                  │
│    id: "spotify",                                   │
│    enabled: true,                                   │
│    market: "US",                                    │
│    search_limit: 20,                                │
│    cache_ttl: 300                                   │
│  }                                                  │
│                                                     │
│  {                                                  │
│    id: "soulseek",                                  │
│    enabled: true,                                   │
│    search_timeout: 30,                              │
│    max_downloads: 3,                                │
│    quality_filter: "320kbps+"                       │
│  }                                                  │
│                                                     │
│ Service Credentials (encrypted):                    │
│  {                                                  │
│    id: "spotify_credentials",                       │
│    client_id: "...",     # Encrypted                │
│    client_secret: "..." # Encrypted                │
│  }                                                  │
│                                                     │
│  {                                                  │
│    id: "slskd_credentials",                         │
│    url: "http://localhost:5030",                    │
│    api_key: "...",       # Encrypted (optional)     │
│    username: "...",      # Encrypted (if no API key)│
│    password: "..."       # Encrypted (if no API key)│
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

### 3.2 Settings Service

```python
# core/settings/settings_service.py

"""
Settings Persistence Service

Manages all application and module settings via Database Module.

**Architecture:**
- Global settings (app-wide)
- Module settings (per module)
- Service credentials (encrypted)
- User preferences (UI state, etc.)

**Features:**
- Validation on save
- Defaults for missing settings
- Change events published
- Encrypted credential storage
- Type-safe access

**Storage:**
All settings stored in Database Module entity_type="settings".
Credentials stored with sensitive_keys for automatic encryption.
"""

from typing import Any
from pydantic import BaseModel, validator

from core.database import DatabaseService
from core.events import EventBus
from core.errors import ValidationError


# Settings schemas with validation
class GlobalSettings(BaseModel):
    """
    Global application settings.
    
    Hey future me – These are system-wide settings that affect all modules.
    Validated on save to prevent invalid configuration.
    """
    port: int = 8765
    log_level: str = "INFO"
    music_directory: str = "/music"
    download_directory: str = "/downloads"
    theme: str = "dark"
    language: str = "en"
    
    @validator("port")
    def validate_port(cls, v):
        if not (1024 <= v <= 65535):
            raise ValueError("Port must be between 1024 and 65535")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        if v not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            raise ValueError("Invalid log level")
        return v
    
    @validator("theme")
    def validate_theme(cls, v):
        if v not in ["light", "dark"]:
            raise ValueError("Theme must be 'light' or 'dark'")
        return v


class ModuleSettings(BaseModel):
    """Module-specific settings."""
    enabled: bool = True
    # Module-specific fields added in subclasses


class SpotifySettings(ModuleSettings):
    """Spotify module settings."""
    market: str = "US"
    search_limit: int = 20
    cache_ttl: int = 300
    
    @validator("search_limit")
    def validate_search_limit(cls, v):
        if not (1 <= v <= 50):
            raise ValueError("Search limit must be between 1 and 50")
        return v


class SoulseekSettings(ModuleSettings):
    """Soulseek module settings."""
    search_timeout: int = 30
    max_downloads: int = 3
    quality_filter: str = "320kbps+"
    
    @validator("max_downloads")
    def validate_max_downloads(cls, v):
        if not (1 <= v <= 10):
            raise ValueError("Max downloads must be between 1 and 10")
        return v


class SettingsService:
    """
    Settings persistence service.
    
    Args:
        db_service: Database Module for settings storage
        event_bus: Event Bus for change notifications
    """
    
    def __init__(
        self,
        db_service: DatabaseService,
        event_bus: EventBus
    ):
        self.db = db_service
        self.events = event_bus
    
    async def get_global_settings(self) -> GlobalSettings:
        """
        Get global application settings.
        
        Returns defaults if not set.
        
        Returns:
            Global settings with all fields
            
        Examples:
            >>> settings = await settings_service.get_global_settings()
            >>> print(settings.port)
            8765
        """
        stored = await self.db.get("settings", "global")
        
        if not stored:
            # Return defaults
            return GlobalSettings()
        
        return GlobalSettings(**stored)
    
    async def save_global_settings(
        self,
        settings: GlobalSettings
    ) -> None:
        """
        Save global settings.
        
        Validates settings, persists to Database Module, publishes event.
        
        Args:
            settings: Validated global settings
            
        Raises:
            ValidationError: If settings invalid
            
        Examples:
            >>> settings = GlobalSettings(port=8765, theme="dark")
            >>> await settings_service.save_global_settings(settings)
        """
        # Validate (Pydantic does this automatically)
        settings_dict = settings.dict()
        
        # Save via Database Module
        await self.db.save(
            entity_type="settings",
            entity_data={
                "id": "global",
                **settings_dict
            }
        )
        
        # Publish change event
        await self.events.publish(
            "settings.global.changed",
            settings_dict
        )
    
    async def get_module_settings(
        self,
        module_name: str,
        schema: type[ModuleSettings]
    ) -> ModuleSettings:
        """
        Get module-specific settings.
        
        Args:
            module_name: Module identifier (e.g., "spotify")
            schema: Pydantic model for validation
            
        Returns:
            Module settings with defaults if not set
            
        Examples:
            >>> spotify_settings = await settings_service.get_module_settings(
            ...     "spotify",
            ...     SpotifySettings
            ... )
            >>> print(spotify_settings.market)
            "US"
        """
        stored = await self.db.get("settings", module_name)
        
        if not stored:
            return schema()  # Defaults
        
        return schema(**stored)
    
    async def save_module_settings(
        self,
        module_name: str,
        settings: ModuleSettings
    ) -> None:
        """
        Save module settings.
        
        Args:
            module_name: Module identifier
            settings: Validated module settings
            
        Examples:
            >>> settings = SpotifySettings(market="DE", search_limit=30)
            >>> await settings_service.save_module_settings("spotify", settings)
        """
        settings_dict = settings.dict()
        
        await self.db.save(
            entity_type="settings",
            entity_data={
                "id": module_name,
                **settings_dict
            }
        )
        
        await self.events.publish(
            f"settings.{module_name}.changed",
            settings_dict
        )
    
    async def save_credentials(
        self,
        service_name: str,
        credentials: dict,
        sensitive_keys: list[str]
    ) -> None:
        """
        Save service credentials (encrypted).
        
        Args:
            service_name: Service identifier (e.g., "spotify_credentials")
            credentials: Credential dict
            sensitive_keys: Keys to encrypt (e.g., ["client_secret", "api_key"])
            
        Examples:
            >>> await settings_service.save_credentials(
            ...     "spotify_credentials",
            ...     {"client_id": "abc", "client_secret": "secret"},
            ...     ["client_secret"]
            ... )
        """
        await self.db.save(
            entity_type="credentials",
            entity_data={
                "id": service_name,
                **credentials
            },
            sensitive_keys=sensitive_keys
        )
        
        await self.events.publish(
            f"credentials.{service_name}.updated",
            {"service": service_name}
        )
    
    async def get_credentials(
        self,
        service_name: str
    ) -> dict | None:
        """
        Get service credentials (decrypted automatically).
        
        Args:
            service_name: Service identifier
            
        Returns:
            Credentials dict (decrypted) or None if not set
            
        Examples:
            >>> creds = await settings_service.get_credentials("spotify_credentials")
            >>> print(creds["client_id"])
            "abc123"
        """
        return await self.db.get("credentials", service_name)
```

### 3.3 Settings UI Integration

**Settings stored via Database Module, accessed via Settings Service:**

```python
# modules/settings/backend/api/routes.py

"""
Settings API endpoints.

All settings managed via Settings Service → Database Module.
No direct database access, no .env files.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.settings import SettingsService, GlobalSettings, SpotifySettings
from core.database import get_database_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/global")
async def get_global_settings(
    settings_service: SettingsService = Depends(get_settings_service)
) -> GlobalSettings:
    """Get global settings."""
    return await settings_service.get_global_settings()


@router.post("/global")
async def save_global_settings(
    settings: GlobalSettings,
    settings_service: SettingsService = Depends(get_settings_service)
) -> dict:
    """Save global settings."""
    await settings_service.save_global_settings(settings)
    return {"status": "saved"}


@router.get("/spotify")
async def get_spotify_settings(
    settings_service: SettingsService = Depends(get_settings_service)
) -> SpotifySettings:
    """Get Spotify module settings."""
    return await settings_service.get_module_settings("spotify", SpotifySettings)


@router.post("/spotify")
async def save_spotify_settings(
    settings: SpotifySettings,
    settings_service: SettingsService = Depends(get_settings_service)
) -> dict:
    """Save Spotify settings."""
    await settings_service.save_module_settings("spotify", settings)
    return {"status": "saved"}


@router.post("/spotify/credentials")
async def save_spotify_credentials(
    client_id: str,
    client_secret: str,
    settings_service: SettingsService = Depends(get_settings_service)
) -> dict:
    """Save Spotify API credentials (encrypted)."""
    await settings_service.save_credentials(
        "spotify_credentials",
        {"client_id": client_id, "client_secret": client_secret},
        ["client_secret"]  # Encrypt client_secret
    )
    return {"status": "saved"}
```

---

## 4. Summary

### 4.1 Authentication Architecture

**No User Authentication:**
- ✅ Single-user, local deployment
- ✅ No login/logout
- ✅ No sessions or JWT
- ✅ UI accessible at http://localhost:8765 without auth

**Service Authentication:**
- ✅ Spotify OAuth 2.0 (Authorization Code + PKCE)
- ✅ Token extraction and automatic refresh
- ✅ Encrypted token storage via Database Module
- ✅ Background task for proactive token refresh

### 4.2 Settings Persistence

**Storage Strategy:**
- ✅ All settings via Database Module
- ✅ No .env files (replaced by onboarding + DB)
- ✅ Settings Service with validation (Pydantic)
- ✅ Encrypted credentials (Fernet via Database Module)
- ✅ Event-driven change notifications
- ✅ Type-safe access with defaults

### 4.3 Implementation Priority

**Phase 1: Core (Week 1)**
1. Database Module (entity types: settings, credentials, oauth_session)
2. Settings Service
3. Event Bus integration

**Phase 2: Spotify Auth (Week 2)**
1. OAuth Service (start_authorization, handle_callback, refresh_token)
2. Background token refresh task
3. API endpoints (/spotify/auth/start, /spotify/auth/callback)

**Phase 3: Settings UI (Week 3)**
1. Settings API endpoints
2. Settings cards (UI Design System)
3. Onboarding wizard integration

---

**This architecture provides secure, simple authentication and settings management for single-user local deployment.**
