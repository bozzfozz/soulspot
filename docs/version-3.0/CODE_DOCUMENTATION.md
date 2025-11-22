# Code Documentation Standards (Version 3.0)

**Version:** 3.0.0  
**Status:** Planning Phase  
**Last Updated:** 2025-11-22

---

## 1. Overview

This document defines **code documentation standards** for SoulSpot Bridge Version 3.0. The core principle: **No complex algorithms or non-trivial code without clear explanation.**

### 1.1 Core Principle

> "Write code for humans first, computers second. If code is tricky, non-obvious, or clever, explain it like you're writing a note to your future self after six months."

### 1.2 Why This Matters

**Bad Code (No Documentation):**
```python
def q_score(b, f, s):
    m = {"flac": 1.2, "mp3": 0.9}.get(f, 0.7)
    return int((min(b / 320, 1.5) * m) * 100)
```

**Good Code (Well-Documented):**
```python
def calculate_quality_score(bitrate: int, format: str, file_size: int) -> int:
    """
    Calculate quality score for search results (0-100).
    
    Hey future me – This scoring algorithm prioritizes lossless formats
    (FLAC, ALAC) over lossy (MP3, OGG), then ranks by bitrate. We penalize
    tiny files because they're often incomplete or corrupted.
    
    The magic numbers are based on user feedback (see GitHub issue #42):
    - 320 kbps = reference bitrate (max MP3 quality)
    - 1.2x multiplier for FLAC = user preference for lossless
    - 5MB minimum for FLAC = prevents false positives
    
    Args:
        bitrate: Audio bitrate in kbps (128-320 for MP3, 800-1400 for FLAC)
        format: File format (mp3, flac, m4a, ogg, etc.)
        file_size: File size in bytes
        
    Returns:
        Quality score (0-100). Higher is better.
        100 = Perfect (FLAC at high bitrate)
        85 = Excellent (MP3 320kbps)
        70 = Good (MP3 256kbps)
        50 = Acceptable (MP3 192kbps)
        0 = Reject (corrupted or unsupported)
        
    Examples:
        >>> calculate_quality_score(320, "mp3", 10_000_000)
        85  # Excellent MP3
        
        >>> calculate_quality_score(1411, "flac", 30_000_000)
        100  # Perfect FLAC
        
        >>> calculate_quality_score(1411, "flac", 1_000_000)
        0  # FLAC too small, likely corrupted
        
    Notes:
        - FLAC files below 5MB are suspicious (3min song @ 1411kbps ≈ 30MB)
        - MP3 320kbps is the sweet spot for lossy compression
        - We don't penalize large FLAC files (high-res audio is normal)
        
    See Also:
        - GitHub issue #42: Quality scoring feedback
        - docs/architecture.md: Search result ranking
    """
    # Lossless formats get bonus multiplier
    # Why these values? User testing showed FLAC preference over MP3
    format_multiplier = {
        "flac": 1.2,   # Lossless, preferred
        "alac": 1.2,   # Apple lossless, same quality
        "ape": 1.1,    # Monkey's Audio, less common
        "wav": 1.0,    # Uncompressed but huge files
        "mp3": 0.9,    # Lossy but widely compatible
        "m4a": 0.9,    # AAC, similar to MP3
        "ogg": 0.85,   # Ogg Vorbis, good but less compatible
    }.get(format.lower(), 0.7)  # Unknown format penalty
    
    # Normalize bitrate to 0-1 scale, using 320 as reference
    # Why 320? It's the max MP3 bitrate, good comparison point
    bitrate_score = min(bitrate / 320, 1.5)  # Allow FLAC to exceed 1.0
    
    # File size sanity check (detect corrupted files)
    # Why 5MB? Average song is 3-4 minutes
    # - 320kbps MP3 ≈ 9-12MB
    # - 1411kbps FLAC ≈ 30-40MB
    if file_size < 5_000_000 and format.lower() in ["flac", "alac", "ape"]:
        # Lossless file this small is probably corrupt or incomplete
        return 0
    
    # Calculate final score
    score = int((bitrate_score * format_multiplier) * 100)
    return min(score, 100)  # Cap at 100
```

---

## 2. Documentation Requirements

### 2.1 Module-Level Documentation

**Every module MUST have:**

