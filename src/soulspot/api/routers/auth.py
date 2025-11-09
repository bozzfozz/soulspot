"""Authentication and OAuth endpoints."""

from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response

from soulspot.api.dependencies import get_session_store
from soulspot.application.services.session_store import SessionStore
from soulspot.config import Settings, get_settings
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

router = APIRouter()


@router.get("/authorize")
async def authorize(
    response: Response,
    settings: Settings = Depends(get_settings),
    session_store: SessionStore = Depends(get_session_store),
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
    session = session_store.create_session(oauth_state=state, code_verifier=code_verifier)

    # Set session cookie (HttpOnly for security)
    response.set_cookie(
        key="session_id",
        value=session.session_id,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=3600,  # 1 hour
    )

    # Get authorization URL
    auth_url = await spotify_client.get_authorization_url(state, code_verifier)

    return {
        "authorization_url": auth_url,
        "message": "Visit the authorization_url to grant access. Your session is stored securely.",
    }


@router.get("/callback")
async def callback(
    code: str = Query(..., description="Authorization code from Spotify"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    session_id: str | None = Cookie(None),
    settings: Settings = Depends(get_settings),
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    """Handle OAuth callback from Spotify with session verification.

    Verifies the OAuth state matches the stored session state (CSRF protection),
    exchanges the authorization code for tokens, and stores them in the session.

    Args:
        code: Authorization code from Spotify
        state: CSRF protection state
        session_id: Session ID from cookie
        settings: Application settings
        session_store: Session store

    Returns:
        Success message with token info
        
    Raises:
        HTTPException: If session or state verification fails
    """
    # Verify session exists
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found. Please start authorization flow again.")

    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please start authorization flow again.")

    # Verify state matches (CSRF protection)
    if session.oauth_state != state:
        raise HTTPException(status_code=400, detail="State verification failed. Possible CSRF attack.")

    # Get code verifier from session
    if not session.code_verifier:
        raise HTTPException(status_code=400, detail="Code verifier not found in session.")

    spotify_client = SpotifyClient(settings.spotify)

    try:
        # Exchange code for tokens
        token_data = await spotify_client.exchange_code(code, session.code_verifier)

        # Store tokens in session
        session.set_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", ""),
            expires_in=token_data.get("expires_in", 3600),
        )

        # Clear OAuth state and verifier (no longer needed)
        session.oauth_state = None
        session.code_verifier = None

        return {
            "message": "Successfully authenticated. Tokens stored in session.",
            "expires_in": token_data.get("expires_in", 3600),
            "token_type": token_data.get("token_type", "Bearer"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to exchange code: {str(e)}") from e


@router.post("/refresh")
async def refresh_token(
    session_id: str | None = Cookie(None),
    settings: Settings = Depends(get_settings),
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    """Refresh access token using session's refresh token.

    Retrieves the refresh token from the session and obtains a new access token.

    Args:
        session_id: Session ID from cookie
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

    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    if not session.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token in session. Please re-authenticate.")

    spotify_client = SpotifyClient(settings.spotify)

    try:
        token_data = await spotify_client.refresh_token(session.refresh_token)

        # Update session with new token
        session.set_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", session.refresh_token),  # Use old refresh token if not provided
            expires_in=token_data.get("expires_in", 3600),
        )

        return {
            "message": "Token refreshed successfully",
            "expires_in": token_data.get("expires_in", 3600),
            "token_type": token_data.get("token_type", "Bearer"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to refresh token: {str(e)}") from e


@router.get("/session")
async def get_session_info(
    session_id: str | None = Cookie(None),
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    """Get current session information.

    Args:
        session_id: Session ID from cookie
        session_store: Session store

    Returns:
        Session information (without sensitive tokens)
        
    Raises:
        HTTPException: If no session found
    """
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found.")

    session = session_store.get_session(session_id)
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


@router.post("/logout")
async def logout(
    response: Response,
    session_id: str | None = Cookie(None),
    session_store: SessionStore = Depends(get_session_store),
) -> dict[str, Any]:
    """Log out and delete session.

    Args:
        response: FastAPI response for clearing cookies
        session_id: Session ID from cookie
        session_store: Session store

    Returns:
        Logout confirmation
    """
    if session_id:
        session_store.delete_session(session_id)
        response.delete_cookie(key="session_id")
        return {"message": "Logged out successfully"}
    
    return {"message": "No active session"}
