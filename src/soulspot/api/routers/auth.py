"""Authentication and OAuth endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from soulspot.config import Settings, get_settings

router = APIRouter()


@router.get("/authorize")
async def authorize(
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Start OAuth authorization flow.

    Returns:
        Authorization URL and state for CSRF protection
    """
    # In production, this should use a TokenManager instance
    # For now, return a simple redirect URL structure
    from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

    spotify_client = SpotifyClient(settings.spotify)

    # Generate state for CSRF protection
    import secrets

    state = secrets.token_urlsafe(32)
    code_verifier = SpotifyClient.generate_code_verifier()

    # Store state and code_verifier in session/redis in production
    # For now, return them in response (not secure for production)
    auth_url = await spotify_client.get_authorization_url(state, code_verifier)

    return {
        "authorization_url": auth_url,
        "state": state,
        "code_verifier": code_verifier,
        "message": "Visit the authorization_url to grant access",
    }


@router.get("/callback")
async def callback(
    code: str = Query(..., description="Authorization code from Spotify"),
    state: str = Query(..., description="State parameter for CSRF protection"),  # noqa: ARG001
    code_verifier: str = Query(..., description="Code verifier for PKCE"),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Handle OAuth callback from Spotify.

    Args:
        code: Authorization code
        state: CSRF protection state
        code_verifier: PKCE code verifier

    Returns:
        Token information
    """
    # TODO: Verify state matches stored state

    from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

    spotify_client = SpotifyClient(settings.spotify)

    try:
        # Exchange code for token
        token_data = await spotify_client.exchange_code(code, code_verifier)

        return {
            "message": "Successfully authenticated",
            "access_token": token_data["access_token"],
            "expires_in": token_data.get("expires_in", 3600),
            "token_type": token_data.get("token_type", "Bearer"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to exchange code: {str(e)}") from e


@router.post("/refresh")
async def refresh_token(
    refresh_token: str = Query(..., description="Refresh token"),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Refresh access token.

    Args:
        refresh_token: Refresh token to use

    Returns:
        New token information
    """
    from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

    spotify_client = SpotifyClient(settings.spotify)

    try:
        token_data = await spotify_client.refresh_token(refresh_token)

        return {
            "message": "Token refreshed successfully",
            "access_token": token_data["access_token"],
            "expires_in": token_data.get("expires_in", 3600),
            "token_type": token_data.get("token_type", "Bearer"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to refresh token: {str(e)}") from e
