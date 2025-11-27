"""Authentication and OAuth endpoints."""

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from soulspot.api.dependencies import (
    get_session_id,
    get_session_store,
)
from soulspot.application.services.session_store import DatabaseSessionStore
from soulspot.config import Settings, get_settings
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

if TYPE_CHECKING:
    from soulspot.application.services.token_manager import DatabaseTokenManager

router = APIRouter()


# Hey future me, this is the START of the OAuth dance. We create a session FIRST with state+verifier
# BEFORE sending user to Spotify. Why? Because when Spotify redirects back, we need to verify the
# state matches (CSRF protection!) and we need the verifier to exchange the auth code. The session
# cookie is HttpOnly to prevent XSS, and SameSite=lax to allow Spotify's redirect. DON'T make it
# SameSite=strict or the callback will fail! Secure flag depends on settings - True in prod with HTTPS.
@router.get("/authorize")
async def authorize(
    response: Response,
    settings: Settings = Depends(get_settings),
    session_store: DatabaseSessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    """Start OAuth authorization flow with session management.

    Creates a new session, stores OAuth state and PKCE verifier securely,
    and returns the authorization URL.

    Args:
        response: FastAPI response for setting cookies
        settings: Application settings
        session_store: Session store for managing user sessions

    Returns:
        Authorization URL for user to visit
    """
    spotify_client = SpotifyClient(settings.spotify)

    # Generate state for CSRF protection and PKCE verifier
    import secrets

    state = secrets.token_urlsafe(32)
    code_verifier = SpotifyClient.generate_code_verifier()

    # Create session and store state + verifier
    session = await session_store.create_session(
        oauth_state=state, code_verifier=code_verifier
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

    # Get authorization URL
    auth_url = await spotify_client.get_authorization_url(state, code_verifier)

    return {
        "authorization_url": auth_url,
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
@router.get("/callback", response_model=None)
async def callback(
    request: Request,
    code: str = Query(..., description="Authorization code from Spotify"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    redirect_to: str = Query("/", description="Redirect URL after success"),
    settings: Settings = Depends(get_settings),
    session_store: DatabaseSessionStore = Depends(get_session_store),
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
        session_id: Session ID from cookie
        settings: Application settings
        session_store: Session store

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

    spotify_client = SpotifyClient(settings.spotify)

    try:
        # Exchange code for tokens
        token_data = await spotify_client.exchange_code(code, session.code_verifier)

        # Store tokens in session (for user requests)
        session.set_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", ""),
            expires_in=token_data.get("expires_in", 3600),
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
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", ""),
                expires_in=token_data.get("expires_in", 3600),
                scope=token_data.get("scope"),
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
@router.post("/refresh")
async def refresh_token(
    settings: Settings = Depends(get_settings),
    session_store: DatabaseSessionStore = Depends(get_session_store),
    session_id: str | None = Depends(get_session_id),
) -> dict[str, Any]:
    """Refresh access token using session's refresh token.

    Retrieves the refresh token from the session and obtains a new access token.

    Args:
        session_id: Session ID from cookie or Authorization header
        settings: Application settings
        session_store: Session store

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

    spotify_client = SpotifyClient(settings.spotify)

    try:
        token_data = await spotify_client.refresh_token(session.refresh_token)

        # Update session with new token
        session.set_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get(
                "refresh_token", session.refresh_token
            ),  # Use old refresh token if not provided
            expires_in=token_data.get("expires_in", 3600),
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
            "expires_in": token_data.get("expires_in", 3600),
            "token_type": token_data.get("token_type", "Bearer"),
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
# messages for when things are missing. We check BOTH token existence AND expiration - a common
# bug is having an expired token and thinking you're still connected! The "connected" bool is the
# single source of truth the frontend should trust. If false, show the "connect Spotify" button.
# If true, proceed with API calls. Don't cache this response - token state can change!
@router.get("/spotify/status")
async def spotify_status(
    session_store: DatabaseSessionStore = Depends(get_session_store),
    session_id: str | None = Depends(get_session_id),
) -> dict[str, Any]:
    """Get Spotify connection status for onboarding flow.

    Args:
        session_id: Session ID from cookie or Authorization header
        session_store: Session store

    Returns:
        Connection status information
    """
    if not session_id:
        return {
            "connected": False,
            "provider": "spotify",
            "message": "No session found",
        }

    session = await session_store.get_session(session_id)
    if not session:
        return {
            "connected": False,
            "provider": "spotify",
            "message": "Invalid or expired session",
        }

    # Check if we have a valid, non-expired access token
    has_token = session.access_token is not None
    is_expired = session.is_token_expired()

    return {
        "connected": has_token and not is_expired,
        "provider": "spotify",
        "expires_at": session.token_expires_at.isoformat()
        if session.token_expires_at
        else None,
        "token_expired": is_expired,
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
            # We could add a flag here if needed in the future
            # For now, just acknowledge the skip
            pass

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
) -> Any:
    """Get background token status for UI warning banner.

    This endpoint checks if background workers have a valid Spotify token.
    The UI uses this to show a warning banner when re-authentication is needed.

    Content negotiation:
    - Accept: text/html (default for HTMX) → Returns HTML partial
    - Accept: application/json → Returns JSON response

    Returns:
        Token status including:
        - exists: Whether any token is stored
        - is_valid: Whether token is usable (not revoked/expired)
        - needs_reauth: Whether user needs to re-authenticate (show banner if true)
        - expires_in_minutes: Minutes until token expires (if valid)
        - last_error: Error message if refresh failed
    """
    from fastapi.responses import HTMLResponse

    # Check if DatabaseTokenManager is initialized
    if not hasattr(request.app.state, "db_token_manager"):
        status_data: dict[str, Any] = {
            "exists": False,
            "is_valid": False,
            "needs_reauth": True,
            "expires_in_minutes": None,
            "last_error": "Token manager not initialized",
            "last_error_at": None,
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
        }

    # Check Accept header for content negotiation
    # HTMX sends "text/html" by default, API clients send "application/json"
    accept_header = request.headers.get("accept", "text/html")

    if "application/json" in accept_header:
        # Return JSON for API clients
        return status_data

    # Return HTML partial for HTMX polling
    # Hey future me - this HTML is directly swapped into #token-status-banner via HTMX.
    # Only show the banner when needs_reauth is true! When token is valid, return empty div
    # so the banner disappears. The red styling is inline for simplicity - matches the app's
    # red accent color. The /api/auth/authorize endpoint starts the re-auth flow.
    if status_data["needs_reauth"]:
        # Show warning banner
        error_detail = ""
        if status_data.get("last_error"):
            error_detail = f" ({status_data['last_error']})"

        html = f"""
        <div class="token-warning-banner" style="
            background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
            color: white;
            padding: 12px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            border-radius: 8px;
            margin: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        ">
            <div style="display: flex; align-items: center; gap: 12px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
                <span style="font-weight: 500;">
                    Spotify-Verbindung unterbrochen{error_detail}. Hintergrund-Sync ist pausiert.
                </span>
            </div>
            <a href="/api/auth/authorize"
               style="
                   background: white;
                   color: #dc2626;
                   padding: 8px 16px;
                   border-radius: 6px;
                   text-decoration: none;
                   font-weight: 600;
                   white-space: nowrap;
                   transition: background 0.2s;
               "
               onmouseover="this.style.background='#f3f4f6'"
               onmouseout="this.style.background='white'">
                Erneut anmelden
            </a>
        </div>
        """
        return HTMLResponse(content=html)
    else:
        # Token is valid - return empty div (banner disappears)
        return HTMLResponse(content="")


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
