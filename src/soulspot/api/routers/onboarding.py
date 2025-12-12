"""Onboarding API endpoints for first-time setup flow."""

# Hey future me - dieser Router handled das Onboarding-Flow!
# Multi-Step-Wizard: Spotify OAuth → Soulseek Config → Fertig
# Skip-Funktion tracked ob User übersprungen hat, damit Dashboard Banner zeigen kann.

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_credentials_service, get_db_session
from soulspot.application.services.app_settings_service import AppSettingsService
from soulspot.application.services.credentials_service import CredentialsService

logger = logging.getLogger(__name__)

router = APIRouter()


class OnboardingStatus(BaseModel):
    """Current onboarding state."""

    completed: bool = Field(description="Whether onboarding was fully completed")
    skipped: bool = Field(description="Whether onboarding was skipped")
    current_step: int = Field(
        description="Current step (1=Spotify, 2=Soulseek, 3=Done)"
    )
    spotify_connected: bool = Field(description="Spotify OAuth done")
    soulseek_configured: bool = Field(description="Soulseek credentials saved")
    show_banner: bool = Field(
        description="Whether to show 'Complete Setup' banner on Dashboard"
    )


class OnboardingComplete(BaseModel):
    """Request to mark onboarding as complete."""

    skipped: bool = Field(default=False, description="Whether user skipped some steps")


class SlskdTestRequest(BaseModel):
    """Request to test Soulseek connection."""

    url: str = Field(description="slskd URL (e.g., http://localhost:5030)")
    username: str = Field(description="slskd username")
    password: str = Field(description="slskd password")
    api_key: str | None = Field(default=None, description="slskd API key (optional)")


class SlskdTestResponse(BaseModel):
    """Response from Soulseek connection test."""

    success: bool = Field(description="Whether connection was successful")
    message: str = Field(description="Status message")
    version: str | None = Field(default=None, description="slskd version if connected")
    error: str | None = Field(default=None, description="Error message if failed")


# Hey future me - dieser Endpoint gibt den aktuellen Onboarding-Status zurück!
# Das Dashboard checkt diesen Endpoint um zu entscheiden ob es den "Setup fortsetzen"
# Banner zeigen soll. show_banner ist True wenn:
# - Onboarding nicht completed UND
# - User es übersprungen hat (skipped=true)
@router.get("/status")
async def get_onboarding_status(
    db: AsyncSession = Depends(get_db_session),
    credentials_service: CredentialsService = Depends(get_credentials_service),
) -> OnboardingStatus:
    """Get current onboarding status.

    Used by Dashboard to decide whether to show 'Complete Setup' banner.
    Also used by Onboarding page to restore state on page reload.

    Returns:
        Current onboarding state including Spotify/Soulseek config status
    """
    from soulspot.infrastructure.persistence.repositories import SpotifyTokenRepository

    settings_service = AppSettingsService(db)

    # Check Spotify connection (via stored token)
    token_repo = SpotifyTokenRepository(db)
    token = await token_repo.get_active_token()
    spotify_connected = token is not None and token.access_token is not None

    # Check Soulseek configuration (via DB first, env fallback via CredentialsService)
    # Hey future me - Soulseek ist konfiguriert wenn URL + (API Key ODER Username/Password) gesetzt sind
    slskd_creds = await credentials_service.get_slskd_credentials()
    soulseek_url_set = bool(slskd_creds.url and slskd_creds.url.strip())
    soulseek_auth_set = bool(slskd_creds.api_key) or (
        bool(slskd_creds.username) and bool(slskd_creds.password)
    )
    soulseek_configured = soulseek_url_set and soulseek_auth_set

    # Check onboarding flags from DB
    completed = await settings_service.get_bool("onboarding.completed", default=False)
    skipped = await settings_service.get_bool("onboarding.skipped", default=False)

    # Determine current step
    if completed:
        current_step = 3  # Done
    elif spotify_connected and soulseek_configured:
        current_step = 3  # Ready to complete
    elif spotify_connected:
        current_step = 2  # Soulseek step
    else:
        current_step = 1  # Spotify step

    # Show banner if skipped or not completed (but user has been to onboarding before)
    show_banner = not completed and skipped

    return OnboardingStatus(
        completed=completed,
        skipped=skipped,
        current_step=current_step,
        spotify_connected=spotify_connected,
        soulseek_configured=soulseek_configured,
        show_banner=show_banner,
    )


