"""Quality Profile Entity - Download quality preferences.

Hey future me - Quality Profiles definieren wie Musik heruntergeladen werden soll!

KONZEPT:
- User erstellt Profile wie "Audiophile", "Mobile", "Space Saver"
- Beim Download wird das aktive Profil angewendet
- Search-Ergebnisse werden gefiltert und gerankt basierend auf Profil

FEATURES:
- Format-Präferenzen (FLAC > MP3 > AAC)
- Bitrate-Filter (min/max)
- Größenlimits
- Keyword-Ausschlüsse ("live", "remix", "karaoke")
- User-Ausschlüsse (blockierte Uploader)

USAGE:
```python
# Audiophile nur FLAC
profile = QualityProfile(
    name="Audiophile",
    preferred_formats=["flac", "alac"],
    min_bitrate=1000,
    prefer_lossless=True,
    allow_lossy=False,
)

# Filter Search Results
matcher = QualityMatcher(profile)
for result in search_results:
    matches, score = matcher.matches(result)
    if matches:
        ranked_results.append((result, score))
```
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class AudioFormat(str, Enum):
    """Supported audio formats with quality ranking.

    Hey future me - order matters! Higher = better quality.
    FLAC is lossless (1411kbps equivalent), MP3/AAC are lossy.
    """

    FLAC = "flac"
    ALAC = "alac"
    WAV = "wav"
    MP3 = "mp3"
    AAC = "aac"
    M4A = "m4a"
    OGG = "ogg"
    OPUS = "opus"

    @property
    def is_lossless(self) -> bool:
        """Check if format is lossless."""
        return self in {AudioFormat.FLAC, AudioFormat.ALAC, AudioFormat.WAV}


# Quality ranking - higher = better (for sorting)
FORMAT_QUALITY_SCORE = {
    AudioFormat.FLAC: 100,
    AudioFormat.ALAC: 95,
    AudioFormat.WAV: 90,  # Uncompressed but no metadata support
    AudioFormat.MP3: 70,
    AudioFormat.AAC: 65,
    AudioFormat.M4A: 65,
    AudioFormat.OGG: 60,
    AudioFormat.OPUS: 55,
}


@dataclass
class QualityProfileId:
    """Value object for Quality Profile ID."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("QualityProfileId cannot be empty")

    @classmethod
    def generate(cls) -> QualityProfileId:
        """Generate a new unique ID."""
        return cls(str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, QualityProfileId):
            return self.value == other.value
        return False


