# Image Service Architecture

**Category:** Architecture  
**Status:** IMPLEMENTED ✅  
**Last Updated:** 2025-01-XX  
**Related Docs:** [Plugin System](./plugin-system.md) | [Service Separation Principles](./service-separation-principles.md)

---

## Overview

ImageService is the central service for all image operations in SoulSpot: fetching display URLs, downloading images, caching locally, and optimizing storage.

**What ImageService Does:**
- Get best display URL (local cache > CDN > placeholder)
- Download images from provider CDNs
- Convert to WebP and cache locally
- Validate CDN URLs (check if still accessible)
- Optimize cache (cleanup old/orphaned images)

**What ImageService Does NOT Do:**
- ❌ Fetch URLs from providers → Plugins do this (SpotifyPlugin, DeezerPlugin)
- ❌ Provider authentication → Plugins handle this
- ❌ Provider-specific fallback logic → Plugins handle this

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                            │
│                                                                  │
│   Templates (Jinja2)                                            │
│   ├── dashboard.html  <img src="{{ artist|image_display_url }}">│
│   ├── playlists.html                                            │
│   └── ...                                                       │
│                                                                  │
│   Calls: get_display_url(source_url, local_path, entity_type)  │
│   Gets:  "/artwork/local/artists/ab/abc.webp" (cached)         │
│          "https://i.scdn.co/image/abc" (CDN fallback)           │
│          "/static/images/placeholder-artist.svg" (no image)     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                            │
│                                                                  │
│   ImageService                                                  │
│   ├── get_display_url()     ← Sync, for templates               │
│   ├── get_image()           ← Async, return ImageInfo           │
│   ├── download_and_cache()  ← Async, download + WebP + cache    │
│   ├── validate_image()      ← Async, HEAD request to CDN        │
│   └── optimize_cache()      ← Async, cleanup old images         │
│                                                                  │
│   Internal:                                                     │
│   ├── _download_image()     ← HTTP GET via HttpClientPool       │
│   ├── _convert_to_webp()    ← PIL in thread pool                │
│   ├── _save_to_cache()      ← Filesystem write                  │
│   └── _update_entity_image_path() ← DB update                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                          │
│                                                                  │
│   Plugins (provide URLs only, NO downloads!)                    │
│   ├── SpotifyPlugin.get_artist_details()                        │
│   │   └── ArtistDTO { name, image_url, ... }                   │
│   ├── DeezerPlugin.get_album_details()                          │
│   │   └── AlbumDTO { title, cover_url, ... }                   │
│   └── ...                                                       │
│                                                                  │
│   HttpClientPool (for image downloads)                          │
│   └── Shared httpx.AsyncClient with connection reuse            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Download and Display Image

### Step 1: Sync Service Gets Data from Plugin

```python
# SpotifySyncService or DeezerSyncService
artist_dto = await spotify_plugin.get_artist_details(spotify_uri)

# artist_dto contains:
# - name: "Radiohead"
# - image_url: "https://i.scdn.co/image/abc123..."  ← CDN URL!
# - spotify_uri: "spotify:artist:4Z8W4fKeB5YxbusRsdQVPb"
```

**Plugin provides the URL as part of entity data!**

---

### Step 2: Sync Service Calls ImageService

```python
# Sync service decides: cache image locally?
if settings.cache_images_locally:
    result = await image_service.download_and_cache(
        source_url=artist_dto.image_url,  # URL from plugin
        entity_type="artist",
        entity_id=artist.id,              # Internal UUID
    )
    
    if result.success:
        # artist.image_path is now set
        logger.info(f"Image cached: {result.image_info.local_path}")
```

---

### Step 3: ImageService Processes Image

