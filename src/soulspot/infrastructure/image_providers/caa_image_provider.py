"""⚠️ DEPRECATED - DO NOT USE! ⚠️

This file is DEPRECATED. The CoverArtArchive feature is not actively used.

This file will be removed in a future release.
DELETE: src/soulspot/infrastructure/image_providers/caa_image_provider.py

NOTE: Unlike SpotifyImageProvider and DeezerImageProvider, there is NO 
replacement in infrastructure/providers/. If CAA support is needed in the
future, it should be re-implemented there.

-------------------------------------------------------------------------------
Original docstring (kept for reference):
-------------------------------------------------------------------------------

CoverArtArchive Image Provider - IImageProvider for MusicBrainz/CAA.

Hey future me - dieser Provider nutzt MusicBrainz + CoverArtArchive für Album-Artwork!

WICHTIG:
- MusicBrainz/CAA ist KOSTENLOS und braucht KEINE Auth!
- CAA hat hochwertige Cover (bis 1200x1200)
- Aber: Nur für Alben, NICHT für Artists!
- Perfekt als letzter Fallback für Album-Cover

FLOW für Albums:
    ImageProviderRegistry
        │
        └─► CAAImageProvider.search_album_image("Abbey Road", "The Beatles")
                │
                ├─► MusicBrainzClient.search_release_group("Abbey Road", "The Beatles")
                │       └─► Release Group MBID
                │
                └─► CoverArtArchiveClient.get_release_group_front_cover(mbid)
                        └─► Image URL

Für Artists:
- CAA hat KEINE Artist-Bilder!
- search_artist_image() gibt immer leeres Ergebnis zurück
- Nutze Spotify/Deezer für Artist-Bilder

Priorität: 3 (niedrigste) - nur für Alben, als letzter Fallback
"""

from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING, Any

from soulspot.domain.ports.image_provider import (
    IImageProvider,
    ImageQuality,
    ImageResult,
    ImageSearchResult,
    ProviderName,
)

if TYPE_CHECKING:
    from soulspot.infrastructure.integrations.coverartarchive_client import (
        CoverArtArchiveClient,
    )
    from soulspot.infrastructure.integrations.musicbrainz_client import (
        MusicBrainzClient,
    )

logger = logging.getLogger(__name__)

# Emit deprecation warning on import
warnings.warn(
    "CoverArtArchiveImageProvider is DEPRECATED. "
    "This feature is not actively used. The entire image_providers package will be removed.",
    DeprecationWarning,
    stacklevel=2,
)


