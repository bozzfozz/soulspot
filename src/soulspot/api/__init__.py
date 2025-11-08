"""API module for SoulSpot Bridge."""

from soulspot.api.routers import auth, downloads, playlists, tracks

__all__ = ["auth", "downloads", "playlists", "tracks"]
