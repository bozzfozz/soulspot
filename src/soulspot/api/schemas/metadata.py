"""API schemas for metadata management."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MetadataSourceEnum(str, Enum):
    """Metadata source enumeration."""

    MANUAL = "manual"
    MUSICBRAINZ = "musicbrainz"
    SPOTIFY = "spotify"
    LASTFM = "lastfm"


class MetadataFieldOverride(BaseModel):
    """Schema for manual metadata field override."""

    field_name: str = Field(..., description="Name of the field to override")
    value: Any = Field(..., description="Override value")
    source: MetadataSourceEnum = Field(
        default=MetadataSourceEnum.MANUAL, description="Source of the override"
    )


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


class MetadataConflict(BaseModel):
    """Schema for metadata conflict information."""

    field_name: str = Field(..., description="Name of the conflicting field")
    current_value: Any = Field(..., description="Current field value")
    current_source: MetadataSourceEnum = Field(..., description="Current value source")
    conflicting_values: dict[MetadataSourceEnum, Any] = Field(
        ..., description="Map of source to conflicting value"
    )


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


class TagNormalizationResult(BaseModel):
    """Result of tag normalization."""

    original: str = Field(..., description="Original tag value")
    normalized: str = Field(..., description="Normalized tag value")
    changed: bool = Field(..., description="Whether normalization made changes")
