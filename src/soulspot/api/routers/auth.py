"""Authentication and OAuth endpoints."""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from soulspot.api.dependencies import (
    get_credentials_service,
    get_session_id,
    get_session_store,
    get_spotify_auth_service,
)
from soulspot.application.services.credentials_service import CredentialsService
from soulspot.application.services.session_store import DatabaseSessionStore
from soulspot.application.services.spotify_auth_service import SpotifyAuthService
from soulspot.config import Settings, get_settings

if TYPE_CHECKING:
    from soulspot.application.services.token_manager import DatabaseTokenManager

logger = logging.getLogger(__name__)

router = APIRouter()


# Hey future me, this is the START of the OAuth dance. We create a session FIRST with state+verifier
# BEFORE sending user to Spotify. Why? Because when Spotify redirects back, we need to verify the
# state matches (CSRF protection!) and we need the verifier to exchange the auth code. The session
# cookie is HttpOnly to prevent XSS, and SameSite=lax to allow Spotify's redirect. DON'T make it
# SameSite=strict or the callback will fail! Secure flag depends on settings - True in prod with HTTPS.
# REFACTORED (Dec 2025): Now uses SpotifyAuthService for cleaner OAuth handling!
@router.get("/authorize")
async def authorize(
    response: Response,
    settings: Settings = Depends(get_settings),
    session_store: DatabaseSessionStore = Depends(get_session_store),
    auth_service: SpotifyAuthService = Depends(get_spotify_auth_service),
) -> dict[str, Any]:
    """Start OAuth authorization flow with session management.

    Creates a new session, stores OAuth state and PKCE verifier securely,
    and returns the authorization URL.

    Args:
        response: FastAPI response for setting cookies
        settings: Application settings
        session_store: Session store for managing user sessions
        auth_service: SpotifyAuthService for OAuth URL generation

    Returns:
        Authorization URL for user to visit
    """
    # Generate auth URL with state and PKCE verifier
    auth_result = await auth_service.generate_auth_url()

    # Create session and store state + verifier
    session = await session_store.create_session(
        oauth_state=auth_result.state, code_verifier=auth_result.code_verifier
    )

    # Set session cookie (HttpOnly for security, Secure flag from settings)
    response.set_cookie(
        key=settings.api.session_cookie_name,
        value=session.session_id,
        httponly=True,
        secure=settings.api.secure_cookies,  # Configurable - True in production with HTTPS
        samesite="lax",
        max_age=settings.api.session_max_age,
    )

    return {
        "authorization_url": auth_result.authorization_url,
        "message": "Visit the authorization_url to grant access. Your session is stored securely.",
    }


