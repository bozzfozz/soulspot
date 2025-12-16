"""External integration client implementations."""

from soulspot.infrastructure.integrations.coverartarchive_client import (
    CoverArt,
    CoverArtArchiveClient,
    CoverArtRelease,
)
from soulspot.infrastructure.integrations.deezer_client import (
    DeezerClient,
    DeezerOAuthConfig,
)
# NOTE (Dec 2025): DeezerOAuthClient REMOVED - was a stub, DeezerClient has OAuth methods!
from soulspot.infrastructure.integrations.http_pool import HttpClientPool
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
    "DeezerOAuthConfig",
    "HttpClientPool",
    "SlskdClient",
    "SpotifyClient",
    "TidalClient",
    "MusicBrainzClient",
    "LastfmClient",
]
