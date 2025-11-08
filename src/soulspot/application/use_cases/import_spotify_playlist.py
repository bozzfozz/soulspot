"""Import Spotify playlist use case."""

from dataclasses import dataclass
from datetime import datetime

from soulspot.application.use_cases import UseCase
from soulspot.domain.entities import Artist, Playlist, PlaylistSource, Track
from soulspot.domain.ports import (
    IArtistRepository,
    IPlaylistRepository,
    ISpotifyClient,
    ITrackRepository,
)
from soulspot.domain.value_objects import ArtistId, PlaylistId, SpotifyUri, TrackId


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


class ImportSpotifyPlaylistUseCase(UseCase[ImportSpotifyPlaylistRequest, ImportSpotifyPlaylistResponse]):
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
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            spotify_client: Client for Spotify API operations
            playlist_repository: Repository for playlist persistence
            track_repository: Repository for track persistence
            artist_repository: Repository for artist persistence
        """
        self._spotify_client = spotify_client
        self._playlist_repository = playlist_repository
        self._track_repository = track_repository
        self._artist_repository = artist_repository

    async def execute(self, request: ImportSpotifyPlaylistRequest) -> ImportSpotifyPlaylistResponse:
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
            raise ValueError(f"Failed to fetch playlist from Spotify: {e}")

        # 2. Create or update playlist entity
        playlist_id = PlaylistId.generate()
        playlist = Playlist(
            id=playlist_id,
            name=spotify_playlist["name"],
            description=spotify_playlist.get("description"),
            source=PlaylistSource.SPOTIFY,
            spotify_uri=SpotifyUri(f"spotify:playlist:{request.playlist_id}"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Check if playlist already exists by Spotify URI
        existing_playlist = await self._playlist_repository.get_by_spotify_uri(playlist.spotify_uri)
        if existing_playlist:
            # Update existing playlist
            existing_playlist.name = playlist.name
            existing_playlist.description = playlist.description
            existing_playlist.updated_at = datetime.utcnow()
            await self._playlist_repository.update(existing_playlist)
            playlist = existing_playlist
        else:
            # Add new playlist
            await self._playlist_repository.add(playlist)

        # 3. Process tracks if requested
        if request.fetch_all_tracks:
            track_items = spotify_playlist["tracks"]["items"]

            for item in track_items:
                try:
                    track_data = item.get("track")
                    if not track_data:
                        tracks_failed += 1
                        errors.append("Skipped item with no track data")
                        continue

                    # Get or create artist
                    artist_name = track_data["artists"][0]["name"] if track_data.get("artists") else "Unknown Artist"
                    artist = await self._artist_repository.get_by_name(artist_name)
                    if not artist:
                        artist = Artist(
                            id=ArtistId.generate(),
                            name=artist_name,
                            spotify_uri=SpotifyUri(track_data["artists"][0]["uri"])
                            if track_data.get("artists")
                            else None,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                        await self._artist_repository.add(artist)

                    # Create track entity
                    track_id = TrackId.generate()
                    track = Track(
                        id=track_id,
                        title=track_data["name"],
                        artist_id=artist.id,
                        duration_ms=track_data.get("duration_ms", 0),
                        spotify_uri=SpotifyUri(track_data["uri"]),
                        isrc=track_data.get("external_ids", {}).get("isrc"),
                        track_number=track_data.get("track_number"),
                        disc_number=track_data.get("disc_number", 1),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )

                    # Check if track already exists by Spotify URI
                    existing_track = await self._track_repository.get_by_spotify_uri(track.spotify_uri)
                    if existing_track:
                        # Update existing track
                        existing_track.title = track.title
                        existing_track.artist_id = track.artist_id
                        existing_track.duration_ms = track.duration_ms
                        existing_track.isrc = track.isrc
                        existing_track.track_number = track.track_number
                        existing_track.disc_number = track.disc_number
                        existing_track.updated_at = datetime.utcnow()
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