```
ImageService.download_and_cache():
│
├── 1. Check: Already cached and URL same?
│       YES → Return SaveImageResult.success_cached()
│       NO  → Continue
│
├── 2. Download via HttpClientPool
│       GET https://i.scdn.co/image/abc123...
│       → bytes (JPEG, PNG, etc.)
│
├── 3. WebP Conversion (PIL in thread pool)
│       - Resize to 300px (artists) or 500px (albums)
│       - Convert to WebP (quality 85)
│       → webp_bytes
│
├── 4. Save to Cache
│       /app/data/cache/images/artists/ab/abc123.webp
│       Sharding: first 2 chars of ID
│
├── 5. DB Update
│       UPDATE soulspot_artists 
│       SET image_url = 'https://...', 
│           image_path = 'artists/ab/abc123.webp'
│       WHERE id = 'abc123...'
│
└── 6. Return SaveImageResult.success_downloaded()
```

---

### Step 4: Template Displays Image

```jinja2
<!-- templates/artists.html -->
{% for artist in artists %}
    <img src="{{ artist|image_display_url }}" 
         alt="{{ artist.name }}"
         loading="lazy">
{% endfor %}
```

**Filter calls `ImageService.get_display_url()`:**
```python
# Priority order:
# 1. Local cache (if exists and valid)
# 2. CDN URL (if exists and valid)
# 3. Placeholder (fallback)

def get_display_url(source_url: str | None, local_path: str | None, entity_type: str) -> str:
    # Prefer local cache
    if local_path:
        cache_file = IMAGE_CACHE_DIR / local_path
        if cache_file.exists():
            return f"/artwork/local/{local_path}"
    
    # Fallback to CDN
    if source_url:
        return source_url
    
    # Last resort: placeholder
    return f"/static/images/placeholder-{entity_type}.svg"
```

---

## Image Cache Structure

```
/app/data/cache/images/
├── artists/
│   ├── 00/  ← First 2 chars of entity ID (sharding)
│   │   ├── 001234ab-cdef-5678-90ab-cdefabcd1234.webp
│   │   └── 00fedcba-9876-5432-10fe-dcba98765432.webp
│   ├── 01/
│   ├── ab/
│   │   └── abc123...webp
│   └── ...
├── albums/
│   ├── 00/
│   ├── ab/
│   └── ...
└── playlists/
    └── ...
```

**Why sharding?** Filesystems slow down with >10,000 files in single directory. Sharding distributes files across subdirectories.

---

## ImageService Methods

### get_display_url() (Sync)

**Purpose:** Get best URL for displaying image in templates.

```python
def get_display_url(
    self,
    source_url: str | None,
    local_path: str | None,
    entity_type: str,
) -> str:
    """Get best display URL (sync method for templates).
    
    Priority:
    1. Local cache (if exists)
    2. CDN URL (if exists)
    3. Placeholder
    
    Returns:
        URL string (always returns something)
    """
```

**Source:** `src/soulspot/application/services/images/image_service.py` (lines 120-145)

---

### download_and_cache() (Async)

**Purpose:** Download image from CDN, convert to WebP, cache locally.

```python
async def download_and_cache(
    self,
    source_url: str,
    entity_type: str,
    entity_id: UUID,
) -> SaveImageResult:
    """Download image and save to local cache.
    
    Steps:
    1. Check if already cached with same URL
    2. Download from source_url
    3. Convert to WebP (resize + compress)
    4. Save to cache with sharding
    5. Update entity's image_path in DB
    
    Returns:
        SaveImageResult with success/error info
    """
```

**Source:** `src/soulspot/application/services/images/image_service.py` (lines 200-350)

---

### validate_image() (Async)

**Purpose:** Check if CDN URL is still accessible (HEAD request).

```python
async def validate_image(self, url: str) -> bool:
    """Validate if image URL is still accessible.
    
    Makes HEAD request to check:
    - URL returns 200 OK
    - Content-Type is image/*
    
    Returns:
        True if valid, False otherwise
    """
```

**Used by:** Background worker to detect broken CDN links.

---

### optimize_cache() (Async)

**Purpose:** Cleanup old/orphaned images from cache.

```python
async def optimize_cache(
    self,
    max_age_days: int = 90,
    dry_run: bool = False,
) -> dict[str, int]:
    """Optimize image cache.
    
    Removes:
    - Images not accessed in max_age_days
    - Orphaned images (entity deleted from DB)
    - Corrupted images (invalid WebP)
    
    Returns:
        Stats: {"removed": 123, "kept": 456, "freed_mb": 78}
    """
```

