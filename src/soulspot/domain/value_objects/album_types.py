"""Album type enums for the domain layer (Lidarr-style dual type system).

Hey future me - this is based on how Lidarr/MusicBrainz model album types!

The KEY INSIGHT is that albums have TWO type dimensions:
1. PRIMARY TYPE: The main category (album, EP, single, etc.)
2. SECONDARY TYPES: Modifiers/attributes (compilation, live, soundtrack, etc.)

Why dual types? Because a live album can ALSO be a compilation! These are orthogonal
concepts. MusicBrainz, Spotify, and Lidarr all use this model.

Example combinations:
- "Thriller" by Michael Jackson: primary=album, secondary=[]
- "Unplugged in New York" by Nirvana: primary=album, secondary=[live]
- "Now That's What I Call Music 2024": primary=album, secondary=[compilation]
- "Pulp Fiction Soundtrack": primary=album, secondary=[soundtrack]
- "The Beatles Live at Hollywood Bowl": primary=album, secondary=[live, compilation]

Usage:
    from soulspot.domain.value_objects.album_types import PrimaryAlbumType, SecondaryAlbumType

    album.primary_type = PrimaryAlbumType.ALBUM
    album.secondary_types = [SecondaryAlbumType.COMPILATION, SecondaryAlbumType.LIVE]

    if SecondaryAlbumType.COMPILATION in album.secondary_types:
        # Show track-level artists in UI
"""

from enum import Enum


class PrimaryAlbumType(str, Enum):
    """Primary album type - the main category of the release.

    These are mutually exclusive - an album can only have ONE primary type.
    Default is ALBUM if not specified.

    Values match MusicBrainz/Lidarr conventions for interoperability.
    """

    ALBUM = "album"
    """Standard full-length album (default)."""

    EP = "ep"
    """Extended Play - typically 4-6 tracks, longer than single but shorter than album."""

    SINGLE = "single"
    """Single release - typically 1-3 tracks."""

    BROADCAST = "broadcast"
    """Radio broadcast recording."""

    OTHER = "other"
    """Anything that doesn't fit other categories."""

    @classmethod
    def from_string(cls, value: str) -> "PrimaryAlbumType":
        """Parse string to enum, defaulting to ALBUM if unknown.

        Args:
            value: String like "album", "ep", "EP", etc.

        Returns:
            Corresponding enum value, or ALBUM if not recognized.
        """
        if not value:
            return cls.ALBUM

        normalized = value.lower().strip()

        # Try direct match first
        try:
            return cls(normalized)
        except ValueError:
            pass

        # Handle common variations
        mappings = {
            "lp": cls.ALBUM,
            "full-length": cls.ALBUM,
            "studio": cls.ALBUM,
            "mini-album": cls.EP,
            "maxi-single": cls.SINGLE,
            '7"': cls.SINGLE,
            '12"': cls.SINGLE,
        }

        return mappings.get(normalized, cls.ALBUM)

    def __str__(self) -> str:
        return self.value


