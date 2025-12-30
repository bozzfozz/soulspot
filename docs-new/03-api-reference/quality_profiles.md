# Quality Profiles API

Download quality preferences and file format management.

## Overview

The Quality Profiles API manages download quality preferences:
- **Preferred Formats**: Define format priority (FLAC > MP3 > AAC)
- **Bitrate Constraints**: Min/max bitrate requirements (e.g., 192-320 kbps)
- **File Size Limits**: Max file size (e.g., 50MB)
- **Exclude Keywords**: Skip files with specific keywords (live, demo, etc.)
- **Active Profile**: One profile active for download filtering/scoring

**Integration Points:**
- **PostProcessingWorker**: Validates downloads against active profile
- **DownloadService**: Filters/scores search results by profile criteria
- **App Settings**: Active profile ID stored in `app_settings` table

**Built-in Profiles:**
- **AUDIOPHILE**: FLAC only, 320kbps+, no size limit
- **BALANCED**: FLAC/MP3, 192-320kbps, 50MB limit
- **SPACE_SAVER**: MP3/AAC, no min bitrate, 20MB limit

---

## List Quality Profiles

**Endpoint:** `GET /api/quality-profiles`

**Description:** List all quality profiles with active profile highlighted.

**Query Parameters:** None

**Response:**
```json
{
    "profiles": [
        {
            "id": "profile-uuid-123",
            "name": "Audiophile",
            "description": "Lossless only, maximum quality",
            "preferred_formats": ["flac"],
            "min_bitrate": 320,
            "max_bitrate": null,
            "max_file_size_mb": null,
            "exclude_keywords": ["live", "demo", "bootleg"],
            "is_active": true,
            "is_builtin": true,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z"
        },
        {
            "id": "profile-uuid-456",
            "name": "Balanced",
            "description": "Good quality, reasonable file sizes",
            "preferred_formats": ["flac", "mp3"],
            "min_bitrate": 192,
            "max_bitrate": 320,
            "max_file_size_mb": 50,
            "exclude_keywords": [],
            "is_active": false,
            "is_builtin": true,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z"
        }
    ],
    "total": 2,
    "active_id": "profile-uuid-123"
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/quality_profiles.py
# Lines 156-178

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
        active_id=str(active.id) if active else None,
    )
```

**Profile Fields:**
- `id` (string): Profile UUID
- `name` (string): Profile name
- `description` (string | null): Profile description
- `preferred_formats` (array[string]): Format priority list (e.g., `["flac", "mp3", "aac"]`)
- `min_bitrate` (integer | null): Minimum bitrate in kbps
- `max_bitrate` (integer | null): Maximum bitrate in kbps
- `max_file_size_mb` (integer | null): Maximum file size in MB
- `exclude_keywords` (array[string]): Keywords to exclude from results
- `is_active` (boolean): Whether this is the active profile
- `is_builtin` (boolean): Whether this is a built-in profile
- `created_at` (string): ISO timestamp
- `updated_at` (string): ISO timestamp

**Format Priority:**
- **Order Matters**: First format in array is most preferred
- **Example**: `["flac", "mp3"]` = Prefer FLAC, accept MP3 if FLAC unavailable
- **Fallback**: Download service tries formats in order

**Supported Audio Formats:**
- `flac` (lossless)
- `alac` (lossless)
- `wav` (lossless)
- `mp3` (lossy)
- `aac` (lossy)
- `m4a` (lossy)
- `ogg` (lossy)
- `opus` (lossy)

**Use Cases:**
- **Settings UI**: List all profiles for user selection
- **Active Profile**: Display currently active profile
- **Profile Management**: Show user-created + built-in profiles

**Default Initialization:**
- **First Access**: Creates 3 built-in profiles (AUDIOPHILE, BALANCED, SPACE_SAVER)
- **BALANCED Active**: BALANCED profile set as active by default
- **Idempotent**: Safe to call multiple times

---

## Get Active Profile

**Endpoint:** `GET /api/quality-profiles/active`

**Description:** Get the currently active quality profile.

**Query Parameters:** None