class CoverArtArchiveImageProvider(IImageProvider):
    """⚠️ DEPRECATED - This feature is not actively used!
    
    Hey future me - dieser Provider:
    4. Keine Auth nötig, immer verfügbar
    
    Priorität: 3 - nur als letzter Fallback für Album-Cover
    """
    
    def __init__(
        self,
        musicbrainz_client: MusicBrainzClient,
        caa_client: CoverArtArchiveClient,
    ) -> None:
        """Initialize with clients.
        
        Args:
            musicbrainz_client: For searching release groups
            caa_client: For fetching artwork
        """
        self._mb_client = musicbrainz_client
        self._caa_client = caa_client
        
    # === Properties ===
    
    @property
    def provider_name(self) -> ProviderName:
        """CoverArtArchive provider name."""
        return "coverartarchive"
    
    @property
    def requires_auth(self) -> bool:
        """MusicBrainz and CAA are free, no auth required."""
        return False
    
    # === Availability ===
    
    async def is_available(self) -> bool:
        """MusicBrainz and CAA are always available (public APIs).
        
        Hey future me - wir könnten Health-Checks machen, aber das ist zu langsam.
        Beide APIs sind sehr stabil und haben gute Uptime.
        """
        return True
    
    # === Direct Lookup Methods (by ID) ===
    
    async def get_artist_image(
        self,
        artist_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """CoverArtArchive does NOT have artist images!
        
        Hey future me - CAA ist NUR für Album-Cover.
        Für Artist-Bilder nutze Spotify oder Deezer.
        
        Returns:
            Always None - CAA has no artist images
        """
        logger.debug(
            "CoverArtArchive does not provide artist images. "
            "Use Spotify/Deezer for artist_id=%s",
            artist_id
        )
        return None
    
    async def get_album_image(
        self,
        album_id: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageResult | None:
        """Get album image by MusicBrainz Release Group MBID.
        
        Args:
            album_id: MusicBrainz Release Group ID (MBID)
            quality: Desired image quality
            
        Returns:
            ImageResult with URL or None if not found
        """
        try:
            # CAA uses Release Group MBIDs
            url = await self._caa_client.get_release_group_front_cover(album_id)
            
            if not url:
                logger.debug("No CAA artwork for release-group %s", album_id)
                return None
            
            # Thumbnail sizes: 250, 500, 1200
            # Wir versuchen die passende Größe zu bekommen
            thumbnail_url = await self._get_thumbnail_url(album_id, quality)
            final_url = thumbnail_url or url
            
            return ImageResult(
                url=final_url,
                provider="coverartarchive",
                quality=quality,
                entity_id=album_id,
            )
            
        except Exception as e:
            logger.warning(
                "Failed to get CAA album image for %s: %s",
                album_id, e
            )
            return None
    
    async def _get_thumbnail_url(
        self, 
        release_group_mbid: str, 
        quality: ImageQuality,
    ) -> str | None:
        """Get thumbnail URL for quality preference.
        
        Args:
            release_group_mbid: MusicBrainz Release Group ID
            quality: Desired quality
            
        Returns:
            Thumbnail URL or None
        """
        # Map quality to CAA thumbnail size
        size_map = {
            ImageQuality.THUMBNAIL: 250,
            ImageQuality.SMALL: 250,
            ImageQuality.MEDIUM: 500,
            ImageQuality.LARGE: 1200,
            ImageQuality.ORIGINAL: 1200,
        }
        size = size_map.get(quality, 500)
        
        try:
            # Wir brauchen eine Release ID für Thumbnails, nicht Release Group
            # Das ist kompliziert, daher nutzen wir erstmal die standard URL
            # TODO: Implement proper thumbnail lookup via release group → release
            return None
        except Exception:
            return None
    
    # === Search Methods (by name) ===
    
    async def search_artist_image(
        self,
        artist_name: str,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageSearchResult:
        """CoverArtArchive does NOT have artist images!
        
        Hey future me - CAA ist NUR für Album-Cover.
        Diese Methode gibt immer leeres Ergebnis zurück.
        
        Returns:
            Empty ImageSearchResult - CAA has no artist images
        """
        logger.debug(
            "CoverArtArchive does not provide artist images. "
            "Skipping search for: %s",
            artist_name
        )
        return ImageSearchResult(matches=[], best_match=None)
    
    async def search_album_image(
        self,
        album_title: str,
        artist_name: str | None = None,
        quality: ImageQuality = ImageQuality.MEDIUM,
    ) -> ImageSearchResult:
        """Search for album image via MusicBrainz + CoverArtArchive.
        
        Hey future me - der Killer-Usecase für CAA!
        1. Suche MusicBrainz nach Release Group
        2. Hole Cover von CAA für gefundene Release Groups
        
        Args:
            album_title: Album title to search for
            artist_name: Optional artist name for better matching
            quality: Desired image quality
            
        Returns:
            ImageSearchResult with best_match and alternatives
        """
        try:
            # 1. Search MusicBrainz for release groups
            release_groups = await self._mb_client.search_release_group(
                artist=artist_name,
                album=album_title,
                limit=5,
            )
            
            if not release_groups:
                logger.debug(
                    "No MusicBrainz results for album: %s (artist: %s)",
                    album_title, artist_name
                )
                return ImageSearchResult(matches=[], best_match=None)
            
            # 2. Try to get cover art for each release group
            matches: list[ImageResult] = []
            
            for rg in release_groups:
                rg_mbid = rg.get("id")
                if not rg_mbid:
                    continue
                
                # Get cover URL from CAA
                url = await self._caa_client.get_release_group_front_cover(rg_mbid)
                
                if url:
                    # Build entity name for logging/debugging
                    rg_title = rg.get("title", album_title)
                    rg_artist = self._extract_artist_credit(rg)
                    
                    matches.append(ImageResult(
                        url=url,
                        provider="coverartarchive",
                        quality=quality,
                        entity_name=rg_title,
                        entity_id=rg_mbid,
                    ))
                    
                    logger.debug(
                        "Found CAA cover for %s - %s (mbid=%s)",
                        rg_artist, rg_title, rg_mbid
                    )
            
            if not matches:
                logger.debug(
                    "No CAA artwork found for album: %s (artist: %s)",
                    album_title, artist_name
                )
                return ImageSearchResult(matches=[], best_match=None)
            
            return ImageSearchResult(
                matches=matches,
                best_match=matches[0],
            )
            
        except Exception as e:
            logger.warning(
                "Failed to search CAA album image for %s: %s",
                album_title, e
            )
            return ImageSearchResult(matches=[], best_match=None)
    
    def _extract_artist_credit(self, release_group: dict[str, Any]) -> str:
        """Extract artist name from release group data.
        
        MusicBrainz artist-credit is a complex structure, we just want the name.
        """
        try:
            artist_credit = release_group.get("artist-credit", [])
            if artist_credit and isinstance(artist_credit, list):
                first_credit = artist_credit[0]
                if isinstance(first_credit, dict):
                    artist = first_credit.get("artist", {})
                    return artist.get("name", "Unknown Artist")
            return "Unknown Artist"
        except Exception:
            return "Unknown Artist"