# Hey future me - markiert das Onboarding als abgeschlossen!
# Wird aufgerufen wenn User auf "Fertig" klickt oder alle Steps durchlaufen hat.
# Wenn skipped=true, zeigen wir später den Banner auf dem Dashboard.
@router.post("/complete")
async def complete_onboarding(
    request: OnboardingComplete,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Mark onboarding as complete.

    Sets the onboarding.completed flag in DB. If skipped=true,
    also sets onboarding.skipped so Dashboard shows reminder banner.

    Args:
        request: Completion request with optional skipped flag

    Returns:
        Success message
    """
    settings_service = AppSettingsService(db)

    await settings_service.set(
        "onboarding.completed",
        True,
        value_type="boolean",
        category="onboarding",
    )

    if request.skipped:
        await settings_service.set(
            "onboarding.skipped",
            True,
            value_type="boolean",
            category="onboarding",
        )

    await db.commit()

    logger.info("Onboarding completed (skipped=%s)", request.skipped)

    return {
        "success": True,
        "message": "Onboarding completed",
        "skipped": request.skipped,
    }


# Hey future me - setzt den "skipped" Flag ohne das Onboarding als completed zu markieren!
# Wird aufgerufen wenn User "Nicht jetzt" klickt.
@router.post("/skip")
async def skip_onboarding(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Skip onboarding for now.

    Sets onboarding.skipped flag so Dashboard shows reminder banner.
    Does NOT set completed flag - user can continue later.

    Returns:
        Success message
    """
    settings_service = AppSettingsService(db)

    await settings_service.set(
        "onboarding.skipped",
        True,
        value_type="boolean",
        category="onboarding",
    )

    await db.commit()

    return {
        "success": True,
        "message": "Onboarding skipped. You can complete setup later in Settings.",
    }


# Hey future me - testet die Soulseek/slskd Verbindung VOR dem Speichern!
# Der User gibt URL + Credentials ein, wir testen ob die Verbindung funktioniert.
# Wenn ja, kann der User auf "Speichern" klicken. Wenn nein, zeigen wir den Fehler.
# WICHTIG: Dieser Endpoint speichert NICHTS - er testet nur!
@router.post("/test-slskd")
async def test_slskd_connection(
    request: SlskdTestRequest,
) -> SlskdTestResponse:
    """Test Soulseek (slskd) connection with provided credentials.

    Attempts to connect to slskd API and verify credentials.
    Does NOT save credentials - just tests them.

    IMPORTANT: This tests the connection BEFORE saving to env/settings.
    If successful, user should call PATCH /api/settings/ to save.

    Args:
        request: Connection details to test

    Returns:
        Test result with success/failure and optional version info
    """
    import httpx

    url = request.url.rstrip("/")

    # Build headers based on auth method
    headers = {"Content-Type": "application/json"}

    # Prefer API key if provided
    if request.api_key:
        headers["X-API-Key"] = request.api_key
        auth = None
    else:
        auth = httpx.BasicAuth(request.username, request.password)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to hit the slskd health/version endpoint
            # Hey future me - slskd hat verschiedene API Versionen!
            # v0 ist die aktuelle, aber es gibt auch /api/v0/application für Status
            response = await client.get(
                f"{url}/api/v0/application",
                headers=headers,
                auth=auth,
            )

            if response.status_code == 200:
                data = response.json()
                version = data.get("version", "unknown")

                return SlskdTestResponse(
                    success=True,
                    message=f"Verbindung erfolgreich! slskd Version: {version}",
                    version=version,
                )
            elif response.status_code == 401:
                return SlskdTestResponse(
                    success=False,
                    message="Authentifizierung fehlgeschlagen",
                    error="Ungültiger API-Key oder Benutzername/Passwort",
                )
            elif response.status_code == 403:
                return SlskdTestResponse(
                    success=False,
                    message="Zugriff verweigert",
                    error="API-Key oder Benutzer hat keine Berechtigung",
                )
            else:
                return SlskdTestResponse(
                    success=False,
                    message=f"Unerwarteter Status: {response.status_code}",
                    error=response.text[:200] if response.text else "Keine Details",
                )

    except httpx.ConnectError:
        return SlskdTestResponse(
            success=False,
            message="Verbindung fehlgeschlagen",
            error=f"Kann nicht zu {url} verbinden. Ist slskd gestartet?",
        )
    except httpx.TimeoutException:
        return SlskdTestResponse(
            success=False,
            message="Timeout",
            error="Verbindung dauert zu lange. Server antwortet nicht.",
        )
    except Exception as e:
        logger.exception("slskd connection test failed")
        return SlskdTestResponse(
            success=False,
            message="Fehler beim Testen",
            error=str(e),
        )


# Hey future me - speichert die Soulseek Credentials in der Datenbank!
# Das ist ein Wrapper um den Settings-Endpoint, speziell für Onboarding.
# WICHTIG: Diese Settings sind NICHT in .env - sie werden in der DB gespeichert
# und beim nächsten App-Start geladen. Das ist by design, damit User die
# Credentials ohne Server-Restart ändern können.
@router.post("/save-slskd")
async def save_slskd_credentials(
    request: SlskdTestRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Save Soulseek (slskd) credentials to database.

    Saves the credentials that were previously tested with /test-slskd.
    These are stored in DB and loaded on app startup.

    Args:
        request: Credentials to save

    Returns:
        Success message
    """
    settings_service = AppSettingsService(db)

    # Save each setting
    await settings_service.set(
        "slskd.url",
        request.url,
        value_type="string",
        category="slskd",
    )
    await settings_service.set(
        "slskd.username",
        request.username,
        value_type="string",
        category="slskd",
    )
    await settings_service.set(
        "slskd.password",
        request.password,
        value_type="string",
        category="slskd",
    )
    if request.api_key:
        await settings_service.set(
            "slskd.api_key",
            request.api_key,
            value_type="string",
            category="slskd",
        )

    await db.commit()

    logger.info("Soulseek credentials saved via onboarding")

    return {
        "success": True,
        "message": "Soulseek-Einstellungen gespeichert",
    }
