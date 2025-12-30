# SoulSpot Core Philosophy

> **"Soul Spot is Autonomous"**

## Overview

SoulSpot's design is built on three fundamental principles:
1. **Autonomy**: SoulSpot is self-contained and makes all decisions
2. **Multi-Provider Aggregation**: Never rely on a single service
3. **External Services as Tools**: Other services are "dumb" data sources

---

## 1. The Autonomy Principle

SoulSpot is a self-contained, autonomous system. It manages, processes, and organizes everything internally. It does **not** rely on external services for logic or state management.

### Key Concepts

**SoulSpot is the Brain**:
- Decides what to download
- Determines when to pause/resume
- Controls how to tag and organize files
- Maintains the single source of truth

**External Services are Tools**:
- Spotify, Deezer, Tidal → Data sources only
- Soulseek/slskd → Download provider only
- MusicBrainz → Metadata enrichment only
- Services **never** control SoulSpot's state

**Implications**:
```python
# ✅ CORRECT: SoulSpot decides
if should_download_track(track):
    queue_for_download(track)
    
# ❌ WRONG: External service decides
if spotify_says_download(track):  # NO! Spotify doesn't control us
    download_track(track)
```

---

## 2. Plugin Architecture (Data Sources)

Services like **Spotify**, **Deezer**, and **Tidal** are treated strictly as **Data Source Plugins**.

### Role Definition

**What Plugins Do**:
- Provide metadata (artist info, album details, track metadata)
- Supply playlists and discovery data
- Offer search and browse capabilities