```python
# modules/soulseek/__init__.py

"""
Soulseek Module - P2P music download integration.

This module provides integration with the Soulseek network via the slskd client.
It handles track searching, download management, and file organization.

Architecture:
    Main module: Connection management and health checks
    Submodules:
        - search/: Track search functionality
        - downloads/: Download queue and transfer management

Key Features:
    - Search Soulseek network for tracks
    - Quality-based result ranking
    - Parallel download management
    - Automatic retry on failure
    - Integration with Module Router

Dependencies:
    - slskd: External Soulseek daemon (required)
    - core: Core module (required)
    - metadata: For file enrichment (optional)

Configuration:
    See docs/configuration.md for setup guide.

Examples:
    >>> from soulseek import Module
    >>> module = Module()
    >>> health = module.health_check()
    >>> print(health["status"])
    "healthy"

See Also:
    - docs/architecture.md: Design decisions
    - docs/api.md: API documentation
    - SOULSEEK_MODULE.md: Complete specification
"""

__version__ = "1.0.0"
__author__ = "SoulSpot Team"

# ... module code
```

### 2.2 Class Documentation

**Every class MUST have:**

```python
class DownloadService:
    """
    Download management service.
    
    Orchestrates the complete download lifecycle:
    1. Search → select best result
    2. Initiate download via slskd
    3. Monitor progress
    4. Handle completion/failure
    5. Publish events for other modules
    
    Hey future me – This is the heart of the Soulseek module. Downloads
    are managed by slskd, we just coordinate. We DON'T handle file transfers
    ourselves (slskd does that). Our job is:
    - Talk to slskd API
    - Monitor download status
    - Retry on failure
    - Notify other modules when done
    
    Design Decisions:
        - Why polling? slskd doesn't have webhooks (yet)
        - Why 5s interval? Balance between responsiveness and API load
        - Why max 3 retries? Most failures are permanent (user offline)
    
    Attributes:
        slskd_client: HTTP client for slskd API
        download_repo: Database repository for downloads
        event_bus: For publishing download events
        retry_policy: Exponential backoff retry configuration
        
    Example:
        >>> service = DownloadService(slskd_client, repo, event_bus)
        >>> download = await service.start_download(
        ...     artist="Beatles",
        ...     title="Let It Be",
        ... )
        >>> print(download.status)
        "pending"
        
    See Also:
        - docs/architecture.md: Download state machine
        - backend/domain/download.py: Download entity
    """
    
    def __init__(
        self,
        slskd_client: SlskdClient,
        download_repo: DownloadRepository,
        event_bus: EventBus,
    ):
        self.slskd_client = slskd_client
        self.download_repo = download_repo
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
```

### 2.3 Function/Method Documentation

**Every public function MUST have:**

