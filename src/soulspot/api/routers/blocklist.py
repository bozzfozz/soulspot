"""Blocklist API endpoints.

Hey future me - this router manages the Soulseek source blocklist!

The blocklist prevents downloads from problematic sources:
- Users who timeout or provide corrupt files
- Specific files that always fail
- Manually blocked sources

ENDPOINTS:
- GET  /blocklist              → List active blocks
- GET  /blocklist/expired      → List expired blocks
- POST /blocklist              → Add manual block
- DELETE /blocklist/{id}       → Remove block
- POST /blocklist/clear-expired → Clear expired entries

SCOPES:
- USERNAME: Block all files from a user
- FILEPATH: Block a specific file from anyone
- SPECIFIC: Block exact user+file combination

INTEGRATION:
- Used by: SearchService to filter results
- Auto-populated by: DownloadService on failures
- Expired entries cleaned by: CleanupWorker
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.domain.entities import BlocklistEntry, BlocklistScope
from soulspot.infrastructure.persistence.repositories import BlocklistRepository

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================


class BlocklistEntryCreate(BaseModel):
    """Schema for creating a blocklist entry."""

    username: str | None = Field(default=None, description="Soulseek username to block")
    filepath: str | None = Field(default=None, description="File path to block")
    reason: str | None = Field(
        default="Manual block", description="Reason for blocking"
    )
    expires_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Days until expiry (null = permanent)",
    )


class BlocklistEntryResponse(BaseModel):
    """Schema for blocklist entry API responses."""

    id: str
    username: str | None
    filepath: str | None
    scope: str
    reason: str | None
    failure_count: int
    blocked_at: datetime
    expires_at: datetime | None
    is_manual: bool
    is_expired: bool


class BlocklistListResponse(BaseModel):
    """Schema for blocklist list API responses."""

    entries: list[BlocklistEntryResponse]
    total: int


# =============================================================================
# DEPENDENCY
# =============================================================================


async def get_blocklist_repository(
    session: AsyncSession = Depends(get_db_session),
) -> BlocklistRepository:
    """Get blocklist repository dependency."""
    return BlocklistRepository(session)


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("", response_model=BlocklistListResponse)
async def list_active_blocks(
    limit: int = 100,
    repository: BlocklistRepository = Depends(get_blocklist_repository),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List all active (non-expired) blocklist entries.

    Hey future me - this is what the Blocklist UI calls!
    Returns active blocks sorted by most recent first.
    """
    entries = await repository.list_active(limit=limit)
    await session.commit()

    return {
        "entries": [_entry_to_response(e) for e in entries],
        "total": len(entries),
    }


@router.get("/expired", response_model=BlocklistListResponse)
async def list_expired_blocks(
    limit: int = 100,
    repository: BlocklistRepository = Depends(get_blocklist_repository),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List expired blocklist entries.

    These entries no longer affect downloads but are kept for history.
    CleanupWorker can remove old expired entries.
    """
    entries = await repository.list_expired(limit=limit)
    await session.commit()

    return {
        "entries": [_entry_to_response(e) for e in entries],
        "total": len(entries),
    }


@router.post("", response_model=BlocklistEntryResponse, status_code=status.HTTP_201_CREATED)
async def add_block(
    data: BlocklistEntryCreate,
    repository: BlocklistRepository = Depends(get_blocklist_repository),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Add a manual blocklist entry.

    Hey future me - this is for manually blocking problematic sources!

    Must provide at least username OR filepath:
    - username only → Blocks all files from user (USERNAME scope)
    - filepath only → Blocks file from anyone (FILEPATH scope)
    - both → Blocks specific user+file combo (SPECIFIC scope)
    """
    if not data.username and not data.filepath:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide username or filepath (or both)",
        )

    # Check if already blocked
    existing = await repository.get_by_source(data.username, data.filepath)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This source is already blocked",
        )

    # Determine scope
    if data.username and data.filepath:
        scope = BlocklistScope.SPECIFIC
    elif data.username:
        scope = BlocklistScope.USERNAME
    else:
        scope = BlocklistScope.FILEPATH

    # Calculate expiry
    expires_at = None
    if data.expires_days:
        expires_at = datetime.now(UTC) + timedelta(days=data.expires_days)

    # Create entry
    import uuid

    entry = BlocklistEntry(
        id=str(uuid.uuid4()),
        username=data.username,
        filepath=data.filepath,
        scope=scope,
        reason=data.reason or "Manual block",
        failure_count=0,
        blocked_at=datetime.now(UTC),
        expires_at=expires_at,
        is_manual=True,
    )

    await repository.add(entry)
    await session.commit()

    logger.info(f"Manual block added: {data.username or 'N/A'} / {data.filepath or 'N/A'}")

    return _entry_to_response(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_block(
    entry_id: str,
    repository: BlocklistRepository = Depends(get_blocklist_repository),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a blocklist entry.

    Hey future me - this DELETES the entry, doesn't just expire it!
    Use this when you want to immediately unblock a source.
    """
    entry = await repository.get_by_id(entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blocklist entry not found",
        )

    await repository.delete(entry_id)
    await session.commit()

    logger.info(f"Block removed: {entry.username or 'N/A'} / {entry.filepath or 'N/A'}")


@router.post("/clear-expired")
async def clear_expired_blocks(
    repository: BlocklistRepository = Depends(get_blocklist_repository),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Clear all expired blocklist entries.

    Hey future me - this is also done by CleanupWorker periodically!
    Use this to manually trigger cleanup.
    """
    deleted_count = await repository.delete_expired()
    await session.commit()

    logger.info(f"Cleared {deleted_count} expired blocklist entries")

    return {
        "message": f"Cleared {deleted_count} expired entries",
        "deleted_count": deleted_count,
    }


@router.get("/check")
async def check_if_blocked(
    username: str | None = None,
    filepath: str | None = None,
    repository: BlocklistRepository = Depends(get_blocklist_repository),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Check if a source is currently blocked.

    Hey future me - quick check without listing all entries!
    Useful for UI to show block status on search results.
    """
    if not username and not filepath:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide username or filepath (or both)",
        )

    is_blocked = await repository.is_blocked(username, filepath)
    await session.commit()

    return {
        "username": username,
        "filepath": filepath,
        "is_blocked": is_blocked,
    }


# =============================================================================
# HELPERS
# =============================================================================


def _entry_to_response(entry: BlocklistEntry) -> dict[str, Any]:
    """Convert BlocklistEntry entity to API response."""
    now = datetime.now(UTC)
    is_expired = entry.expires_at is not None and entry.expires_at <= now

    return {
        "id": entry.id,
        "username": entry.username,
        "filepath": entry.filepath,
        "scope": entry.scope.value,
        "reason": entry.reason,
        "failure_count": entry.failure_count,
        "blocked_at": entry.blocked_at,
        "expires_at": entry.expires_at,
        "is_manual": entry.is_manual,
        "is_expired": is_expired,
    }