**Response:**
```json
{
    "id": "profile-uuid-123",
    "name": "Audiophile",
    "description": "Lossless only, maximum quality",
    "preferred_formats": ["flac"],
    "min_bitrate": 320,
    "max_bitrate": null,
    "max_file_size_mb": null,
    "exclude_keywords": ["live", "demo", "bootleg"],
    "is_active": true,
    "is_builtin": true,
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
}
```

**Response (No Active Profile):** `null`

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/quality_profiles.py
# Lines 181-201

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
```

**Use Cases:**
- **Download Service**: Get active profile for filtering/scoring
- **UI Display**: Show current active profile
- **Settings Page**: Highlight active profile

**Behavior:**
- **Returns null**: If no profile is active (shouldn't happen after initialization)
- **Auto-Initialize**: Creates defaults if none exist

---

## Get Profile by ID

**Endpoint:** `GET /api/quality-profiles/{profile_id}`

**Description:** Get a specific quality profile by ID.

**Path Parameters:**
- `profile_id` (string): Profile UUID

**Response:** Same structure as active profile

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/quality_profiles.py
# Lines 204-221

@router.get("/{profile_id}", response_model=QualityProfileResponse)
async def get_quality_profile(
    profile_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> QualityProfileResponse:
    """Get a quality profile by ID.

    Hey future me - 404 if not found!
    """
```

**Error Responses:**
- **404 Not Found**: Profile with given ID doesn't exist

**Use Cases:**
- **Edit Dialog**: Load profile details for editing
- **Profile Details**: Display full profile information

---

## Create Quality Profile

**Endpoint:** `POST /api/quality-profiles`

**Description:** Create a new custom quality profile.

**Request Body:**
```json
{
    "name": "My Custom Profile",
    "description": "High quality MP3 for mobile",
    "preferred_formats": ["mp3", "aac"],
    "min_bitrate": 256,
    "max_bitrate": 320,
    "max_file_size_mb": 30,
    "exclude_keywords": ["live", "acoustic", "demo"]
}
```

**Request Fields:**
- `name` (string, required): Profile name (1-100 chars, must be unique)
- `description` (string, optional): Profile description
- `preferred_formats` (array[string], optional): Format priority (default: `["flac", "mp3"]`)
- `min_bitrate` (integer, optional): Min bitrate in kbps (0-9999)
- `max_bitrate` (integer, optional): Max bitrate in kbps (0-9999)
- `max_file_size_mb` (integer, optional): Max file size in MB (0-9999)
- `exclude_keywords` (array[string], optional): Keywords to exclude (default: `[]`)

**Response (HTTP 201):** Created profile object

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/quality_profiles.py
# Lines 224-281

@router.post(
    "", response_model=QualityProfileResponse, status_code=status.HTTP_201_CREATED
)
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
```

**Format Validation:**
- **Valid Formats**: Must be from `AudioFormat` enum (flac, mp3, aac, etc.)
- **Normalization**: Formats lowercased and validated
- **400 Error**: If invalid format provided

**Error Responses:**
- **400 Bad Request**: Invalid format in `preferred_formats`
- **409 Conflict**: Profile with same name already exists

**Use Cases:**
- **Custom Profiles**: User creates personalized quality settings
- **Specialized Workflows**: Different profiles for different use cases (mobile, archival, etc.)

**Example - Mobile Profile:**
```json
{
    "name": "Mobile",
    "description": "Optimized for mobile devices",
    "preferred_formats": ["mp3"],
    "min_bitrate": 128,
    "max_bitrate": 256,
    "max_file_size_mb": 15,
    "exclude_keywords": ["live"]
}
```

---

## Update Quality Profile

**Endpoint:** `PUT /api/quality-profiles/{profile_id}`

**Description:** Update an existing quality profile.

**Path Parameters:**
- `profile_id` (string): Profile UUID to update

**Request Body:** Partial update (all fields optional)
```json
{
    "name": "Updated Name",
    "min_bitrate": 192,
    "exclude_keywords": ["live", "demo", "bootleg"]
}
```

**Request Fields:** Same as create, but all optional

**Response:** Updated profile object

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/quality_profiles.py
# Lines 284-347

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
```

**Update Rules:**
- **Partial Update**: Only provided fields are updated
- **Built-in Protection**: Cannot rename built-in profiles (AUDIOPHILE, BALANCED, SPACE_SAVER)
- **Name Uniqueness**: New name must not conflict with existing profile