```python
async def start_download(
    self,
    artist: str,
    title: str,
    album: str | None = None,
    quality_threshold: int = 70,
) -> Download:
    """
    Start downloading a track.
    
    This function orchestrates the complete download start process:
    1. Search Soulseek network
    2. Filter and rank results by quality
    3. Select best result above threshold
    4. Initiate download via slskd
    5. Create database record
    6. Publish 'download.started' event
    
    Args:
        artist: Artist name (required)
        title: Track title (required)
        album: Album name (optional, helps filter results)
        quality_threshold: Minimum quality score (0-100, default: 70)
            70 = Good MP3 256kbps or better
            85 = Excellent MP3 320kbps
            90 = FLAC/lossless preferred
            
    Returns:
        Download entity with initial status 'pending'
        
    Raises:
        NoResultsFoundError: If search returns no results
        QualityThresholdError: If no results meet quality threshold
        SlskdConnectionError: If slskd is unreachable
        
    Examples:
        >>> # Download with default quality (70+)
        >>> download = await service.start_download(
        ...     artist="Beatles",
        ...     title="Let It Be",
        ... )
        
        >>> # Download only high-quality FLAC
        >>> download = await service.start_download(
        ...     artist="Beatles",
        ...     title="Let It Be",
        ...     quality_threshold=90,
        ... )
        
    Notes:
        - Search is case-insensitive
        - Results are ranked by quality score (see calculate_quality_score)
        - If multiple results have same quality, newest is preferred
        - Download is async (returns immediately, downloads in background)
        
    See Also:
        - calculate_quality_score(): Quality ranking algorithm
        - backend/domain/download.py: Download state machine
        - docs/api.md: Complete API documentation
    """
    self.logger.info(
        f"Starting download",
        extra={
            "artist": artist,
            "title": title,
            "album": album,
            "quality_threshold": quality_threshold,
        }
    )
    
    # Step 1: Search
    search_query = f"{artist} {title}"
    if album:
        search_query += f" {album}"
    
    results = await self._search_track(search_query)
    
    if not results:
        raise NoResultsFoundError(
            code="SLSKD_SEARCH_NO_RESULTS",
            message=f"No results found for '{search_query}'",
            resolution=(
                "Try:\n"
                "1. Check spelling\n"
                "2. Use different keywords\n"
                "3. Remove album name and try again"
            ),
            context={
                "artist": artist,
                "title": title,
                "album": album,
                "query": search_query,
            },
        )
    
    # Step 2: Filter and rank
    # Why filter? Many results are low-quality or incomplete
    quality_results = [
        r for r in results 
        if r.quality_score >= quality_threshold
    ]
    
    if not quality_results:
        raise QualityThresholdError(
            code="SLSKD_SEARCH_QUALITY_TOO_LOW",
            message=f"No results meet quality threshold {quality_threshold}",
            resolution=(
                f"Lower quality threshold or try different search.\n"
                f"Best result found: {max(r.quality_score for r in results)}"
            ),
            context={
                "threshold": quality_threshold,
                "best_score": max(r.quality_score for r in results),
                "results_count": len(results),
            },
        )
    
    # Step 3: Select best result
    # Sort by quality (descending), then by date (newest first)
    best_result = sorted(
        quality_results,
        key=lambda r: (r.quality_score, r.date_added),
        reverse=True,
    )[0]
    
    self.logger.info(
        f"Selected best result",
        extra={
            "username": best_result.username,
            "filename": best_result.filename,
            "quality_score": best_result.quality_score,
        }
    )
    
    # Step 4: Initiate download via slskd
    slskd_download_id = await self.slskd_client.start_download(
        username=best_result.username,
        filename=best_result.filename,
    )
    
    # Step 5: Create database record
    download = Download(
        slskd_id=slskd_download_id,
        artist=artist,
        title=title,
        album=album,
        filename=best_result.filename,
        file_size=best_result.file_size,
        quality_score=best_result.quality_score,
        status=DownloadStatus.PENDING,
        created_at=datetime.utcnow(),
    )
    
    await self.download_repo.save(download)
    
    # Step 6: Publish event
    await self.event_bus.publish(
        "download.started",
        {
            "download_id": download.id,
            "artist": artist,
            "title": title,
            "quality_score": best_result.quality_score,
        }
    )
    
    return download
```

### 2.4 Complex Algorithm Documentation

**For any non-trivial algorithm:**

```python
def _calculate_retry_delay(attempt: int) -> int:
    """
    Calculate exponential backoff delay for retries.
    
    Hey future me – This implements exponential backoff to avoid hammering
    slskd when it's having issues. The formula is:
    
        delay = min(base_delay * 2^attempt, max_delay)
    
    Why exponential? Linear backoff (5s, 10s, 15s) is too aggressive when
    service is down. Exponential (5s, 10s, 20s, 40s) gives service time
    to recover.
    
    Why cap at 300s? Waiting more than 5 minutes is pointless. If service
    is down that long, it's a bigger issue.
    
    Formula Derivation:
        attempt  | delay (s) | reasoning
        ---------|-----------|----------
        1        | 5         | Quick retry, might be transient
        2        | 10        | Give it a bit more time
        3        | 20        | Probably real issue
        4        | 40        | Definitely real issue
        5        | 80        | Service likely down
        6        | 160       | Service definitely down
        7+       | 300       | Max out, no point waiting longer
    
    Args:
        attempt: Retry attempt number (1-indexed)
        
    Returns:
        Delay in seconds before next retry
        
    Examples:
        >>> _calculate_retry_delay(1)
        5
        >>> _calculate_retry_delay(3)
        20
        >>> _calculate_retry_delay(10)
        300  # Capped at max
        
    See Also:
        - docs/architecture.md: Retry strategy discussion
        - GitHub issue #67: Why exponential backoff?
    """
    base_delay = 5      # Start with 5 seconds
    max_delay = 300     # Cap at 5 minutes
    
    # Exponential backoff: base * 2^attempt
    delay = base_delay * (2 ** (attempt - 1))
    
    # Cap at max delay
    return min(delay, max_delay)
```

