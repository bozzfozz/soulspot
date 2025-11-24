"""API module for SoulSpot."""

from soulspot.api.routers import auth, downloads, playlists, tracks

__all__ = ["auth", "downloads", "playlists", "tracks"]
