"""API schemas for metadata management."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# Hey future me, this enum tracks WHERE metadata came from! MANUAL is highest authority (user override),
# then MUSICBRAINZ (official DB), SPOTIFY (streaming service), LASTFM (community data). The order matters
# for conflict resolution - if Spotify says "Rock" but user said "Metal", trust MANUAL! This inherits from
# str so it JSON-serializes nicely. Values are lowercase strings matching external API naming.
class MetadataSourceEnum(str, Enum):
    """Metadata source enumeration."""

    MANUAL = "manual"
    MUSICBRAINZ = "musicbrainz"
    SPOTIFY = "spotify"
    LASTFM = "lastfm"


# Yo, this lets users manually override specific metadata fields! Like "Spotify says genre is Pop but
# I KNOW it's Indie Rock". The field_name is free-form string (track.genre, album.year, etc) - no validation
# that it's a real field! value is Any type so you can set anything - strings, ints, arrays. Source defaults
# to MANUAL which makes sense. This is used in conflict resolution UI - user picks which value to keep.
class MetadataFieldOverride(BaseModel):
    """Schema for manual metadata field override."""

    field_name: str = Field(..., description="Name of the field to override")
    value: Any = Field(..., description="Override value")
    source: MetadataSourceEnum = Field(
        default=MetadataSourceEnum.MANUAL, description="Source of the override"
    )


# Hey future me, this is the KITCHEN SINK request for metadata enrichment! You can toggle EACH source
# (Spotify/MusicBrainz/Last.fm) individually which is useful when one source has bad data. force_refresh
# bypasses cache - normally we don't re-fetch if metadata exists, but this forces it (use when data is
# stale/wrong). enrich_artist/album flags control whether we fetch related entity metadata or just track
# data - performance optimization since artist/album API calls are expensive. manual_overrides is dict of
# field -> value for user corrections. All the bools default to true for "enrich everything" behavior.
class EnrichMetadataMultiSourceRequest(BaseModel):
    """Request schema for multi-source metadata enrichment."""

    track_id: str = Field(..., description="Track ID to enrich")
    force_refresh: bool = Field(
        default=False, description="Force refresh even if metadata exists"
    )
    enrich_artist: bool = Field(default=True, description="Enrich artist metadata")
    enrich_album: bool = Field(default=True, description="Enrich album metadata")
    use_spotify: bool = Field(default=True, description="Use Spotify as a source")
    use_musicbrainz: bool = Field(
        default=True, description="Use MusicBrainz as a source"
    )
    use_lastfm: bool = Field(default=True, description="Use Last.fm as a source")
    manual_overrides: dict[str, Any] | None = Field(
        default=None, description="Manual metadata overrides"
    )


# Listen up, when multiple sources disagree about metadata, we get a CONFLICT! This schema captures the
# disagreement so user can resolve it manually. field_name is like "genre" or "release_year". current_value
# is what we have in DB now (might be from previous enrichment). current_source tracks where that value
# came from. conflicting_values is dict of {SOURCE: value} for all the different opinions. Example: current
# is "Rock" from Spotify, but MusicBrainz says "Alternative" and Last.fm says "Indie" - all three show up!
class MetadataConflict(BaseModel):
    """Schema for metadata conflict information."""

    field_name: str = Field(..., description="Name of the conflicting field")
    current_value: Any = Field(..., description="Current field value")
    current_source: MetadataSourceEnum = Field(..., description="Current value source")
    conflicting_values: dict[MetadataSourceEnum, Any] = Field(
        ..., description="Map of source to conflicting value"
    )


# Yo, this is how user picks the WINNER when metadata sources fight! You specify which entity (track/artist/
# album) has the conflict, which field, and which source's value to use. If you pick MANUAL as selected_source,
# you MUST provide custom_value - that's your override. The three ID fields are all optional because a conflict
# could be on track OR artist OR album - only one will be set. field_name is free text - make sure it matches
# the field from MetadataConflict! This POST request updates DB with chosen value and marks conflict resolved.
class ResolveConflictRequest(BaseModel):
    """Request schema for resolving metadata conflicts."""

    track_id: str | None = Field(default=None, description="Track ID (if applicable)")
    artist_id: str | None = Field(default=None, description="Artist ID (if applicable)")
    album_id: str | None = Field(default=None, description="Album ID (if applicable)")
    field_name: str = Field(..., description="Field name to resolve")
    selected_source: MetadataSourceEnum = Field(
        ..., description="Selected source for resolution"
    )
    custom_value: Any | None = Field(
        default=None, description="Custom value if source is MANUAL"
    )


# Hey future me, the response after enriching metadata! enriched_fields lists what got updated (like
# ["genre", "release_date", "album_art_url"]) so you know what changed. sources_used tells you which APIs
# we hit - useful for debugging ("why is Last.fm data missing? Oh, it wasn't in sources_used!"). conflicts
# is list of MetadataConflict objects if sources disagreed - UI should show these to user for resolution.
# errors catches API failures or validation issues without failing the whole enrichment - partial success
# is OK! Empty lists use default_factory to avoid mutable default gotcha.
class MetadataEnrichmentResponse(BaseModel):
    """Response schema for metadata enrichment."""

    track_id: str = Field(..., description="Track ID")
    enriched_fields: list[str] = Field(..., description="List of enriched fields")
    sources_used: list[str] = Field(..., description="List of sources used")
    conflicts: list[MetadataConflict] = Field(
        default_factory=list, description="Detected metadata conflicts"
    )
    errors: list[str] = Field(
        default_factory=list, description="Any errors encountered"
    )


# Listen, this is for tag cleanup! Like when you have "rock" and "Rock" and "ROCK" - normalization makes
# them all "rock" (lowercase, trimmed, etc). original shows what the tag was before, normalized is the
# cleaned version, changed is true if they differ. This helps dedupe tags and genres. The normalization
# logic (lowercase? titlecase? remove special chars?) lives elsewhere - this just reports the result!
class TagNormalizationResult(BaseModel):
    """Result of tag normalization."""

    original: str = Field(..., description="Original tag value")
    normalized: str = Field(..., description="Normalized tag value")
    changed: bool = Field(..., description="Whether normalization made changes")