### 2.5 Inline Comments for Tricky Code

**Use inline comments for:**

```python
async def _parse_search_results(raw_results: dict) -> List[SearchResult]:
    """Parse raw slskd search results into SearchResult objects."""
    parsed = []
    
    for item in raw_results.get("files", []):
        # HACK: slskd sometimes returns null bitrate for FLAC files
        # This is a bug in slskd v0.19.x. We estimate bitrate from file size.
        # Remove this workaround when bug is fixed.
        # See: https://github.com/slskd/slskd/issues/456
        bitrate = item.get("bitrate")
        if bitrate is None or bitrate == 0:
            file_size = item.get("size", 0)
            duration_ms = item.get("duration", 0)
            
            if duration_ms > 0:
                # Estimate: (file_size_bytes * 8) / (duration_seconds * 1000)
                bitrate = int((file_size * 8) / (duration_ms / 1000))
            else:
                # Can't estimate, use conservative default
                bitrate = 192  # Assume MP3 192kbps
        
        # NOTE: We filter out files with suspicious extensions here
        # Why? Soulseek network has viruses disguised as music files.
        # Common tricks:
        # - file.mp3.exe (double extension)
        # - file.mp3 (but actually .exe with hidden extension)
        # We check both extension and magic bytes (if available)
        filename = item.get("filename", "")
        if any(filename.endswith(ext) for ext in [".exe", ".dll", ".bat", ".sh"]):
            # Skip executable files
            continue
        
        # TODO: Implement magic byte checking for extra safety
        # See GitHub issue #89
        
        parsed.append(
            SearchResult(
                username=item["username"],
                filename=filename,
                file_size=item["size"],
                bitrate=bitrate,
                format=item.get("extension", "unknown"),
                # ... other fields
            )
        )
    
    return parsed
```

---

## 3. Documentation Patterns

### 3.1 "Future-Self" Comments

**Write comments as if explaining to yourself in 6 months:**

```python
# Hey future me – Remember when you spent 3 hours debugging why downloads
# were stuck at 99%? It was because slskd reports completion BEFORE
# actually writing the last chunk to disk. That's why we added this
# 2-second delay. Don't remove it or the bug comes back.
await asyncio.sleep(2)
await self._verify_file_complete(download.file_path)
```

### 3.2 Edge Case Comments

**Document edge cases and gotchas:**

```python
def _sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file system storage.
    
    Edge cases handled:
    1. Empty filename → "untitled"
    2. Only special chars → "untitled"
    3. Path traversal (../) → stripped
    4. Reserved Windows names (CON, PRN, etc.) → prefixed with "_"
    5. Too long (>255 chars) → truncated with hash suffix
    6. Unicode normalization → NFC form
    """
    # Edge case 1: Empty or whitespace-only
    if not filename or not filename.strip():
        return "untitled"
    
    # Edge case 2: Remove path separators (prevent directory traversal)
    filename = filename.replace("/", "_").replace("\\", "_")
    
    # Edge case 3: Remove parent directory references
    filename = filename.replace("..", "")
    
    # Edge case 4: Check for Windows reserved names
    # Why? CON, PRN, AUX, NUL cause errors on Windows
    base_name = filename.split(".")[0].upper()
    reserved = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
    if base_name in reserved:
        filename = f"_{filename}"  # Prefix with underscore
    
    # Edge case 5: Truncate if too long (filesystem limit)
    if len(filename) > 255:
        # Keep extension, truncate name, add hash for uniqueness
        import hashlib
        name, ext = os.path.splitext(filename)
        hash_suffix = hashlib.md5(name.encode()).hexdigest()[:8]
        max_name_len = 255 - len(ext) - len(hash_suffix) - 1
        filename = f"{name[:max_name_len]}_{hash_suffix}{ext}"
    
    # Edge case 6: Normalize Unicode (prevent duplicate files)
    # Why? "café" and "café" can be different on some filesystems
    import unicodedata
    filename = unicodedata.normalize("NFC", filename)
    
    return filename
```

