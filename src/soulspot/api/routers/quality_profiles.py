"""Quality Profile API endpoints.

Hey future me - this router manages Quality Profiles for download preferences!

Quality profiles define:
- Preferred audio formats (FLAC > MP3 > AAC)
- Bitrate constraints (min 192kbps, max 320kbps)
- File size limits (max 50MB)
- Exclude keywords (skip "live", "demo")

ENDPOINTS:
- GET  /quality-profiles          → List all profiles
- GET  /quality-profiles/{id}     → Get profile details
- GET  /quality-profiles/active   → Get currently active profile
- POST /quality-profiles          → Create new profile
- PUT  /quality-profiles/{id}     → Update profile
- PUT  /quality-profiles/{id}/activate → Set as active
- DELETE /quality-profiles/{id}   → Delete profile (not builtin/active)

INTEGRATION:
- Used by PostProcessingWorker for quality validation
- Used by DownloadService for search result filtering/scoring
- Active profile ID stored in app_settings for quick access
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.domain.entities import AudioFormat, QualityProfile, QUALITY_PROFILES
from soulspot.infrastructure.persistence.repositories import QualityProfileRepository

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================
# Hey future me - these are API schemas, NOT domain entities!
# They define what the API accepts/returns, with validation.


class QualityProfileCreate(BaseModel):
    """Schema for creating a new quality profile."""

    name: str = Field(min_length=1, max_length=100, description="Profile name")
    description: str | None = Field(default=None, description="Profile description")
    preferred_formats: list[str] = Field(
        default_factory=lambda: ["flac", "mp3"],
        description="Preferred formats in priority order (e.g., ['flac', 'mp3', 'aac'])",
    )
    min_bitrate: int | None = Field(
        default=None, ge=0, le=9999, description="Minimum bitrate in kbps"
    )
    max_bitrate: int | None = Field(
        default=None, ge=0, le=9999, description="Maximum bitrate in kbps"
    )
    max_file_size_mb: int | None = Field(
        default=None, ge=0, le=9999, description="Maximum file size in MB"
    )
    exclude_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to exclude from search results (e.g., ['live', 'demo'])",
    )


class QualityProfileUpdate(BaseModel):
    """Schema for updating a quality profile."""

    name: str | None = Field(
        default=None, min_length=1, max_length=100, description="Profile name"
    )
    description: str | None = Field(default=None, description="Profile description")
    preferred_formats: list[str] | None = Field(
        default=None,
        description="Preferred formats in priority order",
    )
    min_bitrate: int | None = Field(
        default=None, ge=0, le=9999, description="Minimum bitrate in kbps"
    )
    max_bitrate: int | None = Field(
        default=None, ge=0, le=9999, description="Maximum bitrate in kbps"
    )
    max_file_size_mb: int | None = Field(
        default=None, ge=0, le=9999, description="Maximum file size in MB"
    )
    exclude_keywords: list[str] | None = Field(
        default=None,
        description="Keywords to exclude from search results",
    )


class QualityProfileResponse(BaseModel):
    """Schema for quality profile API responses."""

    id: str
    name: str
    description: str | None
    preferred_formats: list[str]
    min_bitrate: int | None
    max_bitrate: int | None
    max_file_size_mb: int | None
    exclude_keywords: list[str]
    is_active: bool
    is_builtin: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, profile: QualityProfile) -> "QualityProfileResponse":
        """Convert domain entity to API response."""
        return cls(
            id=profile.id,
            name=profile.name,
            description=profile.description,
            preferred_formats=profile.preferred_formats,
            min_bitrate=profile.min_bitrate,
            max_bitrate=profile.max_bitrate,
            max_file_size_mb=profile.max_file_size_mb,
            exclude_keywords=profile.exclude_keywords,
            is_active=profile.is_default,
            is_builtin=profile.is_system,
            created_at=profile.created_at.isoformat(),
            updated_at=(profile.updated_at or profile.created_at).isoformat(),
        )


class QualityProfileListResponse(BaseModel):
    """Schema for listing quality profiles."""

    profiles: list[QualityProfileResponse]
    total: int
    active_id: str | None = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _validate_formats(format_strings: list[str]) -> list[str]:
    """Validate and normalize format strings.

    Hey future me - we keep formats as plain strings in the domain entity
    (e.g. "flac"), but we still want strict validation against AudioFormat.
    """
    normalized: list[str] = []
    for fmt in format_strings:
        try:
            normalized.append(AudioFormat(fmt.lower()).value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid audio format: {fmt}. "
                    f"Valid formats: {[af.value for af in AudioFormat]}"
                ),
            )
    return normalized


# =============================================================================
# API ENDPOINTS
# =============================================================================


@router.get("", response_model=QualityProfileListResponse)
async def list_quality_profiles(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> QualityProfileListResponse:
    """List all quality profiles.

    Hey future me - returns all profiles with active profile highlighted!
    """
    repo = QualityProfileRepository(session)

    # Ensure defaults exist on first access
    await repo.ensure_defaults_exist()
    await session.commit()

    profiles = await repo.list_all()
    active = await repo.get_active()

    return QualityProfileListResponse(
        profiles=[QualityProfileResponse.from_entity(p) for p in profiles],
        total=len(profiles),
        active_id=active.id if active else None,
    )


@router.get("/active", response_model=QualityProfileResponse | None)
async def get_active_profile(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> QualityProfileResponse | None:
    """Get the currently active quality profile.

    Hey future me - returns None if no profile is active!
    """
    repo = QualityProfileRepository(session)

    # Ensure defaults exist
    await repo.ensure_defaults_exist()
    await session.commit()

    active = await repo.get_active()
    if not active:
        return None

    return QualityProfileResponse.from_entity(active)


@router.get("/{profile_id}", response_model=QualityProfileResponse)
async def get_quality_profile(
    profile_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> QualityProfileResponse:
    """Get a quality profile by ID.

    Hey future me - 404 if not found!
    """
    repo = QualityProfileRepository(session)
    profile = await repo.get_by_id(profile_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality profile not found: {profile_id}",
        )

    return QualityProfileResponse.from_entity(profile)


@router.post("", response_model=QualityProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_quality_profile(
    data: QualityProfileCreate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> QualityProfileResponse:
    """Create a new quality profile.

    Hey future me - validates formats before creating!
    """
    repo = QualityProfileRepository(session)

    # Check for duplicate name
    existing = await repo.get_by_name(data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Quality profile with name '{data.name}' already exists",
        )

    # Validate formats
    formats = _validate_formats(data.preferred_formats)

    # Create entity
    profile = QualityProfile(
        name=data.name,
        description=data.description,
        preferred_formats=formats,
        min_bitrate=data.min_bitrate,
        max_bitrate=data.max_bitrate,
        max_file_size_mb=data.max_file_size_mb,
        exclude_keywords=data.exclude_keywords,
        is_default=False,
        is_system=False,
    )

    await repo.add(profile)
    await session.commit()

    logger.info(f"Created quality profile: {profile.name}")
    return QualityProfileResponse.from_entity(profile)


@router.put("/{profile_id}", response_model=QualityProfileResponse)
async def update_quality_profile(
    profile_id: str,
    data: QualityProfileUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> QualityProfileResponse:
    """Update a quality profile.

    Hey future me - can't update builtin profile names!
    """
    repo = QualityProfileRepository(session)
    profile = await repo.get_by_id(profile_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality profile not found: {profile_id}",
        )

    # Protect builtin profile names
    if profile.is_system and data.name and data.name != profile.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rename built-in profiles",
        )

    # Update fields if provided
    if data.name is not None:
        # Check for duplicate name
        existing = await repo.get_by_name(data.name)
        if existing and existing.id != profile_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Quality profile with name '{data.name}' already exists",
            )
        profile.name = data.name

    if data.description is not None:
        profile.description = data.description

    if data.preferred_formats is not None:
        profile.preferred_formats = _validate_formats(data.preferred_formats)

    if data.min_bitrate is not None:
        profile.min_bitrate = data.min_bitrate

    if data.max_bitrate is not None:
        profile.max_bitrate = data.max_bitrate

    if data.max_file_size_mb is not None:
        profile.max_file_size_mb = data.max_file_size_mb

    if data.exclude_keywords is not None:
        profile.exclude_keywords = data.exclude_keywords

    await repo.update(profile)
    await session.commit()

    logger.info(f"Updated quality profile: {profile.name}")
    return QualityProfileResponse.from_entity(profile)


@router.put("/{profile_id}/activate", response_model=QualityProfileResponse)
async def activate_quality_profile(
    profile_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> QualityProfileResponse:
    """Set a quality profile as the active one.

    Hey future me - deactivates all other profiles first!
    """
    repo = QualityProfileRepository(session)
    profile = await repo.get_by_id(profile_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality profile not found: {profile_id}",
        )

    await repo.set_active(profile_id)
    await session.commit()

    # Reload to get updated state
    profile = await repo.get_by_id(profile_id)

    logger.info(f"Activated quality profile: {profile.name}")
    return QualityProfileResponse.from_entity(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quality_profile(
    profile_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a quality profile.

    Hey future me - can't delete active or builtin profiles!
    """
    repo = QualityProfileRepository(session)
    profile = await repo.get_by_id(profile_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality profile not found: {profile_id}",
        )

    if profile.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the active quality profile. Activate another profile first.",
        )

    if profile.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete built-in profiles",
        )

    await repo.delete(profile_id)
    await session.commit()

    logger.info(f"Deleted quality profile: {profile.name}")


