# Spotify API: Artist Integration

> **Version:** 1.0  
> **Last Updated:** 2025-11-25

---

## Overview

This document describes the integration between SoulSpot and the Spotify Web API for artist-related operations. It covers available endpoints, data models, authentication, rate limiting, and synchronization strategies.

---

## Spotify Endpoints (Artist-related)

### Primary Endpoint

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/artists/{id}` | GET | Retrieve artist details by Spotify ID |

### Optional Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/artists/{id}/related-artists` | GET | Get artists similar to the specified artist |
| `/v1/artists/{id}/albums` | GET | Get albums for an artist (for album links on artist pages) |

> **Note:** Related artists endpoint can be used to build artist recommendation graphs. Albums endpoint is optional since the primary focus is on artist metadata.

---

## Artist Data Model

### Required Fields (Minimum Schema)

These fields **must** be stored for every artist:

| Field | Type | Description |
|-------|------|-------------|
| `spotify_id` | `string` | Unique identifier from Spotify (primary key) |
| `name` | `string` | Artist display name |
| `genres` | `array[string]` | List of genres associated with the artist |
| `popularity` | `int (0-100)` | Spotify popularity score |
| `followers_total` | `int` | Total follower count |
| `images` | `array[ImageObject]` | Artist images (url, height, width) |
| `external_url` | `string` | Spotify page URL |
| `last_synced_at` | `timestamp` | Last synchronization timestamp (UTC) |

### Optional Fields (Useful Extensions)

These fields are optional but provide additional value:

| Field | Type | Description |
|-------|------|-------------|
| `href` | `string` | API link to artist endpoint |
| `popularity_history` | `JSON/time series` | Historical popularity data for trend tracking |
| `related_artists` | `array[spotify_id]` | List of related artist IDs (or separate relation table) |
| `canonical_name` | `string` | Normalized name for matching |
| `aliases` | `array[string]` | Alternative names for the artist |
| `raw_spotify_json` | `JSONB` | Complete original payload for debug/extension |

---

## Database Schema

### PostgreSQL Schema (Reference)

```sql
CREATE TABLE artists (
    -- Internal primary key
    id SERIAL PRIMARY KEY,
    
    -- Spotify identifier (authoritative)
    spotify_id TEXT UNIQUE NOT NULL,
    
    -- Core metadata
    name TEXT NOT NULL,
    genres TEXT[] DEFAULT '{}',
    popularity SMALLINT CHECK (popularity >= 0 AND popularity <= 100),
    followers_total INTEGER,
    images JSONB,  -- [{url, height, width}, ...]
    external_url TEXT,
    href TEXT,
    
    -- Sync tracking
    last_synced_at TIMESTAMP WITH TIME ZONE,
    
    -- Raw data storage
    raw JSONB,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX ix_artists_spotify_id ON artists(spotify_id);
CREATE INDEX ix_artists_name_lower ON artists(LOWER(name));
CREATE INDEX ix_artists_genres ON artists USING GIN(genres);  -- Optional: for genre-based queries
```

### SQLite Schema (Current SoulSpot Implementation)

SoulSpot uses SQLite for portability. The current implementation stores a subset of fields, with additional fields planned for future versions:

```sql
CREATE TABLE artists (
    id TEXT PRIMARY KEY,  -- UUID (internal)
    name TEXT NOT NULL,
    spotify_uri TEXT UNIQUE,  -- spotify:artist:{spotify_id}
    musicbrainz_id TEXT UNIQUE,
    image_url TEXT,  -- Single image URL (320px preferred)
    genres TEXT,  -- JSON array stored as TEXT
    tags TEXT,    -- JSON array stored as TEXT
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_artists_spotify_uri ON artists(spotify_uri);
CREATE INDEX ix_artists_name_lower ON artists(name);
```

> **Implementation Notes:**
> - SQLite stores JSON arrays as TEXT. The application layer handles JSON serialization/deserialization.
> - The `spotify_uri` field contains the full URI (e.g., `spotify:artist:1Xyo4u8uXC1ZmMpatF05PJ`), from which the Spotify ID can be extracted.
> - Fields like `popularity`, `followers_total`, `external_url`, and `last_synced_at` from the reference schema are planned for future implementation and can be stored in a `raw` JSONB/TEXT field until then.
> - For a full-featured implementation, extend the schema with the additional fields from the PostgreSQL reference above.