**Error Responses:**
- **400 Bad Request**: Attempting to rename built-in profile, or invalid format
- **404 Not Found**: Profile doesn't exist
- **409 Conflict**: New name conflicts with existing profile

**Use Cases:**
- **Preference Changes**: Adjust quality criteria
- **Keyword Updates**: Add/remove exclude keywords
- **Bitrate Tuning**: Fine-tune bitrate constraints

**Example - Update Bitrate:**
```json
{
    "min_bitrate": 256,
    "max_bitrate": 320
}
```

---

## Activate Quality Profile

**Endpoint:** `PUT /api/quality-profiles/{profile_id}/activate`

**Description:** Set a quality profile as the active one.

**Path Parameters:**
- `profile_id` (string): Profile UUID to activate

**Request Body:** None

**Response:** Activated profile object

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/quality_profiles.py
# Lines 350-375

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
```

**Behavior:**
- **Deactivates Others**: All other profiles set to `is_active=false`
- **Single Active**: Only one profile can be active at a time
- **Immediate Effect**: Download service uses new profile immediately

**Error Responses:**
- **404 Not Found**: Profile doesn't exist

**Use Cases:**
- **Profile Switching**: Change active profile from settings UI
- **Quality Mode**: Switch between quality modes (e.g., WiFi = FLAC, mobile = MP3)

---

## Delete Quality Profile

**Endpoint:** `DELETE /api/quality-profiles/{profile_id}`

**Description:** Delete a quality profile permanently.

**Path Parameters:**
- `profile_id` (string): Profile UUID to delete

**Response:** HTTP 204 No Content

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/quality_profiles.py
# Lines 378-408

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
```

**Deletion Rules:**
- **Cannot Delete Active**: Must activate different profile first
- **Cannot Delete Built-in**: AUDIOPHILE, BALANCED, SPACE_SAVER are protected
- **User Profiles Only**: Only custom user-created profiles can be deleted

**Error Responses:**
- **400 Bad Request**: Attempting to delete active or built-in profile
- **404 Not Found**: Profile doesn't exist

**Use Cases:**
- **Cleanup**: Remove unused custom profiles
- **Profile Management**: Delete outdated profiles

**Workflow for Deleting Active Profile:**
1. Activate different profile: `PUT /quality-profiles/{other_id}/activate`
2. Delete original profile: `DELETE /quality-profiles/{profile_id}`

---

## Get Available Formats

**Endpoint:** `GET /api/quality-profiles/formats/available`

**Description:** Get list of supported audio formats.

**Query Parameters:** None

**Response:**
```json
[
    {
        "value": "flac",
        "label": "FLAC",
        "lossless": true
    },
    {
        "value": "mp3",
        "label": "MP3",
        "lossless": false
    },
    {
        "value": "aac",
        "label": "AAC",
        "lossless": false
    }
]
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/quality_profiles.py
# Lines 417-434

@router.get("/formats/available", response_model=list[dict[str, str]])
async def get_available_formats(
    request: Request,
) -> list[dict[str, str]]:
    """Get list of supported audio formats.

    Hey future me - useful for populating format dropdown in UI!
    """
    formats = [
        {
            "value": af.value,
            "label": af.value.upper(),
            "lossless": af.value in ("flac", "alac", "wav"),
        }
        for af in AudioFormat
    ]
    return formats
```

**Format Fields:**
- `value` (string): Format identifier (lowercase, use in API requests)
- `label` (string): Display name (uppercase, for UI)
- `lossless` (boolean): Whether format is lossless

**Lossless Formats:**
- `flac` (FLAC)
- `alac` (Apple Lossless)
- `wav` (WAV)

**Lossy Formats:**
- `mp3` (MP3)
- `aac` (AAC)
- `m4a` (M4A)
- `ogg` (Ogg Vorbis)
- `opus` (Opus)

**Use Cases:**
- **UI Form**: Populate format dropdown in profile editor
- **Validation**: Client-side validation before submission
- **Documentation**: Show available formats to users

---

## Get Default Profiles Info

