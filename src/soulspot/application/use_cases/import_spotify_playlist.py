"""Import Spotify playlist use case."""

from dataclasses import dataclass
from datetime import UTC, datetime

from soulspot.application.use_cases import UseCase
from soulspot.domain.entities import Album, Artist, Playlist, PlaylistSource, Track
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    IPlaylistRepository,
    ISpotifyClient,
    ITrackRepository,
)
from soulspot.domain.value_objects import (
    AlbumId,
    ArtistId,
    PlaylistId,
    SpotifyUri,
    TrackId,
)


@dataclass
class ImportSpotifyPlaylistRequest:
    """Request to import a Spotify playlist."""

    playlist_id: str
    access_token: str
    fetch_all_tracks: bool = True


@dataclass
class ImportSpotifyPlaylistResponse:
    """Response from importing a Spotify playlist."""

    playlist: Playlist
    tracks_imported: int
    tracks_failed: int
    errors: list[str]


class ImportSpotifyPlaylistUseCase(
    UseCase[ImportSpotifyPlaylistRequest, ImportSpotifyPlaylistResponse]
):
    """Use case for importing a Spotify playlist into the system.

    This use case:
    1. Fetches playlist metadata from Spotify
    2. Creates or updates the playlist entity
    3. Fetches all tracks in the playlist
    4. Creates or updates track entities
    5. Associates tracks with the playlist
    """

    def __init__(
        self,
        spotify_client: ISpotifyClient,
        playlist_repository: IPlaylistRepository,
        track_repository: ITrackRepository,
        artist_repository: IArtistRepository,
        album_repository: IAlbumRepository, # Added album_repository
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            spotify_client: Client for Spotify API operations
            playlist_repository: Repository for playlist persistence
            track_repository: Repository for track persistence
            artist_repository: Repository for artist persistence
            album_repository: Repository for album persistence # Added album_repository docstring
        """
        self._spotify_client = spotify_client
        self._playlist_repository = playlist_repository
        self._track_repository = track_repository
        self._artist_repository = artist_repository
        self._album_repository = album_repository # Added album_repository initialization

    # Hey future me, this helper extracts year from Spotify release_date! Spotify returns dates
    # in different formats: "2023-11-26" (full date), "2023-11" (year-month), or "2023" (year only).
    # We only care about the year, so we split on "-" and take first part. Returns None if invalid.
    @staticmethod
    def _extract_year(release_date: str | None) -> int | None:
        """Extract year from Spotify release date string.
        
        Args:
            release_date: Date string from Spotify (e.g., "2023-11-26", "2023-11", "2023")
            
        Returns:
            Year as integer, or None if invalid
        """
        if not release_date:
            return None
        try:
            return int(release_date.split("-")[0])
        except (ValueError, IndexError):
            return None

    # Hey future me: Spotify playlist import - the entry point for getting music into the system
    # WHY fetch_all_tracks? Sometimes you just want playlist metadata without pulling 200 tracks
    # GOTCHA: This creates OR UPDATES tracks - if the track exists by Spotify URI, we update it
    # This is idempotent - running it twice on same playlist won't create duplicates
    async def execute(
        self, request: ImportSpotifyPlaylistRequest
    ) -> ImportSpotifyPlaylistResponse:
        """Execute the import playlist use case.

        Args:
            request: Request containing playlist ID and access token

        Returns:
            Response with imported playlist and statistics
        """
        errors: list[str] = []
        tracks_imported = 0
        tracks_failed = 0

        # 1. Fetch playlist metadata from Spotify
        try:
            spotify_playlist = await self._spotify_client.get_playlist(
                request.playlist_id,
                request.access_token,
            )
        except Exception as e:
            raise ValueError(f"Failed to fetch playlist from Spotify: {e}") from e

        # 2. Create or update playlist entity
        playlist_id = PlaylistId.generate()
        playlist = Playlist(
            id=playlist_id,
            name=spotify_playlist["name"],
            description=spotify_playlist.get("description"),
            source=PlaylistSource.SPOTIFY,
            spotify_uri=SpotifyUri(f"spotify:playlist:{request.playlist_id}"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Check if playlist already exists by Spotify URI
        existing_playlist = await self._playlist_repository.get_by_spotify_uri(
            playlist.spotify_uri
        )
        if existing_playlist:
            # Update existing playlist
            existing_playlist.name = playlist.name
            existing_playlist.description = playlist.description
            existing_playlist.updated_at = datetime.now(UTC)
            await self._playlist_repository.update(existing_playlist)
            playlist = existing_playlist
        else:
            # Add new playlist
            await self._playlist_repository.add(playlist)

    # Hey future me, this helper creates an Artist entity from Spotify API artist data!
    # Extracted to avoid code duplication between single and batch artist fetching.
    # Handles image URL extraction (prefer medium size ~320x320) and genres.
    # Returns a fully populated Artist entity ready to be added to the repository.
    def _create_artist_from_data(self, artist_data: dict) -> Artist:
        """Create Artist entity from Spotify artist data.
        
        Args:
            artist_data: Full artist object from Spotify API
            
        Returns:
            Artist entity with all metadata
        """
        artist_id = artist_data["id"]
        artist_name = artist_data["name"]
        artist_spotify_uri = SpotifyUri(f"spotify:artist:{artist_id}")

        # Extract image URL (prefer medium size ~320x320)
        images = artist_data.get("images", [])
        image_url = None
        if images:
            preferred_image = images[1] if len(images) > 1 else images[0]
            image_url = preferred_image.get("url")

        # Extract genres
        genres = artist_data.get("genres", [])

        return Artist(
            id=ArtistId.generate(),
            name=artist_name,
            spotify_uri=artist_spotify_uri,
            image_url=image_url,
            genres=genres,
            metadata_sources={
                "name": "spotify",
                "image_url": "spotify" if image_url else None,
                "genres": "spotify" if genres else None,
            },
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    # Yo future me, this is THE PERFORMANCE BOOSTER! Instead of fetching artists one-by-one
    # in the track loop (N API calls), we collect all unique artist IDs first, check which
    # already exist in DB, then batch-fetch the missing ones (N/50 API calls). For a playlist
    # with 100 unique artists, this reduces API calls from 100 to 2! The artists_map returned
    # maps artist_id -> Artist entity so the track loop can just look them up. IMPORTANT: We
    # handle errors gracefully - if a batch fails, we log it but continue with other batches.
    # This prevents one bad artist from killing the entire import!
    async def _fetch_and_create_artists_batch(
        self, artist_ids: list[str], access_token: str, errors: list[str]
    ) -> dict[str, Artist]:
        """Fetch and create multiple artists in batches of 50.
        
        Args:
            artist_ids: List of Spotify artist IDs to fetch
            access_token: Spotify OAuth token
            errors: List to append errors to
            
        Returns:
            Dict mapping artist_id to Artist entity
        """
        artists_map: dict[str, Artist] = {}

        # Step 1: Check which artists already exist in DB (by Spotify URI)
        for artist_id in artist_ids:
            spotify_uri = SpotifyUri(f"spotify:artist:{artist_id}")
            existing = await self._artist_repository.get_by_spotify_uri(spotify_uri)
            if existing:
                artists_map[artist_id] = existing

        # Step 2: Get IDs of artists we need to fetch from Spotify
        missing_ids = [aid for aid in artist_ids if aid not in artists_map]

        if not missing_ids:
            return artists_map  # All artists already in DB!

        # Step 3: Fetch missing artists in batches of 50
        for i in range(0, len(missing_ids), 50):
            batch = missing_ids[i : i + 50]
            try:
                artists_data = await self._spotify_client.get_several_artists(
                    batch, access_token
                )

                # Create and save artist entities
                for artist_data in artists_data:
                    artist = self._create_artist_from_data(artist_data)
                    await self._artist_repository.add(artist)
                    artists_map[artist_data["id"]] = artist

            except Exception as e:
                # Log error but continue with other batches
                errors.append(f"Failed to fetch artist batch: {e}")

        return artists_map

    # 3. Process tracks if requested
        if request.fetch_all_tracks:
            track_items = spotify_playlist["tracks"]["items"]

            # PERFORMANCE OPTIMIZATION: Batch fetch all artists first!
            # Step 1: Collect all unique artist IDs from tracks
            unique_artist_ids: set[str] = set()
            for item in track_items:
                track_data = item.get("track")
                if track_data and track_data.get("artists"):
                    unique_artist_ids.add(track_data["artists"][0]["id"])

            # Step 2: Batch fetch and create all artists (10x faster!)
            artists_map = await self._fetch_and_create_artists_batch(
                list(unique_artist_ids), request.access_token, errors
            )

            # Step 3: Process tracks (artists already in DB!)
            for item in track_items:
                try:
                    track_data = item.get("track")
                    if not track_data:
                        tracks_failed += 1
                        errors.append("Skipped item with no track data")
                        continue

                    # Get artist from pre-fetched map (no API call!)
                    artist = None
                    if track_data.get("artists"):
                        artist_id = track_data["artists"][0]["id"]
                        artist = artists_map.get(artist_id)

                    # Fallback: create Unknown Artist if needed
                    if not artist:
                        artist_name = "Unknown Artist"
                        artist = await self._artist_repository.get_by_name(artist_name)
                        if not artist:
                            artist = Artist(
                                id=ArtistId.generate(),
                                name=artist_name,
                                created_at=datetime.now(UTC),
                                updated_at=datetime.now(UTC),
                            )
                            await self._artist_repository.add(artist)

                    # Get or create album (with artwork!)
                    album = None
                    album_id = None
                    if track_data.get("album"):
                        album_data = track_data["album"]
                        album_spotify_uri = SpotifyUri(album_data["uri"])

                        # Check if album exists
                        album = await self._album_repository.get_by_spotify_uri(
                            album_spotify_uri
                        )

                        if not album:
                            # Extract album cover (prefer medium size ~300x300)
                            images = album_data.get("images", [])
                            artwork_url = None
                            if images:
                                preferred_image = images[1] if len(images) > 1 else images[0]
                                artwork_url = preferred_image.get("url")

                            # Extract release year
                            release_year = self._extract_year(album_data.get("release_date"))

                            album = Album(
                                id=AlbumId.generate(),
                                title=album_data["name"],
                                artist_id=artist.id,
                                release_year=release_year,
                                spotify_uri=album_spotify_uri,
                                artwork_url=artwork_url,  # NEW: Store album cover!
                                created_at=datetime.now(UTC),
                                updated_at=datetime.now(UTC),
                            )
                            await self._album_repository.add(album)

                        album_id = album.id

                    # Create track entity
                    track_id = TrackId.generate()
                    track = Track(
                        id=track_id,
                        title=track_data["name"],
                        artist_id=artist.id,
                        album_id=album_id, # NEW: Associate track with album
                        duration_ms=track_data.get("duration_ms", 0),
                        spotify_uri=SpotifyUri(track_data["uri"]),
                        isrc=track_data.get("external_ids", {}).get("isrc"),
                        track_number=track_data.get("track_number"),
                        disc_number=track_data.get("disc_number", 1),
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )

                    # Check if track already exists by Spotify URI
                    existing_track = await self._track_repository.get_by_spotify_uri(
                        track.spotify_uri
                    )
                    if existing_track:
                        # Update existing track
                        existing_track.title = track.title
                        existing_track.artist_id = track.artist_id
                        existing_track.duration_ms = track.duration_ms
                        existing_track.isrc = track.isrc
                        existing_track.track_number = track.track_number
                        existing_track.disc_number = track.disc_number
                        existing_track.updated_at = datetime.now(UTC)
                        await self._track_repository.update(existing_track)
                        track = existing_track
                    else:
                        # Add new track
                        await self._track_repository.add(track)

                    # Associate track with playlist
                    await self._playlist_repository.add_track(playlist.id, track.id)
                    tracks_imported += 1

                except Exception as e:
                    tracks_failed += 1
                    errors.append(f"Failed to import track: {e}")

        return ImportSpotifyPlaylistResponse(
            playlist=playlist,
            tracks_imported=tracks_imported,
            tracks_failed=tracks_failed,
            errors=errors,
        )