---

## Spotify API Response Example

### GET `/v1/artists/{id}` Response

```json
{
  "id": "1Xyo4u8uXC1ZmMpatF05PJ",
  "name": "The Weeknd",
  "genres": ["canadian contemporary r&b", "pop"],
  "popularity": 95,
  "followers": {
    "total": 33456789
  },
  "images": [
    {
      "height": 640,
      "url": "https://i.scdn.co/image/...",
      "width": 640
    },
    {
      "height": 320,
      "url": "https://i.scdn.co/image/...",
      "width": 320
    },
    {
      "height": 160,
      "url": "https://i.scdn.co/image/...",
      "width": 160
    }
  ],
  "external_urls": {
    "spotify": "https://open.spotify.com/artist/1Xyo4u8uXC1ZmMpatF05PJ"
  },
  "href": "https://api.spotify.com/v1/artists/1Xyo4u8uXC1ZmMpatF05PJ"
}
```

### Field Mapping

| Spotify Field | SoulSpot Field | Status | Transformation |
|---------------|----------------|--------|----------------|
| `id` | `spotify_uri` | ✅ Implemented | Convert to `spotify:artist:{id}` |
| `name` | `name` | ✅ Implemented | Direct mapping |
| `genres` | `genres` | ✅ Implemented | JSON array (stored as TEXT in SQLite) |
| `images[1].url` | `image_url` | ✅ Implemented | Extract 320px image URL |
| `popularity` | `popularity` | 📋 Planned | Direct mapping (requires schema extension) |
| `followers.total` | `followers_total` | 📋 Planned | Nested field extraction (requires schema extension) |
| `external_urls.spotify` | `external_url` | 📋 Planned | Nested field extraction (requires schema extension) |
| `href` | `href` | 📋 Planned | Direct mapping (requires schema extension) |

> **Note:** Fields marked as "Planned" can be stored in a `raw` JSON field for immediate access while schema extensions are developed.

---

## Authentication & Authorization

### Client Credentials Flow

For public artist data, use the **Client Credentials Flow** (no user scopes required):

```http
POST https://accounts.spotify.com/api/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
client_id={CLIENT_ID}
client_secret={CLIENT_SECRET}
```

**Response:**
```json
{
  "access_token": "BQDxxxxxxxxx...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### User Authorization (For Followed Artists)

When fetching a user's followed artists via `/v1/me/following`, use **Authorization Code Flow with PKCE** and the `user-follow-read` scope.

---

## Rate Limiting

### Spotify Rate Limits

Spotify enforces rate limits on API requests:

- **429 Too Many Requests:** Response includes `Retry-After` header
- **Best Practice:** Implement exponential backoff

### Implementation Strategy

```python
import asyncio
from typing import Any

async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    max_retries: int = 5
) -> dict[str, Any]:
    """Fetch with exponential backoff for rate limit handling."""
    for attempt in range(max_retries):
        response = await client.get(url, headers=headers)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))
            wait_time = retry_after * (2 ** attempt)  # Exponential backoff
            await asyncio.sleep(wait_time)
            continue
            
        response.raise_for_status()
        return response.json()
    
    raise Exception("Max retries exceeded")
```

### Concurrency Limits

- **No batch endpoint for artists:** Unlike tracks (`/v1/tracks?ids=...`), Spotify does not provide a batch artist endpoint
- **Parallel requests:** Limit concurrency (e.g., max 10 concurrent requests)
- **Rate limit awareness:** Monitor 429 responses and back off globally

---

## Synchronization Strategy

### On-Demand Sync

Triggered via UI button "Sync Artist":

1. Fetch `/v1/artists/{spotify_artist_id}` from Spotify (where `spotify_artist_id` is the Spotify artist ID, e.g., `1Xyo4u8uXC1ZmMpatF05PJ`)
2. Parse response and map fields
3. Upsert into database (update if exists, insert if new)
4. Update `last_synced_at` timestamp

```python
from datetime import datetime, UTC
from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

