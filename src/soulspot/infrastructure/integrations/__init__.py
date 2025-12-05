"""External integration client implementations."""

from soulspot.infrastructure.integrations.deezer_client import DeezerClient
from soulspot.infrastructure.integrations.lastfm_client import LastfmClient
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
from soulspot.infrastructure.integrations.slskd_client import SlskdClient
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

__all__ = [
    "DeezerClient",
    "SlskdClient",
    "SpotifyClient",
    "MusicBrainzClient",
    "LastfmClient",
]