class SecondaryAlbumType(str, Enum):
    """Secondary album type - modifiers that can be combined.

    An album can have MULTIPLE secondary types (e.g., live + compilation).
    These modify the primary type but don't replace it.

    Values match MusicBrainz/Lidarr conventions.
    """

    COMPILATION = "compilation"
    """Various artists compilation or best-of collection."""

    SOUNDTRACK = "soundtrack"
    """Film, TV, or video game soundtrack."""

    LIVE = "live"
    """Live recording from a concert/performance."""

    REMIX = "remix"
    """Album consisting primarily of remixes."""

    DJ_MIX = "dj-mix"
    """Continuous DJ mix of multiple tracks."""

    MIXTAPE = "mixtape"
    """Mixtape/street album (often hip-hop)."""

    DEMO = "demo"
    """Demo recordings, usually unreleased or limited release."""

    SPOKENWORD = "spokenword"
    """Audiobook, podcast, or spoken word content."""

    INTERVIEW = "interview"
    """Interview recording."""

    AUDIOBOOK = "audiobook"
    """Audiobook (subset of spokenword)."""

    @classmethod
    def from_string(cls, value: str) -> "SecondaryAlbumType | None":
        """Parse string to enum, returning None if unknown.

        Args:
            value: String like "compilation", "live", etc.

        Returns:
            Corresponding enum value, or None if not recognized.
        """
        if not value:
            return None

        normalized = value.lower().strip()

        # Try direct match first
        try:
            return cls(normalized)
        except ValueError:
            pass

        # Handle variations
        mappings = {
            "dj mix": cls.DJ_MIX,
            "djmix": cls.DJ_MIX,
            "mixtape/street": cls.MIXTAPE,
            "street": cls.MIXTAPE,
            "audio drama": cls.SPOKENWORD,
            "audiodrama": cls.SPOKENWORD,
            "spoken word": cls.SPOKENWORD,
        }

        return mappings.get(normalized)

    @classmethod
    def from_string_list(cls, values: list[str]) -> list["SecondaryAlbumType"]:
        """Parse list of strings to list of enums, filtering unknown values.

        Args:
            values: List of strings like ["compilation", "live"]

        Returns:
            List of valid enum values (unknown strings are filtered out).
        """
        result = []
        for v in values:
            parsed = cls.from_string(v)
            if parsed is not None:
                result.append(parsed)
        return result

    def __str__(self) -> str:
        return self.value


# =============================================================================
# VARIOUS ARTISTS DETECTION — Lidarr-Style Compilation Heuristics
# =============================================================================
#
# Hey future me - this implements Lidarr's TrackGroupingService.IsVariousArtists logic!
#
# DETECTION ORDER (precedence):
# 1. Explicit compilation flags (cpil, TCMP, Vorbis COMPILATION) — parsed in scanner
# 2. album_artist matches VA patterns ("Various Artists", "VA", etc.)
# 3. Track artist diversity analysis (≥75% unique artists OR dominant <25%)
# 4. [Optional] MusicBrainz release type verification (Phase 3)
#
# Lidarr Source Reference:
# - TrackGroupingService.cs: IsVariousArtists() uses 75% threshold
# - AudioTag.cs: Reads cpil (MP4), TCMP (ID3), COMPILATION (Vorbis)
#
# MusicBrainz "Various Artists" MBID: 89ad4ac3-39f7-470e-963a-56509c546377
# =============================================================================

# Thresholds — based on Lidarr's proven production values
DIVERSITY_THRESHOLD = 0.75  # If ≥75% of tracks have unique artists → compilation
DOMINANT_ARTIST_THRESHOLD = 0.25  # If no artist has >25% of tracks → compilation
MIN_TRACKS_FOR_DIVERSITY = 3  # Need at least 3 tracks to apply diversity logic

# Hey future me - these are the known "Various Artists" patterns for compilation detection!
# When scanning library, if album_artist matches any of these (case-insensitive), we know
# it's a compilation. Add more patterns as needed. The patterns are in priority order -
# "Various Artists" is most common, "VA" is abbreviated version common in file tags.
VARIOUS_ARTISTS_PATTERNS = frozenset(
    [
        "various artists",
        "various",
        "va",
        "v.a.",
        "v. a.",
        "v/a",
        "diverse",  # German
        "verschiedene",  # German full form
        "verschiedene künstler",  # German
        "verschiedene interpreten",  # German
        "varios artistas",  # Spanish
        "artistes divers",  # French
        "artisti vari",  # Italian
        "vari",  # Italian short
        "sampler",
        "compilation",
        "unknown artist",  # Often misnamed compilations
        "unknown",
        "[unknown]",
        "soundtrack",  # Often compilations
        "ost",  # Original Soundtrack
        "original soundtrack",
    ]
)

# Prefixes that indicate VA even with suffix (e.g., "Various Artists (2024)")
VARIOUS_ARTISTS_PREFIXES = ("various artists", "various ", "va ", "v.a. ")


