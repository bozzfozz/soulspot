# AI-Model: Copilot
"""Service for syncing and managing followed artists from Spotify."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Artist
from soulspot.domain.value_objects import ArtistId, SpotifyUri
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import ArtistRepository

logger = logging.getLogger(__name__)


class FollowedArtistsService:
    """Service for syncing followed artists from Spotify.

    Hey future me - this service handles the "get all my followed artists from Spotify"
    feature! It fetches artists from Spotify's /me/following endpoint (cursor-based pagination),
    creates/updates Artist entities in our DB, and returns them for UI display. The user can then
    select which artists to add to watchlists for auto-downloading new releases.

    GOTCHA: Spotify uses cursor-based pagination (after param) NOT offset! Must follow next cursor
    until cursors.after is null. Can take multiple API calls for users with 100+ followed artists.
    GOTCHA: Requires user-follow-read OAuth scope - we added this to SpotifyClient.get_authorization_url
    """

    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient,
    ) -> None:
        """Initialize followed artists service.

        Args:
            session: Database session for Artist repository
            spotify_client: Spotify client for API calls
        """
        self.artist_repo = ArtistRepository(session)
        self.spotify_client = spotify_client

    # Hey future me, this is the MAIN method! It fetches ALL followed artists from Spotify (handling
    # pagination automatically) and creates/updates Artist entities in DB. Returns list of Artists
    # for UI to display. The sync operation is idempotent - safe to call multiple times. We use
    # spotify_uri as the unique key to prevent duplicates. If artist already exists, we update the
    # name (in case they changed it on Spotify). Each API call gets max 50 artists, so 200 followed
    # artists = 4 API calls. Progress is logged. Commits are caller's responsibility (service doesn't
    # commit - separation of concerns). If Spotify API fails mid-pagination, partial results are returned.
    async def sync_followed_artists(
        self, access_token: str
    ) -> tuple[list[Artist], dict[str, Any]]:
        """Fetch all followed artists from Spotify and sync to database.

        Args:
            access_token: Spotify OAuth access token with user-follow-read scope

        Returns:
            Tuple of (list of Artist entities, sync statistics dict)

        Raises:
            httpx.HTTPError: If Spotify API request fails
        """
        all_artists: list[Artist] = []
        after_cursor: str | None = None
        page = 1
        stats = {
            "total_fetched": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
        }

        # Listen, Spotify pagination loop! We keep fetching until cursors.after is null.
        # Each iteration gets up to 50 artists. The after_cursor is the last artist ID
        # from previous page - Spotify uses this instead of offset for efficiency.
        while True:
            try:
                response = await self.spotify_client.get_followed_artists(
                    access_token=access_token,
                    limit=50,
                    after=after_cursor,
                )

                artists_data = response.get("artists", {})
                items = artists_data.get("items", [])

                if not items:
                    logger.info("No more followed artists to fetch")
                    break

                logger.info(
                    f"Fetched page {page} with {len(items)} followed artists from Spotify"
                )

                # Process each artist from Spotify response
                for artist_data in items:
                    try:
                        artist, was_created = await self._process_artist_data(
                            artist_data
                        )
                        all_artists.append(artist)
                        stats["total_fetched"] += 1
                        if was_created:
                            stats["created"] += 1
                        else:
                            stats["updated"] += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to process artist {artist_data.get('name', 'unknown')}: {e}"
                        )
                        stats["errors"] += 1

                # Check for next page using cursor
                cursors = artists_data.get("cursors", {})
                after_cursor = cursors.get("after")

                if not after_cursor:
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

    # Yo future me, this processes a single artist from Spotify API response and creates/updates
    # the Artist entity in DB! We use spotify_uri as unique identifier (better than name since
    # artists can share names). If artist exists, we update the name, genres, image_url AND source.
    # Source is now CRITICAL for unified Music Manager:
    # - If artist exists with source='local', upgrade to source='hybrid' (local + Spotify)
    # - If artist doesn't exist, create with source='spotify' (Spotify followed only)
    # Spotify artist object has: id, name, uri, genres (list), images (list of artwork URLs in different sizes).
    # Genres are now persisted to DB as JSON text (migration dd18990ggh48 adds genres/tags columns).
    # Images array typically has 3 sizes: 640x640, 320x320, 160x160. We pick the medium one (index 1, ~320px)
    # for display in the followed artists UI. If no images exist, image_url stays None (indie artists often lack images).
    # Returns tuple (artist, was_created) so caller can track stats properly.
    async def _process_artist_data(
        self, artist_data: dict[str, Any]
    ) -> tuple[Artist, bool]:
        """Process a single artist from Spotify API response.

        Args:
            artist_data: Artist data from Spotify API

        Returns:
            Tuple of (Artist entity, was_created boolean)

        Raises:
            ValueError: If artist data is invalid (missing required fields)
        """
        from soulspot.domain.entities import ArtistSource

        spotify_id = artist_data.get("id")
        name = artist_data.get("name")
        genres = artist_data.get("genres", [])
        images = artist_data.get("images", [])

        if not spotify_id or not name:
            raise ValueError(f"Invalid artist data: missing id or name - {artist_data}")

        spotify_uri = SpotifyUri.from_string(f"spotify:artist:{spotify_id}")

        # Hey future me - extract image URL from Spotify images array! Spotify returns images sorted
        # by size (largest first). We pick medium size (usually index 1, ~320x320) for good balance
        # between quality and load time. If only one image exists (rare), use it. If no images, None.
        image_url = None
        if images:
            # Prefer medium-sized image (index 1), fallback to first available
            preferred_image = images[1] if len(images) > 1 else images[0]
            image_url = preferred_image.get("url")

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
                logger.debug(f"Updated artist: {name} (id: {spotify_id})")
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
        logger.info(f"Created new Spotify followed artist: {name} (id: {spotify_id}, source=spotify)")

        return new_artist, True  # Was created

    # Hey future me, this is a simple utility to get a preview of followed artists WITHOUT
    # syncing to DB! Useful for "show me who I follow on Spotify" without persisting data.
    # Just fetches first page (50 artists max). Returns raw Spotify data for quick display.
    # Use sync_followed_artists() if you actually want to store the artists in DB!
    async def preview_followed_artists(
        self, access_token: str, limit: int = 50
    ) -> dict[str, Any]:
        """Get a preview of followed artists without syncing to database.

        Args:
            access_token: Spotify OAuth access token
            limit: Max artists to fetch (1-50)

        Returns:
            Spotify API response with artist data
        """
        return await self.spotify_client.get_followed_artists(
            access_token=access_token,
            limit=min(limit, 50),
        )