### 3.3 Magic Number Explanations

**Always explain magic numbers:**

```python
# Bad: Magic numbers without explanation
if retries < 3:
    await asyncio.sleep(5)
    
# Good: Explained magic numbers
MAX_RETRIES = 3  # Based on user testing: 3 retries cover 95% of transient failures
RETRY_DELAY = 5  # Seconds. Short enough for good UX, long enough for service recovery

if retries < MAX_RETRIES:
    await asyncio.sleep(RETRY_DELAY)
```

```python
# Bad: Arbitrary threshold
if score > 70:
    return True
    
# Good: Justified threshold
QUALITY_THRESHOLD = 70  # Corresponds to MP3 256kbps (user survey: minimum acceptable quality)
                        # See docs/quality-scoring.md for full breakdown

if score > QUALITY_THRESHOLD:
    return True
```

### 3.4 ADRs (Architecture Decision Records)

**For significant design decisions, create ADRs:**

```markdown
# ADR 001: Why Polling Instead of Webhooks for slskd

## Context
We need to monitor download progress from slskd. Two options:
1. Poll slskd API every N seconds
2. Use webhooks (if/when slskd adds them)

## Decision
Use polling with 5-second interval.

## Rationale
- slskd v0.19.x doesn't support webhooks (as of 2025-11)
- Polling is simple and reliable
- 5s interval balances responsiveness vs. API load
- We can easily migrate to webhooks when available

## Consequences
**Positive:**
- Works with current slskd version
- Simple implementation
- Predictable API load

**Negative:**
- Slight delay (up to 5s) in status updates
- Some unnecessary API calls when nothing changes
- Not scalable to 1000s of concurrent downloads

## Alternatives Considered
1. WebSocket connection: slskd doesn't expose WebSocket API
2. File system watching: Unreliable, OS-dependent
3. Faster polling (1s): Too aggressive, high API load

## Review Date
Review when slskd v0.20.0 releases (expected Q1 2026)

## References
- slskd GitHub: https://github.com/slskd/slskd
- Issue #123: Webhook support request
```

---

## 4. README Requirements

### 4.1 Module README

**Every module MUST have README.md:**

```markdown
# Soulseek Module

## Quick Start

```bash
# Configure slskd connection
curl -X POST http://localhost:8000/settings/soulseek \
  -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:5030", "api_key": "your_key"}'

# Search for track
curl http://localhost:8000/soulseek/search?q=Beatles+Let+It+Be

# Start download
curl -X POST http://localhost:8000/soulseek/downloads \
  -H "Content-Type: application/json" \
  -d '{"artist": "Beatles", "title": "Let It Be"}'
```

## Architecture

This module is split into submodules for better organization:

### Main Module
- **Purpose**: Connection management and health checks
- **Size**: ~200 LOC
- **Files**: `backend/infrastructure/slskd_client.py`, `backend/application/health_service.py`

### Search Submodule
- **Purpose**: Track search on Soulseek network
- **Size**: ~600 LOC
- **Why separate?**: Stateless functionality, different team can develop in parallel

### Downloads Submodule
- **Purpose**: Download queue and transfer management
- **Size**: ~1,200 LOC
- **Why separate?**: Stateful downloads have different lifecycle than search

## Why Submodules?

We split search and downloads because they have different:
- **Lifecycles**: Search is stateless (instant), downloads are stateful (long-running)
- **Performance**: Search is fast (<1s), downloads are slow (minutes)
- **Testing**: Search uses mocks, downloads need integration tests
- **Development**: Different developers can work on each without conflicts

## Configuration

See `docs/configuration.md` for complete setup guide.

Required:
- `slskd_url`: URL to slskd instance (e.g., http://localhost:5030)
- `slskd_api_key`: API key for authentication (or username/password)

Optional:
- `quality_threshold`: Minimum quality score (default: 70)
- `max_concurrent_downloads`: Max parallel downloads (default: 3)
- `timeout`: API timeout in seconds (default: 30)

## Development

```bash
# Install dependencies
poetry install --with dev

# Run tests
pytest modules/soulseek/tests/

# Run only search submodule tests
pytest modules/soulseek/submodules/search/tests/

# Run linter
ruff check modules/soulseek/