async def sync_artist(spotify_plugin: SpotifyPlugin, spotify_artist_id: str) -> Artist:
    """Sync a single artist from Spotify.
    
    Args:
        spotify_plugin: SpotifyPlugin instance for Spotify API access
        spotify_artist_id: Spotify artist ID (e.g., '1Xyo4u8uXC1ZmMpatF05PJ')
    """
    # Returns ArtistDTO with typed attributes
    artist_dto = await spotify_plugin.get_artist(spotify_artist_id)
    
    artist = Artist(
        spotify_id=artist_dto.id,
        name=artist_dto.name,
        genres=artist_dto.genres,
        popularity=artist_dto.popularity,
        followers_total=artist_dto.followers,
        images=artist_dto.images,
        external_url=artist_dto.external_urls.get("spotify") if artist_dto.external_urls else None,
        href=artist_dto.href,
        last_synced_at=datetime.now(UTC),
    )
    
    return await artist_repository.upsert(artist)
```
```

### Periodic Sync (Background Worker)

For watched/followed artists, run periodic sync:

1. Query artists due for sync (`last_synced_at < NOW() - INTERVAL`)
2. For each artist:
   - Fetch `/v1/artists/{id}`
   - Compare `popularity`, `followers_total`, `genres`, `images`
   - If changed: update record + `last_synced_at`
   - If unchanged: only update `last_synced_at`
3. Store `raw_spotify_json` for future field extensions

**Recommended interval:** Every 6-24 hours (configurable)

### Related Artists Sync (Optional)

Separate job to maintain artist relations:

1. Fetch `/v1/artists/{id}/related-artists`
2. Store relations in a separate table or JSON field
3. Use for artist recommendations and discovery features

---

## Implementation in SoulSpot

### Domain Entity

```python
from dataclasses import dataclass, field
from datetime import datetime, UTC

@dataclass
class Artist:
    """Artist entity representing a music artist."""
    
    id: ArtistId
    name: str
    spotify_uri: SpotifyUri | None = None
    musicbrainz_id: str | None = None
    image_url: str | None = None  # 320px image URL
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
```

### Spotify Client Method

```python
async def get_artist(self, artist_id: str, access_token: str) -> dict[str, Any]:
    """Get artist details from Spotify API.
    
    Args:
        artist_id: Spotify artist ID
        access_token: OAuth access token
        
    Returns:
        Artist information from Spotify
    """
    client = await self._get_client()
    response = await client.get(
        f"{self.API_BASE_URL}/artists/{artist_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json()
```

### Repository Pattern

The `ArtistRepository` handles database operations:

```python
async def get_by_spotify_uri(self, spotify_uri: SpotifyUri) -> Artist | None:
    """Get artist by Spotify URI."""
    stmt = select(ArtistModel).where(ArtistModel.spotify_uri == str(spotify_uri))
    result = await self.session.execute(stmt)
    model = result.scalar_one_or_none()
    # ... convert to domain entity
```

---

## Best Practices

### Data Quality

1. **Store raw JSON:** Always store `raw_spotify_json` for debugging and future field additions
2. **Normalize genres:** Trim whitespace, lowercase for consistency, use GIN index for fast search
3. **Image handling:** Store URLs only; implement TTL-based caching if using local CDN proxy

### Duplicate Handling

1. **`spotify_id` is authoritative:** Use as the unique identifier
2. **Local artist matching:** For artists without Spotify ID, use fuzzy string matching on name
3. **MusicBrainz fallback:** Cross-reference with MusicBrainz ID when available

### No Audio/Track Files

> **Important:** Spotify API provides metadata only, not audio files. Artist sync is purely for metadata enrichment and library organization.

---

## API Endpoints in SoulSpot

### Future Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/artists/{id}/sync` | POST | Trigger on-demand artist sync |
| `/api/artists/{id}` | GET | Get artist details |
| `/api/artists/search` | GET | Search artists by name/genre |
| `/api/artists/followed` | GET | List user's followed artists |

---

## Related Documentation

- [Advanced Search API](advanced-search-api.md) - Search artists, albums, tracks
- [Library Management API](library-management-api.md) - Library organization
- [Download Management](download-management.md) - Download operations

---

## References

- [Spotify Web API - Artists](https://developer.spotify.com/documentation/web-api/reference/get-an-artist)
- [Spotify Web API - Get User's Followed Artists](https://developer.spotify.com/documentation/web-api/reference/get-followed)
- [Spotify Authorization Guide](https://developer.spotify.com/documentation/web-api/concepts/authorization)