# Listen up future me, this callback is WHERE SECURITY MATTERS MOST! We verify THREE things:
# 1) Session cookie exists and is valid (prevent session fixation)
# 2) OAuth state matches what we stored (prevent CSRF - attacker can't replay old codes)
# 3) Code verifier exists (needed for PKCE token exchange)
# If ANY check fails, REJECT immediately. Attackers WILL try to bypass these. The redirect_to
# parameter lets us send users back to where they came from, but we default to "/" for safety.
# After token exchange succeeds, we CLEAR the state+verifier from session - they're one-time use only!
#
# NEW: We also store tokens in DatabaseTokenManager for background workers (WatchlistWorker, etc.)
# This is SEPARATE from session storage - workers need tokens even when no user session is active!
# REFACTORED (Dec 2025): Now uses SpotifyAuthService for cleaner OAuth handling!
@router.get("/callback", response_model=None)
async def callback(
    request: Request,
    code: str = Query(..., description="Authorization code from Spotify"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    redirect_to: str = Query("/", description="Redirect URL after success"),
    session_store: DatabaseSessionStore = Depends(get_session_store),
    auth_service: SpotifyAuthService = Depends(get_spotify_auth_service),
    session_id: str | None = Cookie(None, alias="session_id"),
) -> RedirectResponse | dict[str, Any]:
    """Handle OAuth callback from Spotify with session verification.

    Verifies the OAuth state matches the stored session state (CSRF protection),
    exchanges the authorization code for tokens, and stores them in:
    1. User session (for user requests)
    2. DatabaseTokenManager (for background workers)

    Args:
        request: FastAPI request (for app.state access)
        code: Authorization code from Spotify
        state: CSRF protection state
        redirect_to: URL to redirect to after successful authentication
        session_store: Session store
        auth_service: SpotifyAuthService for token exchange
        session_id: Session ID from cookie

    Returns:
        Redirect to specified URL or success message with token info

    Raises:
        HTTPException: If session or state verification fails
    """
    # Verify session exists
    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="No session found. Please start authorization flow again.",
        )

    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session. Please start authorization flow again.",
        )

    # Verify state matches (CSRF protection)
    if session.oauth_state != state:
        raise HTTPException(
            status_code=400, detail="State verification failed. Possible CSRF attack."
        )

    # Get code verifier from session
    if not session.code_verifier:
        raise HTTPException(
            status_code=400, detail="Code verifier not found in session."
        )

    try:
        # Exchange code for tokens using SpotifyAuthService
        token_result = await auth_service.exchange_code(code, session.code_verifier)

        # Store tokens in session (for user requests)
        session.set_tokens(
            access_token=token_result.access_token,
            refresh_token=token_result.refresh_token or "",
            expires_in=token_result.expires_in,
        )

        # Clear OAuth state and verifier (no longer needed)
        session.oauth_state = None
        session.code_verifier = None

        # Persist session changes to database
        await session_store.update_session(
            session.session_id,
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            token_expires_at=session.token_expires_at,
            oauth_state=None,
            code_verifier=None,
        )

        # NEW: Also store tokens in DatabaseTokenManager for background workers!
        # This is CRITICAL for WatchlistWorker, DiscographyWorker, etc.
        if hasattr(request.app.state, "db_token_manager"):
            db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager
            await db_token_manager.store_from_oauth(
                access_token=token_result.access_token,
                refresh_token=token_result.refresh_token or "",
                expires_in=token_result.expires_in,
                scope=token_result.scope,
            )

        # Redirect to specified URL (default: dashboard)
        return RedirectResponse(url=redirect_to, status_code=302)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to exchange code: {str(e)}"
        ) from e


# Yo future me, Spotify access tokens expire after 1 hour! This endpoint is your LIFELINE to keep
# users logged in without forcing re-auth. We use the refresh_token (which doesn't expire) to get
# a new access_token. IMPORTANT: Spotify MIGHT return a new refresh_token or might not - if they
# don't, keep using the old one! Don't overwrite it with None or you'll break everything. This is
# idempotent - safe to call multiple times, unlike the auth flow which is one-shot.
# REFACTORED (Dec 2025): Now uses SpotifyAuthService for cleaner OAuth handling!
@router.post("/refresh")
async def refresh_token(
    session_store: DatabaseSessionStore = Depends(get_session_store),
    auth_service: SpotifyAuthService = Depends(get_spotify_auth_service),
    session_id: str | None = Depends(get_session_id),
) -> dict[str, Any]:
    """Refresh access token using session's refresh token.

    Retrieves the refresh token from the session and obtains a new access token.

    Args:
        session_store: Session store
        auth_service: SpotifyAuthService for token refresh
        session_id: Session ID from cookie or Authorization header

    Returns:
        New token information

    Raises:
        HTTPException: If session or refresh token not found
    """
    # Verify session exists
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found.")

    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    if not session.refresh_token:
        raise HTTPException(
            status_code=400,
            detail="No refresh token in session. Please re-authenticate.",
        )

    try:
        # Use SpotifyAuthService for token refresh
        token_result = await auth_service.refresh_token(session.refresh_token)

        # Update session with new token
        # Use old refresh token if Spotify didn't return a new one
        new_refresh_token = token_result.refresh_token or session.refresh_token
        session.set_tokens(
            access_token=token_result.access_token,
            refresh_token=new_refresh_token,
            expires_in=token_result.expires_in,
        )

        # Persist session changes to database
        await session_store.update_session(
            session.session_id,
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            token_expires_at=session.token_expires_at,
        )

        return {
            "message": "Token refreshed successfully",
            "expires_in": token_result.expires_in,
            "token_type": token_result.token_type,
        }
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to refresh token: {str(e)}"
        ) from e