# =============================================================================
# AVAILABLE FORMATS ENDPOINT
# =============================================================================


@router.get("/formats/available", response_model=list[dict[str, str]])
async def get_available_formats(
    request: Request,
) -> list[dict[str, str]]:
    """Get list of supported audio formats.

    Hey future me - useful for populating format dropdown in UI!
    """
    formats = [
        {"value": af.value, "label": af.value.upper(), "lossless": af.value in ("flac", "alac", "wav")}
        for af in AudioFormat
    ]
    return formats


# =============================================================================
# DEFAULT PROFILES INFO
# =============================================================================


@router.get("/defaults/info", response_model=dict[str, Any])
async def get_default_profiles_info(
    request: Request,
) -> dict[str, Any]:
    """Get information about default/builtin profiles.

    Hey future me - useful for UI to show profile descriptions!
    Returns the predefined profiles (AUDIOPHILE, BALANCED, SPACE_SAVER).
    """
    return {
        "profiles": {
            name: {
                "name": profile.name,
                "description": profile.description,
                "preferred_formats": profile.preferred_formats,
                "min_bitrate": profile.min_bitrate,
                "max_bitrate": profile.max_bitrate,
                "max_file_size_mb": profile.max_file_size_mb,
                "exclude_keywords": profile.exclude_keywords,
            }
            for name, profile in QUALITY_PROFILES.items()
        },
        "count": len(QUALITY_PROFILES),
    }
