"""
Standard Data Transfer Objects for SoulSpot Plugin System.

Hey future me – diese DTOs sind das LINGUA FRANCA zwischen allen Music-Service-Plugins!
Jedes Plugin (Spotify, Deezer, Tidal) MUSS Daten in diesem Format zurückgeben.
Application Services müssen KEINE API-spezifische JSON-Konvertierung mehr machen.

Warum DTOs statt Domain Entities direkt?
1. Entities haben required IDs (wir haben aber noch keine bei API-Abrufen)
2. Entities validieren sofort (API-Daten könnten teilweise sein)
3. DTOs sind "dumb data carriers" - Entities haben Business Logic
4. DTOs erlauben partielle Updates (nur bestimmte Felder setzen)

Flow: Plugin API Response → DTO (standardisiert) → Service → Repository → Entity
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from soulspot.domain.exceptions import ValidationError
# Hey future me – ArtistDTO ist das Standard-Format für Künstler aus ALLEN Services!
# Spotify, Deezer, Tidal – alle müssen dieses Format zurückgeben.
# Optional fields erlauben partielle Daten (nicht jede API hat alle Infos).
# Die `source_service` field sagt, woher die Daten kommen (für metadata_sources tracking).
@dataclass
class ArtistDTO:
    """
    Standardized Artist data from any music service.

    All plugins must convert their API responses to this format.
    Application services receive this DTO and create/update Domain Entities.
    """

    name: str
    source_service: str  # "spotify", "deezer", "tidal", "musicbrainz"

    # Hey future me – internal_id is SET BY ProviderMappingService, not by plugins!
    # It contains the SoulSpot internal UUID if this entity exists in our database.
    # Plugins leave this as None, the mapper fills it in after DB lookup.
    internal_id: str | None = None  # SoulSpot internal UUID (set by mapper)

    # Service-specific IDs (Plugin setzt nur das eigene)
    spotify_id: str | None = None  # Spotify artist ID (ohne "spotify:artist:" Prefix)
    spotify_uri: str | None = None  # Full URI "spotify:artist:xxx"
    deezer_id: str | None = None
    tidal_id: str | None = None
    musicbrainz_id: str | None = None

    # Metadata (Optional - nicht jeder Service hat alles)
    image_url: str | None = None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    disambiguation: str | None = None  # MusicBrainz disambiguation
    popularity: int | None = None  # Spotify 0-100
    followers: int | None = None

    # Hey future me – external_urls speichert Links zu Profilen auf verschiedenen Plattformen!
    # z.B. {"spotify": "https://open.spotify.com/artist/...", "wikipedia": "..."}
    external_urls: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate essential fields."""
        if not self.name or not self.name.strip():
            raise ValidationError("Artist name cannot be empty")
        if not self.source_service:
            raise ValidationError("source_service must be specified")