@dataclass
class QualityProfile:
    """Quality profile for download preferences.

    Hey future me - jeder User kann mehrere Profile haben!
    Ein Profil ist "is_default" und wird automatisch verwendet.
    Profile können vordefiniert (system) oder custom (user) sein.

    SCORING:
    Search results werden mit diesem Profil gefiltert und gerankt.
    Score-Berechnung:
    1. Format-Priorität (höher = besser, basierend auf preferred_formats Reihenfolge)
    2. Bitrate-Bonus (höher = besser)
    3. Size-Penalty (größer = schlechter, wenn max_file_size_mb gesetzt)
    """

    id: QualityProfileId
    name: str
    description: str | None = None

    # Format-Präferenzen (Reihenfolge = Priorität, erstes ist bestes)
    preferred_formats: list[str] = field(default_factory=lambda: ["flac", "mp3", "aac"])

    # Bitrate-Filter (kbps)
    min_bitrate: int | None = None  # z.B. 256 für "mindestens 256kbps"
    max_bitrate: int | None = None  # z.B. 320 für "maximal 320kbps" (space saver)

    # Größenlimits (MB)
    min_file_size_mb: float | None = (
        None  # z.B. 3.0 für "mindestens 3MB" (filter corrupted)
    )
    max_file_size_mb: float | None = None  # z.B. 50.0 für "maximal 50MB" (mobile)

    # Ausschlüsse - Case-insensitive matching
    exclude_keywords: list[str] = field(
        default_factory=lambda: ["live", "remix", "karaoke", "instrumental", "cover"]
    )
    exclude_users: list[str] = field(default_factory=list)  # Blocked uploaders

    # Quality flags
    prefer_lossless: bool = True  # Bevorzuge lossless über lossy
    allow_lossy: bool = True  # Erlaube lossy wenn kein lossless gefunden
    require_matching_artist: bool = True  # Filename muss Artist enthalten

    # Profile metadata
    is_default: bool = False  # Ist das aktive Standard-Profil?
    is_system: bool = False  # System-Profil (nicht editierbar)?
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None

    # Hey future me - historical baggage: older layers used `is_active`/`is_builtin`.
    # We keep these aliases so the app doesn't explode if some path still calls them,
    # but the canonical domain vocabulary remains `is_default`/`is_system`.
    @property
    def is_active(self) -> bool:
        return self.is_default

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.is_default = value

    # Hey future me - same story as `is_active`: DB calls it `is_builtin`, domain calls it `is_system`.
    @property
    def is_builtin(self) -> bool:
        return self.is_system

    @is_builtin.setter
    def is_builtin(self, value: bool) -> None:
        self.is_system = value

    def set_as_default(self) -> None:
        """Mark this profile as default."""
        self.is_default = True
        self.updated_at = datetime.now(UTC)

    def unset_default(self) -> None:
        """Remove default flag."""
        self.is_default = False
        self.updated_at = datetime.now(UTC)

    def update(
        self,
        name: str | None = None,
        description: str | None = None,
        preferred_formats: list[str] | None = None,
        min_bitrate: int | None = None,
        max_bitrate: int | None = None,
        min_file_size_mb: float | None = None,
        max_file_size_mb: float | None = None,
        exclude_keywords: list[str] | None = None,
        exclude_users: list[str] | None = None,
        prefer_lossless: bool | None = None,
        allow_lossy: bool | None = None,
    ) -> None:
        """Update profile settings.

        Hey future me - nur nicht-None Werte werden aktualisiert!
        System-Profile können nicht editiert werden.
        """
        if self.is_system:
            raise ValueError("Cannot modify system profile")

        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if preferred_formats is not None:
            self.preferred_formats = preferred_formats
        if min_bitrate is not None:
            self.min_bitrate = min_bitrate if min_bitrate > 0 else None
        if max_bitrate is not None:
            self.max_bitrate = max_bitrate if max_bitrate > 0 else None
        if min_file_size_mb is not None:
            self.min_file_size_mb = min_file_size_mb if min_file_size_mb > 0 else None
        if max_file_size_mb is not None:
            self.max_file_size_mb = max_file_size_mb if max_file_size_mb > 0 else None
        if exclude_keywords is not None:
            self.exclude_keywords = exclude_keywords
        if exclude_users is not None:
            self.exclude_users = exclude_users
        if prefer_lossless is not None:
            self.prefer_lossless = prefer_lossless
        if allow_lossy is not None:
            self.allow_lossy = allow_lossy

        self.updated_at = datetime.now(UTC)


# =============================================================================
# PREDEFINED QUALITY PROFILES
# =============================================================================
# Hey future me - diese werden beim ersten Start in die DB eingefügt!
# User können sie nicht löschen oder editieren (is_system=True).
# Sie können aber eigene Profile erstellen.


def create_audiophile_profile() -> QualityProfile:
    """Create the Audiophile quality profile.

    Only lossless formats (FLAC, ALAC, WAV).
    No size limit, high bitrate requirement.
    """
    return QualityProfile(
        id=QualityProfileId("system-audiophile"),
        name="Audiophile",
        description="Nur verlustfreie Formate (FLAC, ALAC). Für HiFi-Enthusiasten.",
        preferred_formats=["flac", "alac", "wav"],
        min_bitrate=900,  # ~CD quality
        max_bitrate=None,
        min_file_size_mb=5.0,  # Filter tiny corrupt files
        max_file_size_mb=None,  # No limit
        exclude_keywords=[
            "live",
            "remix",
            "karaoke",
            "instrumental",
            "cover",
            "demo",
            "bootleg",
        ],
        prefer_lossless=True,
        allow_lossy=False,  # STRICT: No MP3/AAC
        is_default=False,
        is_system=True,
    )