**What Plugins DON'T Do**:
- Store state (SoulSpot's database is the source of truth)
- Control business logic (SoulSpot makes decisions)
- Dictate data formats (plugins convert to SoulSpot's DTOs)

### Abstraction Layer

```
External API      →   Plugin      →   SoulSpot Internal DTO
──────────────────────────────────────────────────────────
Spotify JSON      →   SpotifyPlugin   →   ArtistDTO
Deezer JSON       →   DeezerPlugin    →   ArtistDTO
Tidal JSON        →   TidalPlugin     →   ArtistDTO
```

**Key Pattern**: SoulSpot converts external data into its own **Domain Entities** immediately:
- Never pass raw API responses through the system
- Always normalize to DTOs at the plugin boundary
- Internal code only works with SoulSpot's data types

---

## 3. Multi-Service Aggregation Principle ⭐

> **"Always use ALL available services, deduplicate, and combine results"**

This is the **most critical** principle for discovery, browse, and search features.

### The Rule

For ANY feature that fetches external data (Browse, Search, Discovery, New Releases, etc.):

1. **Query ALL enabled services** - Not just one
2. **Aggregate results** - Combine responses into unified list
3. **Deduplicate** - Use normalized keys (artist + title, ISRC, etc.)
4. **Tag source** - Track where each result came from
5. **Graceful fallback** - If one service fails, show results from others

### Why This Matters

**Better Coverage**:
- Different services have different catalogs
- Regional availability varies (album on Deezer but not Spotify in Germany)
- Discovery algorithms differ (Spotify's "New Releases" ≠ Deezer's "New Releases")

**User Freedom**:
- Not locked into one ecosystem
- Can discover music unavailable on their primary service
- Freedom to choose download source

**Resilience**:
- If Spotify is down, Deezer still works
- Rate limit on one service? Use another
- Service deprecation doesn't break SoulSpot

**Example**: New Releases page shows albums from **both** Spotify and Deezer, deduplicated:
- User sees 50 albums instead of 25
- Can discover regional releases (Deezer France has different content than Spotify France)
- Graceful fallback (if Spotify OAuth not configured, still see Deezer results)

### Implementation Pattern

**Code Example** (New Releases aggregation):
```python
async def get_new_releases():
    all_releases = []
    seen_keys = set()
    source_counts = {"deezer": 0, "spotify": 0}
    
    # 1. Deezer (no auth needed for browse)
    if await settings.is_provider_enabled("deezer"):
        if deezer_plugin.can_use(PluginCapability.BROWSE_NEW_RELEASES):
            for release in await deezer_plugin.get_browse_new_releases():
                key = normalize(release.artist, release.title)
                if key not in seen_keys:
                    seen_keys.add(key)
                    release.source = "deezer"
                    all_releases.append(release)
                    source_counts["deezer"] += 1
    
    # 2. Spotify (auth required)
    if await settings.is_provider_enabled("spotify"):
        if spotify_plugin.can_use(PluginCapability.BROWSE_NEW_RELEASES):
            for release in await spotify_plugin.get_new_releases():
                key = normalize(release.artist, release.title)
                if key not in seen_keys:
                    seen_keys.add(key)
                    release.source = "spotify"
                    all_releases.append(release)
                    source_counts["spotify"] += 1
    
    # 3. Future: Tidal, Apple Music, etc.
    
    return sorted(all_releases, key=lambda x: x.release_date, reverse=True)
```

**Normalization Pattern**:
```python
def normalize(artist: str, title: str) -> str:
    """Create deduplication key from artist + title."""
    # Remove special chars, lowercase, strip whitespace
    key = f"{artist}|{title}".lower()
    key = re.sub(r'[^\w\s|]', '', key)
    key = re.sub(r'\s+', ' ', key).strip()
    return key

# Examples:
normalize("The Beatles", "Hey Jude")  # "the beatles|hey jude"
normalize("Radiohead", "Paranoid Android")  # "radiohead|paranoid android"
```

**Service Count Tracking**:
```python
# UI can show: "50 releases (30 from Deezer, 20 from Spotify)"
{
    "releases": [...],
    "sources": {"deezer": 30, "spotify": 20},
    "total": 50
}
```

### Service Availability Checks

**Provider Check (First)**:
```python
# Check if provider is enabled in settings (not set to "off")
if not await settings.is_provider_enabled("spotify"):
    return {"skipped": "provider_disabled"}
```

**Authentication Check (Second)**:
```python
# Check if user has completed OAuth
if not spotify_plugin.is_authenticated:
    return {"skipped": "not_authenticated"}
```

**Capability Check (Combined)**:
```python
# can_use() checks BOTH: capability supported + auth if needed
if spotify_plugin.can_use(PluginCapability.BROWSE_NEW_RELEASES):
    # Safe to call - capability exists AND auth available (if required)
    releases = await spotify_plugin.get_browse_new_releases()
```

**Provider Modes**:
- `off`: Disabled completely
- `basic`: Enabled with basic features (metadata/browse)
- `pro`: Full features enabled

**Auth Requirements by Service**:

| Service | Public API (no auth) | Auth Required |
|---------|---------------------|---------------|
| **Deezer** | Search, browse, charts, genres, artist/album lookup | User favorites, playlists |
| **Spotify** | ❌ NOTHING | ALL operations |
| **MusicBrainz** | Everything | N/A |

**Check Order (CRITICAL)**:
```python
# 1. FIRST: Provider enabled?
if not await settings.is_provider_enabled("spotify"):
    return {"skipped": "provider_disabled"}

# 2. SECOND: User authenticated? (if needed)
if not spotify_plugin.is_authenticated:
    return {"skipped": "not_authenticated"}

# 3. THEN: Make API call
result = await spotify_plugin.get_followed_artists()
```

**Why this order?**
- Provider check is cheap (DB lookup)
- Auth check is cheap (memory check)
- API calls are expensive (network + rate limits)
- Don't waste API calls if service is disabled

**Quick Auth Check vs Full Validation**:
```python
# Quick check (synchronous, fast)
if not spotify_plugin.is_authenticated:
    return {"error": "not_authenticated"}

# Full validation (async, makes API call)
auth_status = await spotify_plugin.get_auth_status()
if not auth_status.is_authenticated:
    return {"error": "token_expired"}
```

Use `is_authenticated` property for most checks, `get_auth_status()` only when you need to validate the token is still valid.

---

## 4. Download Management (The "Two Queue" System)

SoulSpot uses external downloaders (Soulseek/slskd) but maintains **strict control** over them.

### The Control Loop

```
┌────────────────────────────────────────────────────────────┐
│                    SOULSPOT INTERNAL QUEUE                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Track 1  │  │ Track 2  │  │ Track 3  │  │ Track 4  │  │
│  │ WAITING  │  │ WAITING  │  │ WAITING  │  │ WAITING  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                            │
│  ↓ Throttled Feeding (5 at a time)                        │
└────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────┐
│                    EXTERNAL QUEUE (slskd)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│  │ Track 1  │  │ Track 2  │  │ Track 3  │                │
│  │ QUEUED   │  │ DOWNLOAD │  │ DOWNLOAD │                │
│  └──────────┘  └──────────┘  └──────────┘                │
│                                                            │
│  SoulSpot monitors and controls via API                    │
└────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────┐
│                      FILE SYSTEM                            │
│  /downloads/completed/Artist - Track.flac                   │
└────────────────────────────────────────────────────────────┘
```

### Control Mechanisms

1. **Internal Queue (SoulSpot's Source of Truth)**:
   - All download requests start here
   - SoulSpot prioritizes and manages this queue
   - Status: `WAITING`, `PENDING`, `QUEUED`, `DOWNLOADING`, `COMPLETED`, `FAILED`

2. **Throttled Feeding**:
   - SoulSpot feeds downloads to slskd incrementally (e.g., 5 at a time)
   - Prevents overwhelming the external service
   - Maintains control over download priority

3. **External Queue (slskd)**:
   - Handles actual file transfer (P2P Soulseek network)
   - SoulSpot polls for status updates
   - Status synced back to internal queue

4. **API Control**:
   - Pause/resume individual downloads
   - Cancel downloads
   - Monitor progress (bytes downloaded, speed, ETA)
   - Circuit breaker for provider health

### Why Two Queues?

**Resilience**:
- If slskd crashes, SoulSpot knows what was downloading
- Can restart downloads from internal queue
- WAITING status allows offline operation (slskd down? Queue still works)

**Provider Abstraction**:
- Can swap Soulseek for Torrents without changing core logic
- Future: Direct Spotify downloads, Deezer downloads
- Single unified queue for all providers

**Control**:
- SoulSpot decides priority (user can reorder queue)
- Can pause downloads without losing state
- Can retry failed downloads with exponential backoff

---

## 5. Summary

| Principle | Rule | Why |
|-----------|------|-----|
| **Autonomy** | SoulSpot makes all decisions | External services don't control state |
| **Multi-Provider** | Always aggregate ALL services | Better coverage, resilience, user freedom |
| **Plugins as Tools** | External APIs are data sources only | Clean abstraction, swappable providers |
| **Two Queues** | Internal queue controls external queue | Resilience, provider abstraction, control |

**Key Takeaway**: SoulSpot is **autonomous** and **multi-provider** by design. Never rely on a single service, never let external services control SoulSpot's state.

---

## See Also

- [Data Standards](./data-standards.md) - DTO definitions and conversion patterns
- [Plugin System](./plugin-system.md) - Plugin interface and implementation
- [Configuration](./configuration.md) - Database-first config architecture
- [Service Separation Principles](./service-separation-principles.md) - Provider abstraction patterns

---

**Document Status**: Migrated from `docs/architecture/CORE_PHILOSOPHY.md`  
**Code Verified**: 2025-12-30  
**Source References**:
- `src/soulspot/infrastructure/plugins/` - Plugin implementations
- `src/soulspot/application/services/app_settings_service.py` - Provider enable checks
- `src/soulspot/domain/ports/plugin.py` - Plugin capability system
- `src/soulspot/api/routers/browse.py` - Multi-provider aggregation example (lines 74-648)