# Hey, this is a SAFE read-only session check - we DON'T return actual tokens (security risk!),
# just metadata about the session state. Frontend uses this to decide if user needs to re-auth.
# The has_access_token/has_refresh_token bools are intentionally vague - we don't leak token values.
# token_expired check is critical - even if we have a token, it might be stale. Trust this over
# just checking token existence!
@router.get("/session")
async def get_session_info(
    session_store: DatabaseSessionStore = Depends(get_session_store),
    session_id: str | None = Depends(get_session_id),
) -> dict[str, Any]:
    """Get current session information.

    Args:
        session_id: Session ID from cookie or Authorization header
        session_store: Session store

    Returns:
        Session information (without sensitive tokens)

    Raises:
        HTTPException: If no session found
    """
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found.")

    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    return {
        "session_id": session.session_id,
        "has_access_token": session.access_token is not None,
        "has_refresh_token": session.refresh_token is not None,
        "token_expired": session.is_token_expired(),
        "created_at": session.created_at.isoformat(),
        "last_accessed_at": session.last_accessed_at.isoformat(),
    }


# Listen, logout should ALWAYS succeed - even if session is already gone! That's why we check
# session_id first and only delete if it exists. We also delete the cookie to prevent the browser
# from sending stale session IDs. This is a POST not GET to prevent CSRF logout attacks (attacker
# embedding <img src="/logout"> to force logout). Logout is destructive - session is GONE forever,
# user needs full OAuth flow to log back in.
@router.post("/logout")
async def logout(
    response: Response,
    settings: Settings = Depends(get_settings),
    session_store: DatabaseSessionStore = Depends(get_session_store),
    session_id: str | None = Depends(get_session_id),
) -> dict[str, Any]:
    """Log out and delete session.

    Args:
        response: FastAPI response for clearing cookies
        settings: Application settings
        session_id: Session ID from cookie or Authorization header
        session_store: Session store

    Returns:
        Logout confirmation
    """
    if session_id:
        await session_store.delete_session(session_id)
        response.delete_cookie(key=settings.api.session_cookie_name)
        return {"message": "Logged out successfully"}

    return {"message": "No active session"}


# Yo, this status check is for the onboarding UI flow. Unlike /session, this returns friendly
# messages for when things are missing. We check the SHARED DatabaseTokenManager token now -
# this way ANY device can check if Spotify is connected, not just the browser that did OAuth!
# The "connected" bool is the single source of truth the frontend should trust. If false, show
# the "connect Spotify" button. If true, proceed with API calls. Don't cache this response -
# token state can change!
@router.get("/spotify/status")
async def spotify_status(
    request: Request,
) -> dict[str, Any]:
    """Get Spotify connection status for onboarding flow.

    Checks the SHARED server-side token (DatabaseTokenManager), so ANY device
    on the network can see if Spotify is connected - not just the browser that
    did the OAuth flow.

    Args:
        request: FastAPI request (for app.state access)

    Returns:
        Connection status information
    """
    # Hey future me - we check DatabaseTokenManager, not per-session token!
    # This is the key change for multi-device support.
    if not hasattr(request.app.state, "db_token_manager"):
        return {
            "connected": False,
            "provider": "spotify",
            "message": "Token manager not initialized",
        }

    db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager
    status = await db_token_manager.get_status()

    return {
        "connected": status.is_valid and not status.needs_reauth,
        "provider": "spotify",
        "expires_in_minutes": status.expires_in_minutes,
        "token_expired": status.needs_reauth,
        "needs_reauth": status.needs_reauth,
        "last_error": status.last_error,
    }


# Hey future me, this skip endpoint is for users who want to explore the UI without connecting
# Spotify first. It's basically a no-op right now (we just return OK), but I left the session
# check in case we want to track "skipped onboarding" state later. Don't delete this endpoint -
# the frontend onboarding flow expects it! If you remove it, you'll break the skip button.
@router.post("/onboarding/skip")
async def skip_onboarding(
    _response: Response,
    session_store: DatabaseSessionStore = Depends(get_session_store),
    session_id: str | None = Depends(get_session_id),
) -> dict[str, Any]:
    """Skip onboarding and proceed to dashboard.

    Args:
        response: FastAPI response
        session_id: Session ID from cookie or Authorization header
        session_store: Session store

    Returns:
        Skip confirmation
    """
    # Mark onboarding as skipped in session if exists
    if session_id:
        session = await session_store.get_session(session_id)
        if session:
            # Currently no additional metadata needed for skip tracking
            # Session existence already indicates active user
            logger.info(f"User skipped onboarding (session: {session_id[:8]}...)")

    return {
        "ok": True,
        "message": "Onboarding skipped. You can connect Spotify later in settings.",
    }