def create_balanced_profile() -> QualityProfile:
    """Create the Balanced quality profile.

    Good quality with reasonable file size.
    Prefers FLAC but accepts high-quality MP3.
    """
    return QualityProfile(
        id=QualityProfileId("system-balanced"),
        name="Balanced",
        description="Gute Qualität bei vernünftiger Dateigröße. Für die meisten Nutzer.",
        preferred_formats=["flac", "mp3", "aac", "m4a"],
        min_bitrate=256,
        max_bitrate=None,
        min_file_size_mb=2.0,
        max_file_size_mb=80.0,  # Max 80MB per track
        exclude_keywords=["live", "remix", "karaoke", "bootleg"],
        prefer_lossless=True,
        allow_lossy=True,
        is_default=True,  # Default profile for new users
        is_system=True,
    )


def create_space_saver_profile() -> QualityProfile:
    """Create the Space Saver quality profile.

    Compact files for mobile listening.
    MP3/AAC preferred, strict size limits.
    """
    return QualityProfile(
        id=QualityProfileId("system-space-saver"),
        name="Space Saver",
        description="Kompakte Dateien für mobiles Hören. Spart Speicherplatz.",
        preferred_formats=["mp3", "aac", "m4a", "ogg", "opus"],
        min_bitrate=128,
        max_bitrate=320,
        min_file_size_mb=1.0,
        max_file_size_mb=15.0,  # Max 15MB per track
        exclude_keywords=["live", "karaoke"],
        prefer_lossless=False,
        allow_lossy=True,
        is_default=False,
        is_system=True,
    )


def create_any_quality_profile() -> QualityProfile:
    """Create the Any Quality profile.

    Accept anything - useful for rare tracks.
    No filters, no restrictions.
    """
    return QualityProfile(
        id=QualityProfileId("system-any"),
        name="Any Quality",
        description="Akzeptiert alles. Für seltene Tracks wo Qualität zweitrangig ist.",
        preferred_formats=["flac", "mp3", "aac", "m4a", "ogg", "wav", "alac", "opus"],
        min_bitrate=None,
        max_bitrate=None,
        min_file_size_mb=None,
        max_file_size_mb=None,
        exclude_keywords=[],  # Accept everything
        prefer_lossless=True,
        allow_lossy=True,
        is_default=False,
        is_system=True,
    )


def get_system_profiles() -> list[QualityProfile]:
    """Get all system-defined quality profiles."""
    return [
        create_audiophile_profile(),
        create_balanced_profile(),
        create_space_saver_profile(),
        create_any_quality_profile(),
    ]


# =============================================================================
# QUALITY MATCHER - Filters and ranks search results
# =============================================================================


@dataclass
class MatchResult:
    """Result of matching a file against a quality profile."""

    matches: bool  # Does the file match the profile?
    score: int  # Ranking score (higher = better)
    reject_reason: str | None = None  # Why it was rejected


