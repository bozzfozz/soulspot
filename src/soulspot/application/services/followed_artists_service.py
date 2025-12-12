# AI-Model: Copilot
"""Service for syncing and managing followed artists from Spotify."""

import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Artist
from soulspot.domain.value_objects import ArtistId, SpotifyUri
from soulspot.infrastructure.persistence.repositories import ArtistRepository

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class FollowedArtistsService:
    """Service for syncing followed artists from Spotify.

    Hey future me - REFACTORED to use SpotifyPlugin instead of raw SpotifyClient!
    The plugin handles token management internally, no more access_token parameter juggling.
    Methods now don't need access_token - the plugin manages that.

    This service handles the "get all my followed artists from Spotify" feature!
    It fetches artists from Spotify's /me/following endpoint (cursor-based pagination),
    creates/updates Artist entities in our DB, and returns them for UI display.
    The user can then select which artists to add to watchlists for auto-downloading.

    GOTCHA: Spotify uses cursor-based pagination (after param) NOT offset! Must follow
    next cursor until cursors.after is null. Plugin handles this with PaginatedResponse.
    """

    def __init__(
        self,
        session: AsyncSession,
        spotify_plugin: "SpotifyPlugin",
    ) -> None:
        """Initialize followed artists service.

        Hey future me - refactored to use SpotifyPlugin!
        The plugin handles token management internally, no more access_token juggling.

        Args:
            session: Database session for Artist repository
            spotify_plugin: SpotifyPlugin for API calls (handles auth internally)
        """
        self.session = session
        self.artist_repo = ArtistRepository(session)
        self.spotify_plugin = spotify_plugin

    # Hey future me, this is the MAIN method! REFACTORED to use SpotifyPlugin!
    # It fetches ALL followed artists from Spotify (handling pagination automatically via
    # PaginatedResponse) and creates/updates Artist entities in DB. Returns list of Artists
    # for UI to display. The sync operation is idempotent - safe to call multiple times.
    # The plugin handles auth internally - no more access_token parameter needed!
    # Progress is logged. Commits are caller's responsibility (service doesn't commit).
    async def sync_followed_artists(
        self,
    ) -> tuple[list[Artist], dict[str, int]]:
        """Fetch all followed artists from Spotify and sync to database.

        Hey future me - refactored to use SpotifyPlugin!
        No more access_token parameter - plugin handles auth internally.

        Returns:
            Tuple of (list of Artist entities, sync statistics dict)

        Raises:
            PluginError: If Spotify API request fails
        """
        from soulspot.domain.dtos import ArtistDTO

        all_artists: list[Artist] = []
        after_cursor: str | None = None
        page = 1
        stats = {
            "total_fetched": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
        }

        # Listen, Spotify pagination loop using SpotifyPlugin!
        # Plugin returns PaginatedResponse with items (ArtistDTOs) and pagination info.
        # We keep fetching until there are no more items.
        while True:
            try:
                # SpotifyPlugin.get_followed_artists returns PaginatedResponse[ArtistDTO]
                response = await self.spotify_plugin.get_followed_artists(
                    limit=50,
                    after=after_cursor,
                )

                items = response.items
                if not items:
                    logger.info("No more followed artists to fetch")
                    break

                logger.info(
                    f"Fetched page {page} with {len(items)} followed artists from Spotify"
                )

                # Process each artist from plugin response (already converted to ArtistDTO!)
                for artist_dto in items:
                    try:
                        artist, was_created = await self._process_artist_dto(
                            artist_dto
                        )
                        all_artists.append(artist)
                        stats["total_fetched"] += 1
                        if was_created:
                            stats["created"] += 1
                        else:
                            stats["updated"] += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to process artist {artist_dto.name}: {e}"
                        )
                        stats["errors"] += 1

                # Check for next page - get last artist's spotify_id as cursor
                if response.next_offset and items:
                    after_cursor = items[-1].spotify_id
                else:
                    logger.info("Reached end of followed artists (no more pages)")
                    break

                page += 1

            except Exception as e:
                logger.error(f"Error fetching followed artists page {page}: {e}")
                # Return partial results if pagination fails mid-sync
                break

        logger.info(
            f"Followed artists sync complete: {stats['total_fetched']} fetched, "
            f"{stats['created']} created, {stats['updated']} updated, {stats['errors']} errors"
        )

        return all_artists, stats

    # Yo future me, REFACTORED to process ArtistDTO from SpotifyPlugin!
    # This processes a single artist DTO and creates/updates the Artist entity in DB.
    # We use spotify_uri as unique identifier (better than name since artists can share names).
    # If artist exists, we update the name, genres, image_url AND source.
    # Source is now CRITICAL for unified Music Manager:
    # - If artist exists with source='local', upgrade to source='hybrid' (local + Spotify)
    # - If artist doesn't exist, create with source='spotify' (Spotify followed only)
    # The DTO already has: name, spotify_id, spotify_uri, image_url, genres (converted by plugin).
    # Returns tuple (artist, was_created) so caller can track stats properly.
    async def _process_artist_dto(
        self, artist_dto: "ArtistDTO"
    ) -> tuple[Artist, bool]:
        """Process a single artist from SpotifyPlugin (ArtistDTO).

        Hey future me - refactored to work with ArtistDTO instead of raw JSON!
        The plugin already converted Spotify JSON to clean DTO format.

        Args:
            artist_dto: ArtistDTO from SpotifyPlugin

        Returns:
            Tuple of (Artist entity, was_created boolean)

        Raises:
            ValueError: If artist data is invalid (missing required fields)
        """
        from soulspot.domain.dtos import ArtistDTO
        from soulspot.domain.entities import ArtistSource

        if not artist_dto.spotify_id or not artist_dto.name:
            raise ValueError(f"Invalid artist DTO: missing spotify_id or name")

        spotify_uri = SpotifyUri.from_string(
            artist_dto.spotify_uri or f"spotify:artist:{artist_dto.spotify_id}"
        )

        # Hey future me - ArtistDTO already has image_url extracted by plugin!
        # Plugin picked the medium-sized image (~320px) for us.
        image_url = artist_dto.image_url
        name = artist_dto.name
        genres = artist_dto.genres or []

        # Hey future me - DEDUPLICATION LOGIC for unified Music Manager!
        # We check TWO ways to find existing artists:
        # 1. By spotify_uri (most reliable - exact match)
        # 2. By name (fallback for local artists that don't have spotify_uri yet)
        # This prevents duplicate artists when:
        # - Local file scan found "Pink Floyd" (no spotify_uri)
        # - Later, user follows "Pink Floyd" on Spotify
        # → We MERGE them instead of creating duplicate!
        existing_artist = await self.artist_repo.get_by_spotify_uri(spotify_uri)

        # Fallback: Check by name if spotify_uri didn't match (case-insensitive)
        if not existing_artist:
            existing_artist = await self.artist_repo.get_by_name(name)
            if existing_artist:
                logger.info(
                    f"Found existing artist by name match: '{name}' "
                    f"(local artist without spotify_uri, now merging)"
                )

        if existing_artist:
            # Update existing artist (name, genres, image_url, source, spotify_uri might have changed)
            needs_update = False

            # Always set spotify_uri if it's missing (local artist matched by name)
            if not existing_artist.spotify_uri:
                existing_artist.spotify_uri = spotify_uri
                needs_update = True
                logger.info(
                    f"Added spotify_uri to local artist '{name}' (matched by name)"
                )

            if existing_artist.name != name:
                existing_artist.update_name(name)
                needs_update = True
            if existing_artist.genres != genres:
                existing_artist.genres = genres
                existing_artist.metadata_sources["genres"] = "spotify"
                needs_update = True
            if existing_artist.image_url != image_url:
                existing_artist.image_url = image_url
                existing_artist.metadata_sources["image_url"] = "spotify"
                needs_update = True

            # Hey future me - UPGRADE source if artist was local-only!
            # If artist was found in local file scan (source='local') and is now
            # followed on Spotify, upgrade to source='hybrid' (both local + Spotify).
            # This is the core of the unified Music Manager - merging both sources!
            if existing_artist.source == ArtistSource.LOCAL:
                existing_artist.source = ArtistSource.HYBRID
                needs_update = True
                logger.info(
                    f"Upgraded artist '{name}' from LOCAL to HYBRID (local + Spotify)"
                )

            if needs_update:
                await self.artist_repo.update(existing_artist)
                logger.debug(f"Updated artist: {name} (spotify_id: {artist_dto.spotify_id})")
            return existing_artist, False  # Not created, was updated

        # Create new artist entity with source='spotify' (followed artist, no local files yet)
        new_artist = Artist(
            id=ArtistId.generate(),
            name=name,
            source=ArtistSource.SPOTIFY,  # Spotify followed artist (no local files yet)
            spotify_uri=spotify_uri,
            image_url=image_url,
            genres=genres,  # Persisted to DB as JSON text
            metadata_sources={
                "name": "spotify",
                "genres": "spotify",
                "image_url": "spotify",
            },
        )

        await self.artist_repo.add(new_artist)
        logger.info(f"Created new Spotify followed artist: {name} (spotify_id: {artist_dto.spotify_id}, source=spotify)")

        return new_artist, True  # Was created

    async def sync_artist_albums(
        self, artist_id: str,
    ) -> dict[str, int]:
        """Sync albums for a Spotify artist into unified albums table.
        
        Hey future me - REFACTORED to use SpotifyPlugin!
        This syncs Spotify albums into soulspot_albums table (unified)!
        Unlike SpotifySyncService which uses separate spotify_albums table, this method
        puts albums directly into the unified music library so they appear alongside
        local albums. This is key for the Music Manager concept!
        
        No more access_token param - plugin handles auth internally.
        
        Args:
            artist_id: Our internal artist ID (not Spotify ID)
            
        Returns:
            Dict with sync stats (total, added, skipped)
        """
        from soulspot.domain.value_objects import AlbumId
        from soulspot.domain.entities import Album
        from soulspot.infrastructure.persistence.repositories import AlbumRepository
        
        stats = {"total": 0, "added": 0, "skipped": 0}
        
        # Get artist by ID
        artist = await self.artist_repo.get(artist_id)
        if not artist or not artist.spotify_uri:
            logger.warning(f"Artist {artist_id} not found or has no spotify_uri")
            return stats
        
        # Extract Spotify ID from spotify_uri (format: spotify:artist:xxx)
        spotify_artist_id = str(artist.spotify_uri).split(":")[-1]
        
        # Fetch albums from Spotify API using SpotifyPlugin (returns PaginatedResponse[AlbumDTO])
        try:
            response = await self.spotify_plugin.get_artist_albums(
                artist_id=spotify_artist_id,
                limit=50,
            )
            albums_dtos = response.items
        except Exception as e:
            logger.error(f"Failed to fetch albums for artist {artist.name}: {e}")
            return stats
        
        album_repo = AlbumRepository(self.session)
        
        # Process each album (now AlbumDTO instead of raw dict!)
        for album_dto in albums_dtos:
            stats["total"] += 1
            
            spotify_uri = SpotifyUri.from_string(
                album_dto.spotify_uri or f"spotify:album:{album_dto.spotify_id}"
            )
            
            # Check if album already exists
            existing_album = await album_repo.get_by_spotify_uri(spotify_uri)
            if existing_album:
                stats["skipped"] += 1
                continue
            
            # Create new album in unified table (using DTO fields!)
            new_album = Album(
                id=AlbumId.generate(),
                title=album_dto.title,
                artist_id=artist.id,
                release_year=album_dto.release_year,
                spotify_uri=spotify_uri,
                artwork_url=album_dto.artwork_url,
            )
            
            await album_repo.add(new_album)
            stats["added"] += 1
            logger.debug(f"Added Spotify album: {album_dto.title} ({album_dto.release_year})")
        
        logger.info(
            f"Synced {stats['added']} new albums for {artist.name} "
            f"({stats['skipped']} already existed)"
        )
        return stats

    # Hey future me, REFACTORED to use SpotifyPlugin!
    # This is a simple utility to get a preview of followed artists WITHOUT syncing to DB!
    # Useful for "show me who I follow on Spotify" without persisting data.
    # Returns list of ArtistDTOs for quick display.
    async def preview_followed_artists(
        self, limit: int = 50
    ) -> list["ArtistDTO"]:
        """Get a preview of followed artists without syncing to database.

        Hey future me - refactored to use SpotifyPlugin!
        No more access_token param - plugin handles auth internally.
        Returns ArtistDTOs instead of raw Spotify JSON.

        Args:
            limit: Max artists to fetch (1-50)

        Returns:
            List of ArtistDTOs from Spotify
        """
        from soulspot.domain.dtos import ArtistDTO

        response = await self.spotify_plugin.get_followed_artists(
            limit=min(limit, 50),
        )
        return response.items