# Hey future me – AlbumDTO ist das Standard-Format für Alben aus ALLEN Services!
# artist_name und artist_id sind beide vorhanden, falls wir den Artist noch nicht in DB haben.
# total_tracks hilft bei Discography-Vollständigkeitsprüfungen.
@dataclass
class AlbumDTO:
    """
    Standardized Album data from any music service.

    All plugins must convert their API responses to this format.
    """

    title: str
    artist_name: str  # Artist name (for display/matching)
    source_service: str  # "spotify", "deezer", "tidal", "musicbrainz"

    # Hey future me – internal_id is SET BY ProviderMappingService, not by plugins!
    internal_id: str | None = None  # SoulSpot internal UUID (set by mapper)
    artist_internal_id: str | None = None  # Artist's internal UUID (set by mapper)

    # Service-specific IDs
    spotify_id: str | None = None
    spotify_uri: str | None = None
    deezer_id: str | None = None
    tidal_id: str | None = None
    musicbrainz_id: str | None = None

    # Artist reference (if known)
    artist_spotify_id: str | None = None
    artist_deezer_id: str | None = None
    artist_tidal_id: str | None = None

    # Album metadata
    release_date: str | None = None  # ISO format "YYYY-MM-DD" or "YYYY"
    release_year: int | None = None
    artwork_url: str | None = None  # Cover art URL
    total_tracks: int | None = None

    # Lidarr-style album types
    album_type: str = "album"  # "album", "single", "ep", "compilation"
    primary_type: str = "Album"
    secondary_types: list[str] = field(default_factory=list)

    # Optional metadata
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    disambiguation: str | None = None
    label: str | None = None
    upc: str | None = None  # Universal Product Code

    # External URLs
    external_urls: dict[str, str] = field(default_factory=dict)

    # Hey future me – tracks ist Optional! Manche API-Aufrufe geben Alben OHNE Tracks zurück
    # (z.B. Artist-Discography-Übersicht). Für volle Album-Details wird separat abgefragt.
    tracks: list["TrackDTO"] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate essential fields."""
        if not self.title or not self.title.strip():
            raise ValidationError("Album title cannot be empty")
        if not self.artist_name or not self.artist_name.strip():
            raise ValidationError("Artist name cannot be empty")
        if not self.source_service:
            raise ValidationError("source_service must be specified")


# Hey future me – TrackDTO ist das Standard-Format für Tracks aus ALLEN Services!
# ISRC ist der universelle Identifikator für Tracks weltweit – nutze ihn für Cross-Service-Matching!
# preview_url ist für 30-Sekunden-Snippets (Spotify bietet das an).
@dataclass
class TrackDTO:
    """
    Standardized Track data from any music service.

    All plugins must convert their API responses to this format.
    """

    title: str
    artist_name: str  # Primary artist name
    source_service: str  # "spotify", "deezer", "tidal"

    # Internal SoulSpot UUIDs - populated by ProviderMappingService after lookup/creation
    # Hey future me - diese Felder werden NICHT von Plugins gesetzt!
    # Der ProviderMappingService mappt die service-spezifischen IDs auf interne UUIDs.
    internal_id: str | None = None  # SoulSpot Track UUID
    internal_artist_id: str | None = None  # SoulSpot Artist UUID (primary artist)
    internal_album_id: str | None = None  # SoulSpot Album UUID

    # Service-specific IDs
    spotify_id: str | None = None
    spotify_uri: str | None = None
    deezer_id: str | None = None
    tidal_id: str | None = None
    musicbrainz_id: str | None = None

    # Universal identifier - THE KEY for cross-service matching!
    isrc: str | None = None

    # Artist references
    artist_spotify_id: str | None = None
    artist_deezer_id: str | None = None
    artist_tidal_id: str | None = None

    # Album references (optional - some tracks are singles)
    album_name: str | None = None
    album_spotify_id: str | None = None
    album_deezer_id: str | None = None
    album_tidal_id: str | None = None

    # Track metadata
    duration_ms: int = 0
    track_number: int | None = None
    disc_number: int = 1
    explicit: bool = False
    popularity: int | None = None  # Spotify 0-100

    # Additional artists (features, collaborations)
    additional_artists: list["ArtistDTO"] = field(default_factory=list)

    # Hey future me - `artists` ist eine Convenience-Property, die den Primary Artist + Additional
    # Artists kombiniert. Wird von spotify_sync_service verwendet.
    # Equivalent to [primary_artist, *additional_artists]
    artists: list["ArtistDTO"] = field(default_factory=list)

    # Hey future me - `album` ist ein optionales AlbumDTO für Tracks, die mit Album-Kontext geladen
    # werden (z.B. aus get_saved_tracks). Wird von spotify_sync_service verwendet.
    # Optional because tracks might be loaded without album context.
    album: "AlbumDTO | None" = None

    # Optional metadata
    genres: list[str] = field(default_factory=list)
    preview_url: str | None = None  # 30-second preview URL

    # External URLs
    external_urls: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate essential fields."""
        if not self.title or not self.title.strip():
            raise ValidationError("Track title cannot be empty")
        if not self.artist_name or not self.artist_name.strip():
            raise ValidationError("Artist name cannot be empty")
        if not self.source_service:
            raise ValidationError("source_service must be specified")
        if self.duration_ms < 0:
            raise ValidationError("Duration cannot be negative")


