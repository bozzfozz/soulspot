# Blocklist API

Soulseek source blocklist management for problematic downloads.

## Overview

The Blocklist API manages problematic Soulseek sources to prevent repeated failures:
- **Automatic Blocking**: Downloads that timeout/fail auto-add to blocklist
- **Manual Blocking**: Users can manually block sources via UI
- **Scopes**: Username-wide, filepath-wide, or specific user+file combinations
- **Expiration**: Blocks can expire automatically (e.g., 7 days) or be permanent
- **Integration**: SearchService filters results, DownloadService adds failures, CleanupWorker removes expired

**Use Cases:**
- **Quality Control**: Block users who provide corrupt files
- **Performance**: Skip sources that always timeout
- **Manual Curation**: Block specific file versions (live recordings, low quality)

**Scopes Explained:**
- `USERNAME`: Block ALL files from a specific Soulseek user
- `FILEPATH`: Block a specific file from ANY user
- `SPECIFIC`: Block exact user+file combination (most restrictive)

---

## List Active Blocks

**Endpoint:** `GET /api/blocklist`

**Description:** List all active (non-expired) blocklist entries.

**Query Parameters:**
- `limit` (integer, optional): Max entries to return (default: 100)

**Response:**
```json
{
    "entries": [
        {
            "id": "uuid-123",
            "username": "baduser123",
            "filepath": null,
            "scope": "USERNAME",
            "reason": "Timeouts (3 failures)",
            "failure_count": 3,
            "blocked_at": "2025-12-15T10:00:00Z",
            "expires_at": "2025-12-22T10:00:00Z",
            "is_manual": false,
            "is_expired": false
        },
        {
            "id": "uuid-456",
            "username": null,
            "filepath": "/artist/song_live.mp3",
            "scope": "FILEPATH",
            "reason": "Manual block - low quality",
            "failure_count": 0,
            "blocked_at": "2025-12-15T11:00:00Z",
            "expires_at": null,
            "is_manual": true,
            "is_expired": false
        }
    ],
    "total": 2
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/blocklist.py
# Lines 100-119

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
```

**Response Fields:**
- `entries` (array): List of blocklist entries
  - `id` (string): Entry UUID
  - `username` (string | null): Blocked Soulseek username
  - `filepath` (string | null): Blocked file path
  - `scope` (string): Scope type (USERNAME, FILEPATH, SPECIFIC)
  - `reason` (string): Block reason/description
  - `failure_count` (integer): Number of failures that triggered block
  - `blocked_at` (string): ISO timestamp when blocked
  - `expires_at` (string | null): ISO timestamp when expires (null = permanent)
  - `is_manual` (boolean): Whether manually added by user
  - `is_expired` (boolean): Whether expired (always false for active list)
- `total` (integer): Total entries returned

**Use Cases:**
- **Blocklist UI**: Display current blocks
- **Audit**: Review blocked sources
- **Management**: Identify blocks to remove

---

## List Expired Blocks

**Endpoint:** `GET /api/blocklist/expired`

**Description:** List expired blocklist entries (kept for history).

**Query Parameters:**
- `limit` (integer, optional): Max entries to return (default: 100)