# Run type checker
mypy modules/soulseek/
```

## Documentation

- `docs/architecture.md`: Design decisions and diagrams
- `docs/api.md`: Complete API documentation
- `docs/events.md`: Event schemas and contracts
- `docs/development.md`: Development and contribution guide
- `CHANGELOG.md`: Version history

## Support

- GitHub Issues: https://github.com/bozzfozz/soulspot-bridge/issues
- Docs: https://docs.soulspot.app/modules/soulseek
- Troubleshooting: https://docs.soulspot.app/troubleshooting/soulseek
```

### 4.2 Submodule README

**Every submodule MUST have README.md:**

```markdown
# Soulseek Search Submodule

## Purpose

Handles track search on the Soulseek network via slskd.

## Features

- Search by artist, title, album
- Quality-based result ranking
- File format filtering
- Duplicate detection

## Usage

```python
from soulseek.submodules.search import SearchService

service = SearchService(slskd_client)
results = await service.search_tracks("Beatles Let It Be")

for result in results:
    print(f"{result.quality_score}/100: {result.filename}")
```

## Architecture

```
search/
├── backend/
│   ├── domain/
│   │   ├── search_query.py     # Query parsing and validation
│   │   └── search_result.py    # Result entity with quality score
│   ├── application/
│   │   └── search_service.py   # Core search logic
│   └── api/
│       ├── routes.py           # HTTP endpoints
│       └── schemas.py          # Request/response models
└── tests/
    ├── test_search_service.py
    └── test_quality_scoring.py
```

## Quality Scoring

See `docs/quality-scoring.md` for complete algorithm explanation.

Summary:
- 100 = Perfect (FLAC high-bitrate)
- 85 = Excellent (MP3 320kbps)
- 70 = Good (MP3 256kbps, default threshold)
- 50 = Acceptable (MP3 192kbps)
- 0 = Reject (corrupted or low quality)

## Testing

```bash
# Unit tests
pytest search/tests/test_search_service.py

# Integration tests (requires slskd)
pytest search/tests/test_integration.py
```

## Development Notes

**Known Issues:**
- slskd sometimes returns null bitrate for FLAC (workaround in `_parse_search_results`)
- Duplicate results from different users (deduplicated by filename hash)

**Future Improvements:**
- Add fuzzy matching for artist/title
- Implement caching for popular searches
- Add user blacklist feature

See `CHANGELOG.md` for version history.
```

---

## 5. Testing Documentation

### 5.1 Test Docstrings

```python
def test_calculate_quality_score_flac():
    """
    Test quality scoring for FLAC files.
    
    FLAC files should score higher than MP3 due to lossless quality.
    
    Test cases:
    1. High-bitrate FLAC (1411kbps) → 100 score
    2. Mid-bitrate FLAC (800kbps) → ~80 score
    3. Suspiciously small FLAC (<5MB) → 0 score (corrupted)
    
    Why test small files? Real bug (GitHub #87): User downloaded
    corrupted FLAC files that appeared high-quality in results.
    """
    # Test case 1: Perfect FLAC
    score = calculate_quality_score(
        bitrate=1411,
        format="flac",
        file_size=30_000_000,  # 30MB, normal for 3-4 min song
    )
    assert score == 100
    
    # Test case 2: Mid-quality FLAC
    score = calculate_quality_score(
        bitrate=800,
        format="flac",
        file_size=20_000_000,
    )
    assert 75 <= score <= 85
    
    # Test case 3: Corrupted FLAC (too small)
    score = calculate_quality_score(
        bitrate=1411,
        format="flac",
        file_size=1_000_000,  # 1MB, way too small
    )
    assert score == 0  # Should reject
```

---

## 6. Summary

**Requirements:**
- ✅ Every module has comprehensive README
- ✅ Every class has docstring with purpose and examples
- ✅ Every public function has complete docstring (Args, Returns, Raises, Examples)
- ✅ Complex algorithms have "future-self" explanations
- ✅ Magic numbers are explained with constants
- ✅ Edge cases are documented inline
- ✅ ADRs for significant design decisions
- ✅ Submodules have their own README

**Benefits:**
- Anyone can understand code 6 months later
- New developers onboard quickly
- Bugs are easier to debug
- Design decisions are preserved
- Code reviews are faster

---

**End of Code Documentation Standards**
