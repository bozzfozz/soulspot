# SoulSpot Core Philosophy

> **"SoulSpot is Autonomous"**

## 1. The Autonomy Principle
SoulSpot is a self-contained, autonomous system. It manages, processes, and organizes everything internally. It does not rely on external services for logic or state management.

- **SoulSpot is the Brain**: It makes all decisions (what to download, when to pause, how to tag).
- **External Services are Tools**: Other services are merely "dumb" tools used by SoulSpot to achieve its goals.

## 2. Plugin Architecture (Data Sources)
Services like **Spotify**, **Deezer**, and **Tidal** are treated strictly as **Data Sources (Plugins)**.

- **Role**: They provide metadata, playlists, and discovery data.
- **Constraint**: SoulSpot fetches data from them, but never relies on them for storage or business logic.
- **Abstraction**: SoulSpot converts external data into its own internal Domain Entities immediately.

## 3. Multi-Service Aggregation Principle ⭐ NEW

> **"Always use ALL available services, deduplicate, and combine results"**

### The Rule
For ANY feature that fetches data from external services (Browse, Search, Discovery, New Releases, etc.):

1. **Query ALL enabled services** - Not just one. Deezer, Spotify, Tidal, etc.
2. **Aggregate results** - Combine all responses into a unified list
3. **Deduplicate** - Use normalized keys (artist_name + album_title, ISRC, etc.)
4. **Tag source** - Each result keeps a `source` field to show where it came from
5. **Graceful fallback** - If one service fails, show results from others

### Why?
- **Better Coverage**: Different services have different catalogs
- **User Freedom**: Users aren't locked to one ecosystem
- **Resilience**: If Spotify is down, Deezer still works
- **Discovery**: Users see music they wouldn't find on a single platform

### Implementation Pattern
```python
async def get_new_releases():
    all_releases = []
    seen_keys = set()
    
    # 1. Try Deezer (no auth needed)
    if settings.deezer_enabled:
        deezer_releases = await deezer_plugin.get_new_releases()
        for r in deezer_releases:
            key = normalize(r.artist, r.title)
            if key not in seen_keys:
                seen_keys.add(key)
                r.source = "deezer"
                all_releases.append(r)
    
    # 2. Try Spotify (needs auth)
    if settings.spotify_enabled and spotify_authenticated:
        spotify_releases = await spotify_plugin.get_new_releases()
        for r in spotify_releases:
            key = normalize(r.artist, r.title)
            if key not in seen_keys:
                seen_keys.add(key)
                r.source = "spotify"
                all_releases.append(r)
    
    # 3. Future: Tidal, etc.
    
    return sorted(all_releases, key=lambda x: x.release_date, reverse=True)
```

### Service Availability
Services can be disabled in two ways:
1. **Provider Disabled**: User toggled "off" in Settings (is_provider_enabled check)
2. **Not Authenticated**: User hasn't completed OAuth flow (is_authenticated check)

**Check Order (IMPORTANT!)**:
```python
# 1. FIRST: Check if provider is enabled
if not await settings.is_provider_enabled("spotify"):
    return {"skipped_provider_disabled": True}

# 2. SECOND: Check if user is authenticated
if not spotify_plugin.is_authenticated:
    return {"skipped_not_authenticated": True}

# 3. THEN: Do the actual operation
result = await spotify_plugin.get_followed_artists()
```

**Why this order?**
- Provider check is cheap (DB lookup)
- Auth check is cheap (memory check)
- API calls are expensive (network + rate limits)
- Don't waste API calls if user disabled the service

### What "Not Authenticated" Means
- `is_authenticated`: Quick sync check - "do we have a token?"
- Does NOT validate the token (it might be expired)
- Use `get_auth_status()` for full validation (makes API call)

**For Services Without Auth (Deezer Public API)**:
- Deezer browse/search works WITHOUT auth
- Only user-specific operations (my playlists, my favorites) need auth
- Check `is_authenticated` only for user-specific operations

## 4. Download Management (The "Two Queue" System)
SoulSpot uses external downloaders (like **Soulseek/slskd**) but maintains strict control over them.

### The Control Loop
1.  **Internal Queue (SoulSpot)**: All download requests start here. SoulSpot prioritizes and manages this queue.
2.  **Throttled Feeding**: SoulSpot feeds downloads to the external service (slskd) incrementally (e.g., 5 at a time).
3.  **External Queue (Soulseek)**: The external service handles the actual file transfer.
4.  **API Control**: SoulSpot constantly monitors and controls the external service via API (pausing, removing, checking status).

**Why?**
- Prevents overwhelming the external service.
- Keeps the "Source of Truth" inside SoulSpot.
- Allows swapping download providers (e.g., switching from Soulseek to Torrent) without changing the core logic.

## 5. Summary
**We are completely autonomous.** Other services exist only to serve data to SoulSpot.
**We aggregate ALL services.** Never rely on just one data source when multiple are available.