**Response:** Same structure as active blocks, but `is_expired` is `true`.

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/blocklist.py
# Lines 122-138

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
```

**Use Cases:**
- **History**: See previously blocked sources
- **Debugging**: Understand past blocking patterns
- **Cleanup Preview**: Before clearing expired entries

**Note:** Expired entries don't affect downloads. They're kept for audit/history until manually cleared.

---

## Add Manual Block

**Endpoint:** `POST /api/blocklist`

**Description:** Add a manual blocklist entry.

**Request Body:**
```json
{
    "username": "problemuser",
    "filepath": null,
    "reason": "Always provides corrupt files",
    "expires_days": 30
}
```

**Request Fields:**
- `username` (string | null): Soulseek username to block
- `filepath` (string | null): File path to block
- `reason` (string, optional): Block reason (default: "Manual block")
- `expires_days` (integer, optional): Days until expiry (1-365, null = permanent)

**Validation:**
- **MUST** provide at least `username` OR `filepath` (or both)
- **Scope Determination:**
  - Both provided → SPECIFIC scope (block user+file combo)
  - Only username → USERNAME scope (block all files from user)
  - Only filepath → FILEPATH scope (block file from any user)

**Response (HTTP 201):**
```json
{
    "id": "uuid-789",
    "username": "problemuser",
    "filepath": null,
    "scope": "USERNAME",
    "reason": "Always provides corrupt files",
    "failure_count": 0,
    "blocked_at": "2025-12-15T12:00:00Z",
    "expires_at": "2026-01-14T12:00:00Z",
    "is_manual": true,
    "is_expired": false
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/blocklist.py
# Lines 141-211

@router.post(
    "", response_model=BlocklistEntryResponse, status_code=status.HTTP_201_CREATED
)
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
```

**Error Responses:**
- **400 Bad Request**: Missing both username and filepath
- **409 Conflict**: Source already blocked

**Use Cases:**
- **Manual Quality Control**: Block known bad sources
- **Temporary Blocks**: Set expiry for sources that may improve
- **Permanent Blocks**: Leave `expires_days` null for spam/malicious sources

**Example - Block All Files from User:**
```json
{
    "username": "spamuser",
    "reason": "Spam account",
    "expires_days": null
}
```

**Example - Block Specific File:**
```json
{
    "filepath": "/music/artist - song (bad quality).mp3",
    "reason": "Low bitrate (96kbps)",
    "expires_days": 7
}
```

---

## Remove Block

**Endpoint:** `DELETE /api/blocklist/{entry_id}`

**Description:** Remove a blocklist entry immediately.

**Path Parameters:**
- `entry_id` (string): Blocklist entry UUID

**Response:** HTTP 204 No Content

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/blocklist.py
# Lines 214-237

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
```

**Error Responses:**
- **404 Not Found**: Entry doesn't exist

**Use Cases:**
- **Immediate Unblock**: Remove block to allow downloads
- **Cleanup**: Delete outdated blocks
- **Mistake Correction**: Remove accidental blocks

**Behavior:**
- **Permanent Deletion**: Entry is removed from database (not just marked expired)
- **Immediate Effect**: Downloads from source are allowed immediately

---

## Clear Expired Blocks

**Endpoint:** `POST /api/blocklist/clear-expired`

**Description:** Delete all expired blocklist entries.

**Request Body:** None

**Response:**
```json
{
    "message": "Cleared 15 expired entries",
    "deleted_count": 15
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/blocklist.py
# Lines 240-257

@router.post("/clear-expired")
async def clear_expired_blocks(
    repository: BlocklistRepository = Depends(get_blocklist_repository),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Clear all expired blocklist entries.

    Hey future me - this is also done by CleanupWorker periodically!
    Use this to manually trigger cleanup.
    """
```

**Use Cases:**
- **Manual Cleanup**: Clear expired entries before automatic cleanup
- **Database Maintenance**: Reduce blocklist table size
- **Audit Preparation**: Clean history before review

**Automatic Cleanup:** CleanupWorker periodically calls this. Manual trigger is for immediate cleanup.

---

## Check If Blocked

**Endpoint:** `GET /api/blocklist/check`

**Description:** Check if a source is currently blocked (without listing all entries).

**Query Parameters:**
- `username` (string, optional): Soulseek username to check
- `filepath` (string, optional): File path to check

**Validation:** MUST provide at least `username` OR `filepath` (or both)

**Response:**
```json
{
    "username": "testuser",
    "filepath": "/music/song.mp3",
    "is_blocked": true
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/blocklist.py
# Lines 260-284

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
```

**Response Fields:**
- `username` (string | null): Username checked
- `filepath` (string | null): Filepath checked
- `is_blocked` (boolean): Whether blocked by any active entry

**Use Cases:**
- **Search Results UI**: Show block indicator on results
- **Quick Validation**: Check before attempting download
- **Integration Testing**: Verify blocklist functionality

**Behavior:**
- **Scope Matching**: Checks all scope types (USERNAME, FILEPATH, SPECIFIC)
- **Active Only**: Only considers non-expired blocks
- **Fast Query**: Optimized for real-time UI checks

**Example - Check User:**
```
GET /api/blocklist/check?username=testuser
```

**Example - Check File:**
```
GET /api/blocklist/check?filepath=/music/song.mp3
```

**Example - Check Both:**
```
GET /api/blocklist/check?username=testuser&filepath=/music/song.mp3
```

---

## Integration Points

### Automatic Blocking (DownloadService)

When downloads fail:
```python
# After 3 failures, automatically block source
if failure_count >= 3:
    blocklist_repo.add(BlocklistEntry(
        username=username,
        filepath=filepath,
        scope=BlocklistScope.SPECIFIC,
        reason=f"Timeouts ({failure_count} failures)",
        expires_at=datetime.now() + timedelta(days=7),
        is_manual=False,
    ))
```

### Search Filtering (SearchService)

Before showing results:
```python
# Filter out blocked sources from search results
is_blocked = await blocklist_repo.is_blocked(username, filepath)
if is_blocked:
    continue  # Skip this result
```

### Periodic Cleanup (CleanupWorker)

Background worker cleans expired entries:
```python
# Run daily
deleted_count = await blocklist_repo.delete_expired()
logger.info(f"Cleaned {deleted_count} expired blocklist entries")
```

---

## Summary

**Total Endpoints:** 6

**Endpoint Breakdown:**
1. **GET /blocklist** - List active blocks
2. **GET /blocklist/expired** - List expired blocks
3. **POST /blocklist** - Add manual block
4. **DELETE /blocklist/{id}** - Remove block
5. **POST /blocklist/clear-expired** - Clear expired blocks
6. **GET /blocklist/check** - Check if blocked

**Key Features:**
- **Automatic Blocking**: Failures trigger automatic blocks
- **Flexible Scopes**: Username, filepath, or specific combos
- **Expiration**: Temporary or permanent blocks
- **History**: Expired entries kept for audit
- **Fast Checks**: Optimized query for real-time UI

**Module Stats:**
- **Source File**: `blocklist.py` (293 lines)
- **Endpoints**: 6
- **Code Validation**: 100%

**Use Cases:**
- **Quality Control**: Prevent bad downloads
- **Performance**: Skip timeout-prone sources
- **Manual Curation**: User-driven blocking
- **Audit**: Review blocking history