class CompilationDetectionResult:
    """Result of compilation detection with reason tracking.

    Hey future me - this is useful for debugging why an album was flagged!
    The UI can show "Detected as compilation via: track_diversity (87% unique)"
    """

    __slots__ = ("is_compilation", "reason", "confidence", "details")

    def __init__(
        self,
        is_compilation: bool,
        reason: str,
        confidence: float = 1.0,
        details: dict | None = None,
    ) -> None:
        self.is_compilation = is_compilation
        self.reason = (
            reason  # e.g., "explicit_flag", "album_artist_pattern", "track_diversity"
        )
        self.confidence = confidence  # 0.0-1.0 how sure we are
        self.details = details or {}  # Extra info like diversity percentage

    def __bool__(self) -> bool:
        return self.is_compilation

    def __repr__(self) -> str:
        return f"CompilationDetectionResult({self.is_compilation}, reason={self.reason!r}, confidence={self.confidence:.0%})"

    def to_dict(self) -> dict:
        """Serialize for JSON storage or API response."""
        return {
            "is_compilation": self.is_compilation,
            "reason": self.reason,
            "confidence": self.confidence,
            "details": self.details,
        }


def is_various_artists(artist_name: str | None) -> bool:
    """Check if an artist name indicates "Various Artists" (compilation).

    Args:
        artist_name: The artist name to check.

    Returns:
        True if the name matches a Various Artists pattern.

    Example:
        >>> is_various_artists("Various Artists")
        True
        >>> is_various_artists("VA")
        True
        >>> is_various_artists("The Beatles")
        False
        >>> is_various_artists("Various Artists (2024)")
        True
    """
    if not artist_name:
        return False

    normalized = artist_name.lower().strip()

    # Exact match check (O(1) with frozenset)
    if normalized in VARIOUS_ARTISTS_PATTERNS:
        return True

    # Partial match for patterns like "Various Artists (2024)"
    return any(normalized.startswith(prefix) for prefix in VARIOUS_ARTISTS_PREFIXES)


def calculate_track_diversity(track_artists: list[str]) -> tuple[float, dict]:
    """Calculate how diverse the track artists are on an album.

    Hey future me - this is the core of Lidarr's compilation detection!

    Returns:
        Tuple of (diversity_ratio, details_dict)
        - diversity_ratio: 0.0 (all same artist) to 1.0 (all unique)
        - details: {unique_artists, total_tracks, dominant_artist, dominant_percent}

    Example:
        >>> calculate_track_diversity(["Artist A", "Artist B", "Artist C", "Artist A"])
        (0.75, {"unique_artists": 3, "total_tracks": 4, ...})
    """
    if not track_artists:
        return 0.0, {"unique_artists": 0, "total_tracks": 0}

    # Normalize artist names (lowercase, strip whitespace)
    normalized = [a.lower().strip() for a in track_artists if a]

    if not normalized:
        return 0.0, {"unique_artists": 0, "total_tracks": 0}

    total_tracks = len(normalized)
    unique_artists = set(normalized)
    unique_count = len(unique_artists)

    # Calculate diversity ratio
    diversity_ratio = unique_count / total_tracks

    # Find dominant artist (most frequent)
    from collections import Counter

    artist_counts = Counter(normalized)
    dominant_artist, dominant_count = artist_counts.most_common(1)[0]
    dominant_percent = dominant_count / total_tracks

    details = {
        "unique_artists": unique_count,
        "total_tracks": total_tracks,
        "dominant_artist": dominant_artist,
        "dominant_count": dominant_count,
        "dominant_percent": round(dominant_percent, 3),
        "diversity_ratio": round(diversity_ratio, 3),
    }

    return diversity_ratio, details


def detect_compilation_from_track_artists(
    album_artist: str | None,
    track_artists: list[str],
    threshold: int = 3,  # noqa: ARG001
) -> bool:
    """Detect if an album is a compilation based on track artist diversity.

    DEPRECATED: Use detect_compilation() for full detection with reasons.
    Kept for backwards compatibility.

    Args:
        album_artist: The album-level artist (from TPE2 tag or similar).
        track_artists: List of track-level artists from the album.
        threshold: Minimum number of unique artists to consider compilation.

    Returns:
        True if the album appears to be a compilation.
    """
    result = detect_compilation(
        album_artist=album_artist,
        track_artists=track_artists,
        explicit_flag=None,
    )
    return result.is_compilation