# =============================================================================
# TOKEN STATUS ENDPOINT (for UI warning banner)
# =============================================================================
# Hey future me - this endpoint is for the UI to check if background workers can access Spotify!
# It's different from /session - that checks USER session, this checks BACKGROUND TOKEN validity.
#
# The UI polls this endpoint (via HTMX) and shows a warning banner if needs_reauth=true.
# This tells users "Hey, background sync stopped working, please re-authenticate!"
#
# When to show the banner:
# - needs_reauth=true → RED banner with "Bitte erneut bei Spotify anmelden"
# - needs_reauth=false → No banner (everything works)
#
# Background workers (WatchlistWorker, etc.) check is_valid flag and skip work when False.
#
# HTMX vs JSON:
# - Default (or Accept: text/html) → Returns HTML partial for HTMX polling
# - Accept: application/json → Returns JSON for API clients
# =============================================================================


@router.get("/token-status")
async def get_token_status(
    request: Request,
    credentials_service: CredentialsService = Depends(get_credentials_service),
) -> Any:
    """Get background token status for UI warning banner.

    This endpoint checks if background workers have a valid Spotify token.
    The UI uses this to show a warning banner when re-authentication is needed.

    IMPORTANT: If Spotify is not configured (no client_id), we return needs_reauth=False
    so the banner doesn't show up. The user hasn't set up Spotify yet, so there's nothing
    to "re-authenticate".

    Content negotiation:
    - Accept: text/html (default for HTMX) → Returns HTML partial
    - Accept: application/json → Returns JSON response

    Returns:
        Token status including:
        - exists: Whether any token is stored
        - is_valid: Whether token is usable (not revoked/expired)
        - needs_reauth: Whether user needs to re-authenticate
        - expires_in_minutes: Minutes until token expires (if valid)
        - last_error: Error message if refresh failed
    """
    # Hey future me - if Spotify isn't configured, don't flag needs_reauth!
    # The user hasn't set up Spotify credentials yet, so there's nothing to re-auth.
    # Now we check DB-first via CredentialsService (falls back to .env for migration period).
    spotify_creds = await credentials_service.get_spotify_credentials()
    spotify_configured = bool(spotify_creds.client_id and spotify_creds.client_id.strip())

    if not spotify_configured:
        # Spotify not configured - no banner needed
        status_data: dict[str, Any] = {
            "exists": False,
            "is_valid": False,
            "needs_reauth": False,  # Don't show banner!
            "expires_in_minutes": None,
            "last_error": None,
            "last_error_at": None,
            "spotify_configured": False,
        }
    elif not hasattr(request.app.state, "db_token_manager"):
        # Token manager not initialized (shouldn't happen in production)
        status_data = {
            "exists": False,
            "is_valid": False,
            "needs_reauth": True,
            "expires_in_minutes": None,
            "last_error": "Token manager not initialized",
            "last_error_at": None,
            "spotify_configured": True,
        }
    else:
        db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager
        status = await db_token_manager.get_status()

        status_data = {
            "exists": status.exists,
            "is_valid": status.is_valid,
            "needs_reauth": status.needs_reauth,
            "expires_in_minutes": status.expires_in_minutes,
            "last_error": status.last_error,
            "last_error_at": status.last_error_at.isoformat()
            if status.last_error_at
            else None,
            "spotify_configured": True,
        }

    # Check Accept header for content negotiation
    # HTMX sends "text/html" by default, API clients send "application/json"
    accept_header = request.headers.get("accept", "text/html")

    if "application/json" in accept_header:
        # Return JSON for API clients
        return status_data

    # Return JSON for all requests now - banner removed, status used by vinyl player & toasts
    return status_data


# Hey - manual token invalidation for disconnect/logout from Spotify
@router.post("/token-invalidate")
async def invalidate_token(
    request: Request,
) -> dict[str, Any]:
    """Manually invalidate the background token.

    Use this when user wants to disconnect Spotify integration.
    Background workers will stop until user re-authenticates.

    Returns:
        Confirmation message
    """
    if not hasattr(request.app.state, "db_token_manager"):
        return {"ok": False, "message": "Token manager not initialized"}

    db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager
    result = await db_token_manager.invalidate()

    if result:
        return {
            "ok": True,
            "message": "Token invalidated. Please re-authenticate to enable background sync.",
        }
    else:
        return {"ok": False, "message": "No token to invalidate"}
