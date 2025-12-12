"""
SoulSpot Plugin Infrastructure.

Hey future me – das ist der Haupteingang für alle Plugins!
Von hier aus importieren Application Services ihre Plugins.

Verwendung:
    from soulspot.infrastructure.plugins import (
        SpotifyPlugin,
        DeezerPlugin,
        TidalPlugin,
        PluginRegistry,
        get_plugin_registry,
    )

Architektur:
    Application Service
           ↓
    PluginRegistry.get(ServiceType.SPOTIFY)
           ↓
    SpotifyPlugin (implements IMusicServicePlugin)
           ↓
    SpotifyClient (HTTP calls)
           ↓
    Spotify API

Alle Plugins geben DTOs zurück, nie raw JSON!
"""

from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
from soulspot.infrastructure.plugins.registry import (
    PluginRegistry,
    get_plugin_registry,
)
from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
from soulspot.infrastructure.plugins.tidal_plugin import TidalPlugin

__all__ = [
    # Plugins
    "SpotifyPlugin",
    "DeezerPlugin",
    "TidalPlugin",
    # Registry
    "PluginRegistry",
    "get_plugin_registry",
]