def detect_compilation(
    album_artist: str | None = None,
    track_artists: list[str] | None = None,
    explicit_flag: bool | None = None,
) -> CompilationDetectionResult:
    """Full compilation detection with Lidarr-style heuristics.

    Hey future me - this is the MAIN ENTRY POINT for compilation detection!
    Call this with whatever data you have. It applies rules in precedence order:

    1. explicit_flag (from TCMP/cpil tags) — most reliable
    2. album_artist matches VA patterns — very reliable
    3. Track diversity analysis — requires MIN_TRACKS_FOR_DIVERSITY tracks

    Args:
        album_artist: Album-level artist (TPE2/aART tag).
        track_artists: List of track-level artists from the album.
        explicit_flag: Value from TCMP/cpil/COMPILATION tag (True/False/None).

    Returns:
        CompilationDetectionResult with is_compilation, reason, confidence, details.

    Example:
        >>> result = detect_compilation(album_artist="Various Artists")
        >>> result.is_compilation
        True
        >>> result.reason
        'album_artist_pattern'

        >>> result = detect_compilation(
        ...     track_artists=["Artist A", "Artist B", "Artist C", "Artist D"]
        ... )
        >>> result.is_compilation
        True
        >>> result.reason
        'track_diversity'
        >>> result.details["diversity_ratio"]
        1.0
    """
    # Rule 1: Explicit compilation flag (highest precedence)
    # Hey - TCMP=1 in ID3 or cpil=1 in MP4 means user/tagger SAID it's a compilation
    if explicit_flag is True:
        return CompilationDetectionResult(
            is_compilation=True,
            reason="explicit_flag",
            confidence=1.0,
            details={"source": "TCMP/cpil/COMPILATION tag"},
        )

    # Rule 2: Album artist matches Various Artists patterns
    if album_artist and is_various_artists(album_artist):
        return CompilationDetectionResult(
            is_compilation=True,
            reason="album_artist_pattern",
            confidence=0.95,
            details={"matched_artist": album_artist},
        )

    # Rule 3: Track artist diversity analysis
    # Need minimum tracks to make this meaningful
    if track_artists and len(track_artists) >= MIN_TRACKS_FOR_DIVERSITY:
        diversity_ratio, diversity_details = calculate_track_diversity(track_artists)

        # Lidarr's primary check: ≥75% unique artists
        if diversity_ratio >= DIVERSITY_THRESHOLD:
            return CompilationDetectionResult(
                is_compilation=True,
                reason="track_diversity",
                confidence=min(
                    0.9, diversity_ratio
                ),  # Higher diversity = higher confidence
                details=diversity_details,
            )

        # Lidarr's secondary check: No dominant artist (none has >25%)
        dominant_percent = diversity_details.get("dominant_percent", 1.0)
        if dominant_percent < DOMINANT_ARTIST_THRESHOLD:
            return CompilationDetectionResult(
                is_compilation=True,
                reason="no_dominant_artist",
                confidence=0.8,
                details=diversity_details,
            )

        # Borderline case: 50-75% diversity - might be compilation
        # Hey - this is where MusicBrainz verification would help (Phase 3)
        if diversity_ratio >= 0.5:
            return CompilationDetectionResult(
                is_compilation=False,
                reason="borderline_diversity",
                confidence=0.5,  # Low confidence = might be wrong
                details={**diversity_details, "suggestion": "verify_with_musicbrainz"},
            )

    # Default: Not a compilation (or not enough data)
    return CompilationDetectionResult(
        is_compilation=False,
        reason="no_indicators",
        confidence=0.7 if track_artists else 0.5,
        details={"track_count": len(track_artists) if track_artists else 0},
    )
