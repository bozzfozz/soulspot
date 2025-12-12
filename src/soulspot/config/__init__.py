"""Configuration module for SoulSpot."""

from .settings import Settings, SpotifySettings, get_settings

# Alias for backwards compatibility
SpotifyConfig = SpotifySettings

__all__ = ["Settings", "SpotifySettings", "SpotifyConfig", "get_settings"]
