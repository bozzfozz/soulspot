"""Credentials Service - Database-first credential management.

Hey future me - this is THE central service for fetching credentials!

Pattern:
1. Check app_settings table (DB) first
2. Fall back to environment variables if DB is empty
3. Settings UI saves to DB, making it the primary source

This enables gradual migration from .env to DB without breaking existing setups.
Users with .env files continue working until they configure via Settings UI.

Usage:
    credentials = CredentialsService(session)
    spotify_config = await credentials.get_spotify_credentials()
    slskd_config = await credentials.get_slskd_credentials()
    deezer_config = await credentials.get_deezer_credentials()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from soulspot.application.services.app_settings_service import AppSettingsService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from soulspot.config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class SpotifyCredentials:
    """Spotify OAuth credentials."""

    client_id: str
    client_secret: str
    redirect_uri: str

    def is_configured(self) -> bool:
        """Check if credentials are complete."""
        return bool(
            self.client_id
            and self.client_id.strip()
            and self.client_secret
            and self.client_secret.strip()
        )


@dataclass
class SlskdCredentials:
    """slskd service credentials."""

    url: str
    api_key: str | None
    username: str | None
    password: str | None

    def is_configured(self) -> bool:
        """Check if credentials are complete (URL + auth)."""
        has_url = bool(self.url and self.url.strip())
        has_api_key = bool(self.api_key and self.api_key.strip())
        has_user_pass = bool(
            self.username
            and self.username.strip()
            and self.password
            and self.password.strip()
        )
        return has_url and (has_api_key or has_user_pass)


@dataclass
class DeezerCredentials:
    """Deezer OAuth credentials."""

    app_id: str
    secret: str
    redirect_uri: str

    def is_configured(self) -> bool:
        """Check if credentials are complete."""
        return bool(
            self.app_id and self.app_id.strip() and self.secret and self.secret.strip()
        )


class CredentialsService:
    """Service for fetching credentials from DB with env fallback.

    Hey future me - this is backward compatible! If DB has no value,
    it falls back to environment variables. This lets users migrate
    gradually from .env to Settings UI.

    The fallback_settings parameter is optional. If not provided,
    only DB values are used (strict mode for new deployments).
    """

    def __init__(
        self,
        session: AsyncSession,
        fallback_settings: Settings | None = None,
    ) -> None:
        """Initialize credentials service.

        Args:
            session: Database session for app_settings queries
            fallback_settings: Optional Settings object for .env fallback
        """
        self._settings_service = AppSettingsService(session)
        self._fallback = fallback_settings

    async def get_spotify_credentials(self) -> SpotifyCredentials:
        """Get Spotify OAuth credentials.

        Checks DB first, falls back to env vars if DB is empty.

        Returns:
            SpotifyCredentials with client_id, client_secret, redirect_uri
        """
        # Try DB first
        client_id = await self._settings_service.get_string(
            "spotify.client_id", default=""
        )
        client_secret = await self._settings_service.get_string(
            "spotify.client_secret", default=""
        )
        redirect_uri = await self._settings_service.get_string(
            "spotify.redirect_uri",
            default="http://localhost:8000/api/auth/callback",
        )

        # Fallback to env if DB is empty
        if not client_id and self._fallback:
            client_id = self._fallback.spotify.client_id
            logger.debug("Spotify client_id loaded from env (DB empty)")
        if not client_secret and self._fallback:
            client_secret = self._fallback.spotify.client_secret
            logger.debug("Spotify client_secret loaded from env (DB empty)")
        if redirect_uri == "http://localhost:8000/api/auth/callback" and self._fallback:
            # Only override if still at default
            env_redirect = self._fallback.spotify.redirect_uri
            if env_redirect and env_redirect != redirect_uri:
                redirect_uri = env_redirect
                logger.debug("Spotify redirect_uri loaded from env (DB at default)")

        return SpotifyCredentials(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

    async def get_slskd_credentials(self) -> SlskdCredentials:
        """Get slskd service credentials.

        Checks DB first, falls back to env vars if DB is empty.

        Returns:
            SlskdCredentials with url, api_key, username, password
        """
        # Try DB first
        url = await self._settings_service.get_string(
            "slskd.url", default="http://localhost:5030"
        )
        api_key = await self._settings_service.get_string("slskd.api_key", default="")
        username = await self._settings_service.get_string("slskd.username", default="")
        password = await self._settings_service.get_string("slskd.password", default="")

        # Fallback to env if DB is empty
        if url == "http://localhost:5030" and self._fallback:
            env_url = self._fallback.slskd.url
            if env_url and env_url != url:
                url = env_url
                logger.debug("slskd url loaded from env (DB at default)")
        if not api_key and self._fallback:
            api_key = self._fallback.slskd.api_key or ""
            if api_key:
                logger.debug("slskd api_key loaded from env (DB empty)")
        if not username and self._fallback:
            username = self._fallback.slskd.username or ""
            if username:
                logger.debug("slskd username loaded from env (DB empty)")
        if not password and self._fallback:
            password = self._fallback.slskd.password or ""
            if password:
                logger.debug("slskd password loaded from env (DB empty)")

        return SlskdCredentials(
            url=url,
            api_key=api_key if api_key else None,
            username=username if username else None,
            password=password if password else None,
        )

    async def get_deezer_credentials(self) -> DeezerCredentials:
        """Get Deezer OAuth credentials.

        Deezer credentials are DB-only (no env fallback).

        Returns:
            DeezerCredentials with app_id, secret, redirect_uri
        """
        app_id = await self._settings_service.get_string("deezer.app_id", default="")
        secret = await self._settings_service.get_string("deezer.secret", default="")
        redirect_uri = await self._settings_service.get_string(
            "deezer.redirect_uri",
            default="http://localhost:8000/api/auth/deezer/callback",
        )

        return DeezerCredentials(
            app_id=app_id,
            secret=secret,
            redirect_uri=redirect_uri,
        )

    async def save_spotify_credentials(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        """Save Spotify credentials to database.

        Args:
            client_id: Spotify OAuth Client ID
            client_secret: Spotify OAuth Client Secret
            redirect_uri: OAuth redirect URI
        """
        await self._settings_service.set("spotify.client_id", client_id)
        await self._settings_service.set("spotify.client_secret", client_secret)
        await self._settings_service.set("spotify.redirect_uri", redirect_uri)
        logger.info("Spotify credentials saved to database")

    async def save_slskd_credentials(
        self,
        url: str,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Save slskd credentials to database.

        Args:
            url: slskd service URL
            api_key: API key (preferred auth)
            username: Username (fallback auth)
            password: Password (fallback auth)
        """
        await self._settings_service.set("slskd.url", url)
        await self._settings_service.set("slskd.api_key", api_key or "")
        await self._settings_service.set("slskd.username", username or "")
        await self._settings_service.set("slskd.password", password or "")
        logger.info("slskd credentials saved to database")

    async def save_deezer_credentials(
        self,
        app_id: str,
        secret: str,
        redirect_uri: str,
    ) -> None:
        """Save Deezer credentials to database.

        Args:
            app_id: Deezer OAuth App ID
            secret: Deezer OAuth Secret
            redirect_uri: OAuth redirect URI
        """
        await self._settings_service.set("deezer.app_id", app_id)
        await self._settings_service.set("deezer.secret", secret)
        await self._settings_service.set("deezer.redirect_uri", redirect_uri)
        logger.info("Deezer credentials saved to database")