class QualityMatcher:
    """Filters and ranks search results based on quality profile.

    Hey future me - dieser Matcher wird in AdvancedSearchService verwendet!

    USAGE:
    ```python
    matcher = QualityMatcher(profile)
    for result in search_results:
        match = matcher.match(result)
        if match.matches:
            ranked.append((result, match.score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    ```
    """

    def __init__(self, profile: QualityProfile):
        self.profile = profile

    def match(self, file_info: dict) -> MatchResult:
        """Check if file matches profile and calculate score.

        Args:
            file_info: Dict with keys:
                - filename: str
                - bitrate: int (kbps)
                - size: int (bytes)
                - username: str (uploader)

        Returns:
            MatchResult with matches flag, score, and optional reject reason
        """
        filename = file_info.get("filename", "").lower()
        bitrate = file_info.get("bitrate", 0)
        size_bytes = file_info.get("size", 0)
        username = file_info.get("username", "")
        size_mb = size_bytes / (1024 * 1024) if size_bytes else 0

        # 1. Check excluded users
        if username and username.lower() in [
            u.lower() for u in self.profile.exclude_users
        ]:
            return MatchResult(False, 0, f"User '{username}' is blocked")

        # 2. Check excluded keywords
        for keyword in self.profile.exclude_keywords:
            if keyword.lower() in filename:
                return MatchResult(False, 0, f"Keyword '{keyword}' excluded")

        # 3. Detect format
        file_format = self._detect_format(filename)
        if not file_format:
            return MatchResult(False, 0, "Unknown format")

        # 4. Check format preference
        is_lossless = file_format in ["flac", "alac", "wav"]
        if not is_lossless and not self.profile.allow_lossy:
            return MatchResult(False, 0, f"Lossy format '{file_format}' not allowed")

        if file_format not in self.profile.preferred_formats:
            # Format not in preferences - still allow but with penalty
            pass

        # 5. Check bitrate
        if self.profile.min_bitrate and bitrate and bitrate < self.profile.min_bitrate:
            return MatchResult(
                False,
                0,
                f"Bitrate {bitrate}kbps below minimum {self.profile.min_bitrate}",
            )

        if self.profile.max_bitrate and bitrate and bitrate > self.profile.max_bitrate:
            return MatchResult(
                False,
                0,
                f"Bitrate {bitrate}kbps above maximum {self.profile.max_bitrate}",
            )

        # 6. Check file size
        if (
            self.profile.min_file_size_mb
            and size_mb
            and size_mb < self.profile.min_file_size_mb
        ):
            return MatchResult(
                False,
                0,
                f"Size {size_mb:.1f}MB below minimum {self.profile.min_file_size_mb}MB",
            )

        if (
            self.profile.max_file_size_mb
            and size_mb
            and size_mb > self.profile.max_file_size_mb
        ):
            return MatchResult(
                False,
                0,
                f"Size {size_mb:.1f}MB above maximum {self.profile.max_file_size_mb}MB",
            )

        # === CALCULATE SCORE ===
        score = 0

        # Format priority bonus (first in list = best)
        if file_format in self.profile.preferred_formats:
            format_index = self.profile.preferred_formats.index(file_format)
            # Higher bonus for earlier (better) formats
            score += (len(self.profile.preferred_formats) - format_index) * 1000
        else:
            # Not in preferred list - base score from format quality
            score += FORMAT_QUALITY_SCORE.get(AudioFormat(file_format), 0) * 5

        # Lossless bonus
        if is_lossless and self.profile.prefer_lossless:
            score += 500

        # Bitrate bonus (normalized to 0-320 range)
        if bitrate:
            score += min(bitrate, 320)

        # Size penalty for very large files (diminishing returns)
        if size_mb > 50:
            score -= int((size_mb - 50) * 2)

        return MatchResult(True, score)

    def _detect_format(self, filename: str) -> str | None:
        """Detect audio format from filename extension."""
        extensions = {
            ".flac": "flac",
            ".mp3": "mp3",
            ".m4a": "m4a",
            ".aac": "aac",
            ".ogg": "ogg",
            ".opus": "opus",
            ".wav": "wav",
            ".alac": "alac",
        }

        for ext, fmt in extensions.items():
            if filename.endswith(ext):
                return fmt

        return None

    def rank_results(self, results: list[dict]) -> list[tuple[dict, int]]:
        """Filter and rank search results.

        Args:
            results: List of file_info dicts

        Returns:
            List of (file_info, score) tuples, sorted by score descending
        """
        ranked = []
        for result in results:
            match = self.match(result)
            if match.matches:
                ranked.append((result, match.score))

        # Sort by score descending (best first)
        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked


# =============================================================================
# EXPORTS - System profiles as dict
# =============================================================================
# Hey future me - QUALITY_PROFILES is a dict of system profiles for easy lookup!
# This is imported in __init__.py and used to initialize the database.

QUALITY_PROFILES: dict[str, QualityProfile] = {
    "audiophile": create_audiophile_profile(),
    "balanced": create_balanced_profile(),
    "space_saver": create_space_saver_profile(),
    "any": create_any_quality_profile(),
}
