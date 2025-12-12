"""External integration client implementations."""

from soulspot.infrastructure.integrations.coverartarchive_client import (
    CoverArt,
    CoverArtArchiveClient,
    CoverArtRelease,
)
from soulspot.infrastructure.integrations.deezer_client import DeezerClient
from soulspot.infrastructure.integrations.deezer_oauth_client import DeezerOAuthClient
from soulspot.infrastructure.integrations.lastfm_client import LastfmClient
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
from soulspot.infrastructure.integrations.slskd_client import SlskdClient
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.integrations.tidal_client import TidalClient

__all__ = [
    "CoverArt",
    "CoverArtArchiveClient",
    "CoverArtRelease",
    "DeezerClient",
    "DeezerOAuthClient",
    "SlskdClient",
    "SpotifyClient",
    "TidalClient",
    "MusicBrainzClient",
    "LastfmClient",
]