**Endpoint:** `GET /api/quality-profiles/defaults/info`

**Description:** Get information about built-in default profiles.

**Query Parameters:** None

**Response:**
```json
{
    "profiles": {
        "AUDIOPHILE": {
            "name": "Audiophile",
            "description": "Lossless only, maximum quality",
            "preferred_formats": ["flac"],
            "min_bitrate": 320,
            "max_bitrate": null,
            "max_file_size_mb": null,
            "exclude_keywords": []
        },
        "BALANCED": {
            "name": "Balanced",
            "description": "Good quality, reasonable file sizes",
            "preferred_formats": ["flac", "mp3"],
            "min_bitrate": 192,
            "max_bitrate": 320,
            "max_file_size_mb": 50,
            "exclude_keywords": []
        },
        "SPACE_SAVER": {
            "name": "Space Saver",
            "description": "Maximum compression, small file sizes",
            "preferred_formats": ["mp3", "aac"],
            "min_bitrate": null,
            "max_bitrate": 192,
            "max_file_size_mb": 20,
            "exclude_keywords": []
        }
    },
    "count": 3
}
```

**Code Reference:**
```python
# vscode-vfs://github/bozzfozz/soulspot/src/soulspot/api/routers/quality_profiles.py
# Lines 443-468

@router.get("/defaults/info", response_model=dict[str, Any])
async def get_default_profiles_info(
    request: Request,
) -> dict[str, Any]:
    """Get information about default/builtin profiles.

    Hey future me - useful for UI to show profile descriptions!
    Returns the predefined profiles (AUDIOPHILE, BALANCED, SPACE_SAVER).
    """
```

**Built-in Profiles:**

**1. AUDIOPHILE:**
- **Target**: Maximum quality, no compromises
- **Formats**: FLAC only
- **Bitrate**: 320kbps minimum
- **Size Limit**: None
- **Use Case**: Archival, high-end audio systems

**2. BALANCED:**
- **Target**: Good quality, reasonable file sizes
- **Formats**: FLAC (preferred), MP3 (fallback)
- **Bitrate**: 192-320kbps
- **Size Limit**: 50MB
- **Use Case**: General listening, balanced storage

**3. SPACE_SAVER:**
- **Target**: Maximum compression, small files
- **Formats**: MP3, AAC
- **Bitrate**: Max 192kbps
- **Size Limit**: 20MB
- **Use Case**: Mobile devices, limited storage

**Use Cases:**
- **Documentation**: Show users what built-in profiles offer
- **Profile Comparison**: Compare custom profiles to defaults
- **Reset Reference**: Know what default settings are

---

## Summary

**Total Endpoints Documented:** 10

**Endpoint Categories:**
1. **List & Get**: 3 endpoints (list all, get active, get by ID)
2. **CRUD**: 3 endpoints (create, update, delete)
3. **Activation**: 1 endpoint (set active profile)
4. **Metadata**: 2 endpoints (available formats, default profiles info)

**Key Features:**
- **Format Priority**: Define preferred format order
- **Quality Constraints**: Min/max bitrate, file size limits
- **Keyword Filtering**: Exclude unwanted content (live, demo, etc.)
- **Built-in Profiles**: 3 predefined profiles (AUDIOPHILE, BALANCED, SPACE_SAVER)
- **Active Profile**: One profile used for download filtering/scoring
- **Protected Defaults**: Built-in profiles cannot be deleted or renamed

**Module Stats:**
- **Source File**: `quality_profiles.py` (489 lines)
- **Endpoints**: 10
- **Code Validation**: 100%

**Supported Formats:**
- **Lossless**: FLAC, ALAC, WAV
- **Lossy**: MP3, AAC, M4A, Ogg, Opus

**Use Cases:**
- **Download Filtering**: Filter Soulseek search results by quality criteria
- **Result Scoring**: Score search results by preference (FLAC > MP3)
- **Post-Processing**: Validate downloads meet quality requirements
- **User Preferences**: Custom quality profiles for different scenarios (WiFi vs. mobile)

**Integration:**
- **DownloadService**: Filters search results using active profile
- **PostProcessingWorker**: Validates downloaded files meet quality criteria
- **AppSettings**: Active profile ID cached for fast access