# Hey future me – PlaylistDTO ist das Standard-Format für Playlists aus ALLEN Services!
# owner_* fields tracken den Playlist-Ersteller (wichtig für collaborative Playlists).
# snapshot_id ist Spotify-spezifisch für Change-Detection.
@dataclass
class PlaylistDTO:
    """
    Standardized Playlist data from any music service.

    All plugins must convert their API responses to this format.
    """

    name: str
    source_service: str  # "spotify", "deezer", "tidal"

    # Service-specific IDs
    spotify_id: str | None = None
    spotify_uri: str | None = None
    deezer_id: str | None = None
    tidal_id: str | None = None

    # Playlist metadata
    description: str | None = None
    cover_url: str | None = None
    is_public: bool = True
    is_collaborative: bool = False
    total_tracks: int | None = None

    # Owner info
    owner_name: str | None = None
    owner_id: str | None = None

    # Spotify-specific for change detection
    snapshot_id: str | None = None

    # Tracks (optional - may need separate fetch for large playlists)
    tracks: list["TrackDTO"] = field(default_factory=list)

    # External URLs
    external_urls: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate essential fields."""
        if not self.name or not self.name.strip():
            raise ValidationError("Playlist name cannot be empty")
        if not self.source_service:
            raise ValidationError("source_service must be specified")


# Hey future me – SearchResultDTO ist Container für Suchergebnisse mit allen Typen!
# Services können nur Tracks zurückgeben oder alles – daher alles Optional.
@dataclass
class SearchResultDTO:
    """
    Standardized search results from any music service.

    Contains artists, albums, and tracks found in search.
    """

    query: str
    source_service: str

    artists: list[ArtistDTO] = field(default_factory=list)
    albums: list[AlbumDTO] = field(default_factory=list)
    tracks: list[TrackDTO] = field(default_factory=list)
    playlists: list[PlaylistDTO] = field(default_factory=list)

    # Pagination info
    total_artists: int = 0
    total_albums: int = 0
    total_tracks: int = 0
    total_playlists: int = 0
    offset: int = 0
    limit: int = 20


# Hey future me – UserProfileDTO für OAuth-verbundene User-Infos!
# product zeigt Spotify-Abo-Typ (free/premium), wichtig für Feature-Gates.
@dataclass
class UserProfileDTO:
    """
    Standardized user profile data from any music service.
    """

    display_name: str
    source_service: str

    # Service-specific IDs
    spotify_id: str | None = None
    deezer_id: str | None = None
    tidal_id: str | None = None

    email: str | None = None
    country: str | None = None
    image_url: str | None = None
    product: str | None = None  # "free", "premium", etc.

    # External URLs
    external_urls: dict[str, str] = field(default_factory=dict)


# Hey future me – PaginatedResponse ist generischer Wrapper für paginierte API-Antworten!
# Plugins wrappen ihre Listen-Responses hiermit für konsistente Pagination.
@dataclass
class PaginatedResponse[T]:
    """
    Generic wrapper for paginated responses.

    Type parameter T is the item type (ArtistDTO, TrackDTO, etc.)
    """

    items: list[T]
    total: int
    offset: int = 0
    limit: int = 20
    next_offset: int | None = None  # None means no more pages

    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.next_offset is not None


# ============================================================================
# VIEW MODELS - For Template Rendering
# ============================================================================
# Hey future me - ViewModels sind für Templates!
# Sie enthalten vorformatierte Daten, die das Template direkt anzeigen kann.
# Routes sollen KEINE Model-Details kennen - Services konvertieren zu ViewModels.


@dataclass
class TrackView:
    """Track data formatted for template display.
    
    Hey future me - das ist die "View" Version eines Tracks!
    Alle Felder sind template-ready (formatierte Dauer, etc.)
    Routes müssen NICHT wissen, ob Model "title" oder "name" hat.
    """
    spotify_id: str | None
    name: str  # Template erwartet "name", nicht "title"
    track_number: int
    disc_number: int
    duration_ms: int
    duration_str: str  # Vorformatiert: "3:45"
    explicit: bool
    preview_url: str | None
    isrc: str | None
    is_downloaded: bool


@dataclass
class AlbumDetailView:
    """Album detail page view model.
    
    Hey future me - das ist ein ViewModel für die Album-Detail-Seite!
    Enthält alles was das Template braucht, vorformatiert und ready-to-use.
    Routes rufen Service auf und bekommen dieses ViewModel zurück.
    """
    # Album info
    spotify_id: str | None
    name: str
    image_url: str | None
    release_date: str | None
    album_type: str
    total_tracks: int
    
    # Artist info (optional, kann None sein)
    artist_spotify_id: str | None
    artist_name: str | None
    
    # Tracks (vorformatiert für Template)
    tracks: list[TrackView]
    
    # Aggregate data
    track_count: int
    total_duration_str: str  # "45 min 32 sec"
    
    # Sync status
    synced: bool = False
    sync_error: str | None = None


# Export all DTOs
__all__ = [
    "ArtistDTO",
    "AlbumDTO",
    "TrackDTO",
    "PlaylistDTO",
    "SearchResultDTO",
    "UserProfileDTO",
    "PaginatedResponse",
    # ViewModels
    "TrackView",
    "AlbumDetailView",
]