**Scheduled:** Daily via cron worker.

---

## Configuration

```python
# src/soulspot/config/settings.py

class ImageSettings:
    # Cache directory
    cache_dir: Path = Path("/app/data/cache/images")
    
    # Enable local caching
    cache_images_locally: bool = True
    
    # Image sizes (max dimension)
    artist_image_size: int = 300
    album_image_size: int = 500
    playlist_image_size: int = 400
    
    # WebP quality (1-100)
    webp_quality: int = 85
    
    # Cache optimization
    cache_max_age_days: int = 90
    cache_cleanup_schedule: str = "0 3 * * *"  # Daily at 3am
```

---

## Plugin Integration

**Plugins provide image URLs in DTOs:**

```python
# SpotifyPlugin
async def get_artist_details(self, spotify_uri: str) -> ArtistDTO:
    """Fetch artist from Spotify API."""
    response = await self._client.get(f"/artists/{artist_id}")
    
    return ArtistDTO(
        name=response["name"],
        image_url=response["images"][0]["url"] if response["images"] else None,
        spotify_id=artist_id,
        ...
    )

# DeezerPlugin
async def get_album_details(self, deezer_id: str) -> AlbumDTO:
    """Fetch album from Deezer API."""
    response = await self._client.get(f"/album/{deezer_id}")
    
    return AlbumDTO(
        title=response["title"],
        cover_url=response["cover_xl"],  # Deezer's high-res cover
        deezer_id=deezer_id,
        ...
    )
```

**ImageService then downloads these URLs.**

---

## Performance Optimizations

### 1. HTTP Connection Pooling

```python
# Shared HTTP client across all image downloads
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    timeout=httpx.Timeout(30.0),
)
```

**Benefit:** Reuse TCP connections, faster downloads.

---

### 2. Thread Pool for Image Processing

```python
# CPU-intensive PIL operations run in thread pool
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def _convert_to_webp(self, image_bytes: bytes) -> bytes:
    """Convert image to WebP in thread pool."""
    return await asyncio.get_event_loop().run_in_executor(
        executor,
        self._convert_to_webp_sync,
        image_bytes,
    )
```

**Benefit:** Don't block async event loop with CPU work.

---

### 3. Filesystem Sharding

```python
# Distribute files across subdirectories
def _get_cache_path(self, entity_type: str, entity_id: UUID) -> Path:
    """Get cache path with sharding."""
    id_str = str(entity_id).replace("-", "")
    shard = id_str[:2]  # First 2 chars
    return self.cache_dir / entity_type / shard / f"{id_str}.webp"
```

**Benefit:** Prevent filesystem slowdown with 10,000+ files per directory.

---

## Testing

```python
# tests/unit/services/test_image_service.py

async def test_download_and_cache_success():
    """Test successful image download and caching."""
    service = ImageService(...)
    
    result = await service.download_and_cache(
        source_url="https://example.com/image.jpg",
        entity_type="artist",
        entity_id=UUID("abc123..."),
    )
    
    assert result.success
    assert result.image_info.local_path == "artists/ab/abc123...webp"
    assert Path(result.image_info.local_path).exists()

async def test_get_display_url_prefers_local():
    """Test display URL prefers local cache over CDN."""
    url = service.get_display_url(
        source_url="https://cdn.example.com/image.jpg",
        local_path="artists/ab/abc123.webp",
        entity_type="artist",
    )
    
    assert url == "/artwork/local/artists/ab/abc123.webp"
```

---

## Related Documentation

- **[Plugin System](./plugin-system.md)** - How plugins provide image URLs
- **[Service Separation Principles](./service-separation-principles.md)** - Single responsibility
- **[Worker Patterns](./worker-patterns.md)** - Background cache optimization

---

**Last Validated:** 2025-01-XX  
**Source:** `src/soulspot/application/services/images/image_service.py`  
**Status:** ✅ IMPLEMENTED and production-ready
