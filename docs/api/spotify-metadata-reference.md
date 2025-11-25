# Spotify API Metadata Reference

> **Version:** 1.0  
> **Last Updated:** 2025-11-25

---

## Overview

This document provides a comprehensive reference for Spotify API metadata fields that Soulspot stores and utilizes. Fields are organized by priority (Minimal vs. Optional) and categorized by their primary use case: identification, deduplication, matching, UI display, or enrichment.

**Design Principles:**
- Store minimal data for core functionality (identification, search, display)
- Preserve `raw_spotify_json` for future field expansion without re-fetching
- Use standard identifiers (ISRC, UPC, MBID) for cross-source matching
- Index fields used in frequent queries (lookups, deduplication)

---

## Table of Contents

1. [Identifiers (Mandatory)](#1-identifiers-mandatory)
2. [Basic Metadata (Minimal for Display & Search)](#2-basic-metadata-minimal-for-display--search)
3. [Provenance & Change Detection](#3-provenance--change-detection)
4. [Availability / Market / Rights](#4-availability--market--rights)
5. [Matching / Dedup / Confidence Fields](#5-matching--dedup--confidence-fields)
6. [Audio Enrichment (Optional)](#6-audio-enrichment-optional)
7. [Temporal / Analytics (Optional)](#7-temporal--analytics-optional)
8. [UI / UX Additional Data (Optional)](#8-ui--ux-additional-data-optional)
9. [Storage Types & Index Recommendations](#9-storage-types--index-recommendations)
10. [Entity-Specific Field Reference](#10-entity-specific-field-reference)
11. [Enrichment & Cross-Reference Sources](#11-enrichment--cross-reference-sources)
12. [Rate Limits & Auth Practicalities](#12-rate-limits--auth-practicalities)
13. [Suggested Minimal Set for MVP](#13-suggested-minimal-set-for-mvp)

---

## 1. Identifiers (Mandatory)

These fields are **required** for every Spotify object to enable unique identification, upsert operations, and cross-source matching.

| Field | Type | Description | Use Case | Index |
|-------|------|-------------|----------|-------|
| `spotify_id` | `TEXT` | Spotify's primary key (22-char base62) | Unique upsert, references | `UNIQUE` |
| `external_ids` | `JSONB` | Container for ISRC (tracks), UPC (albums) | Dedup, multi-source matching | `BTREE` on `isrc`/`upc` |
| `uri` | `TEXT` | Spotify URI (e.g., `spotify:track:...`) | Deep links, API calls | - |
| `external_url` | `TEXT` | Browser URL to Spotify | UI link to stream | - |

### External IDs Structure

```json
{
  "isrc": "USRC11700001",  // Track only - International Standard Recording Code
  "upc": "012345678901",   // Album only - Universal Product Code
  "ean": "5012345678901"   // Album only - European Article Number (rare)
}
```

**Why these matter:**
- `spotify_id`: Definitive Spotify reference. Changes if track is re-uploaded.
- `isrc`: **Best dedup key for tracks** - survives re-releases, remasters (usually).
- `upc`: **Best dedup key for albums** - identifies physical/digital releases.

---

## 2. Basic Metadata (Minimal for Display & Search)

These fields enable basic UI display, search, and relational queries. All are considered **minimal requirements**.

| Field | Type | Applies To | Description | Index |
|-------|------|------------|-------------|-------|
| `name` / `title` | `TEXT` | All | Display name | `BTREE`, `lower()` |
| `type` | `TEXT` | All | Object type: `artist`, `album`, `track`, `playlist` | - |
| `primary_artist` / `artists` | `JSONB` / FK | Track, Album | Artist references | `GIN` or FK table |
| `release_date` | `TEXT` | Album, Track | ISO date (YYYY, YYYY-MM, YYYY-MM-DD) | `BTREE` |
| `release_date_precision` | `TEXT` | Album | Precision: `year`, `month`, `day` | - |
| `duration_ms` | `INTEGER` | Track | Duration in milliseconds | - |
| `explicit` | `BOOLEAN` | Track | Explicit content flag | `BTREE` |
| `popularity` | `SMALLINT` | Artist, Album, Track | 0-100 popularity score | - |
| `followers_total` | `INTEGER` | Artist, Playlist owner | Follower count | - |
| `tracks_total` / `total_tracks` | `INTEGER` | Playlist, Album | Number of tracks | - |
| `images` | `JSONB` | All | Array of `{url, height, width}` | - |
| `last_synced_at` | `TIMESTAMPTZ` | All | Last sync timestamp | `BTREE` |
| `raw_spotify_json` | `JSONB` | All | Complete API response | - |

### Images Structure

```json
[
  {"url": "https://i.scdn.co/image/...", "height": 640, "width": 640},
  {"url": "https://i.scdn.co/image/...", "height": 320, "width": 320},
  {"url": "https://i.scdn.co/image/...", "height": 64, "width": 64}
]
```

**Storage Note:** Store URLs, not binary blobs. Spotify CDN URLs are stable and fast.

---

## 3. Provenance & Change Detection

Fields for tracking data origin and detecting changes during incremental syncs.

| Field | Type | Description | Use Case |
|-------|------|-------------|----------|
| `source` | `TEXT` | Origin: `"spotify"` | Multi-source tracking |
| `snapshot_id` | `TEXT` | Playlist version hash | Change detection |
| `etag` | `TEXT` | HTTP ETag (if available) | Conditional requests |
| `checksum` | `TEXT` | Hash of `raw_spotify_json` | Change detection |
| `fetched_at` | `TIMESTAMPTZ` | When data was retrieved | Staleness detection |
| `last_synced_at` | `TIMESTAMPTZ` | Last successful sync | Incremental syncs |

### Snapshot ID Usage

The `snapshot_id` is crucial for playlist change detection:

```python
# Check if playlist changed since last sync
if current_snapshot_id != stored_snapshot_id:
    # Fetch full playlist - tracks have changed
    pass
else:
    # Skip - playlist unchanged
    pass
```

---

## 4. Availability / Market / Rights

Fields related to geographic availability and content rights.

| Field | Type | Applies To | Description |
|-------|------|------------|-------------|
| `available_markets` | `TEXT[]` / `JSONB` | Track, Album | ISO 3166-1 alpha-2 country codes |
| `copyrights` | `JSONB` | Album | Copyright notices `[{text, type}]` |
| `label` | `TEXT` | Album | Record label name |
| `is_local` | `BOOLEAN` | PlaylistItem | Local file (no Spotify ID) |
| `restrictions` | `JSONB` | Track | Market/product restrictions |

### Available Markets Example

```json
["US", "GB", "DE", "FR", "JP", "AU"]
```

### Handling Local Tracks

```python
# Local tracks have NO spotify_id - handle specially
if is_local:
    # Use track name + artist for matching
    # Generate internal ID
    pass
```

---

## 5. Matching / Dedup / Confidence Fields

Fields for advanced matching, deduplication, and confidence scoring.

| Field | Type | Description | Use Case |
|-------|------|-------------|----------|
| `match_key` | `TEXT` | Normalized fingerprint | Fast exact matching |
| `match_confidence` | `FLOAT` | Match algorithm score (0.0-1.0) | Quality assessment |
| `matched_external_id` | `TEXT` | Linked MusicBrainz ID / internal ID | Cross-source reference |
| `matched_download_candidate_id` | `FK` | Link to download job | Download tracking |

### Match Key Generation

```python
def generate_match_key(name: str, artist: str, duration_ms: int) -> str:
    """
    Generate normalized match key for deduplication.
    
    Normalizations:
    - Lowercase
    - Remove parenthetical suffixes: (Remastered), (Live), etc.
    - Normalize featuring: feat. → featuring
    - Round duration to 5-second buckets
    """
    normalized_name = normalize_title(name)
    normalized_artist = normalize_artist(artist)
    duration_bucket = (duration_ms // 5000) * 5000
    
    return f"{normalized_name}|{normalized_artist}|{duration_bucket}"
```

---

## 6. Audio Enrichment (Optional)

Audio analysis features from Spotify's `/v1/audio-features` endpoint. Useful for mood-based playlisting, recommendations, and advanced search.

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `audio_features` | `JSONB` | - | Container for all features |
| `danceability` | `FLOAT` | 0.0-1.0 | Suitability for dancing |
| `energy` | `FLOAT` | 0.0-1.0 | Intensity and activity |
| `key` | `INTEGER` | 0-11 | Pitch class (C=0, C#=1, ...) |
| `loudness` | `FLOAT` | -60 to 0 dB | Overall loudness |
| `mode` | `INTEGER` | 0/1 | Major (1) or minor (0) |
| `speechiness` | `FLOAT` | 0.0-1.0 | Presence of spoken words |
| `acousticness` | `FLOAT` | 0.0-1.0 | Acoustic vs. electronic |
| `instrumentalness` | `FLOAT` | 0.0-1.0 | Lack of vocals |
| `liveness` | `FLOAT` | 0.0-1.0 | Presence of audience |
| `valence` | `FLOAT` | 0.0-1.0 | Musical positiveness |
| `tempo` | `FLOAT` | BPM | Beats per minute |
| `time_signature` | `INTEGER` | 3-7 | Beats per bar |

### Audio Features JSON Structure

```json
{
  "danceability": 0.735,
  "energy": 0.578,
  "key": 5,
  "loudness": -11.84,
  "mode": 0,
  "speechiness": 0.0461,
  "acousticness": 0.514,
  "instrumentalness": 0.0902,
  "liveness": 0.159,
  "valence": 0.624,
  "tempo": 98.002,
  "time_signature": 4
}
```

### Audio Analysis (Heavy)

The `/v1/audio-analysis` endpoint provides detailed segment-by-segment analysis. **Only store if needed** for:
- Visualizations (waveforms, beat grids)
- DJ/beatmatching features
- Advanced audio fingerprinting

---

## 7. Temporal / Analytics (Optional)

Fields for historical tracking and analytics.

| Field | Type | Description |
|-------|------|-------------|
| `popularity_history` | `JSONB` / Timeseries table | Historical popularity scores |
| `last_played` | `TIMESTAMPTZ` | Last local playback |
| `last_seen` | `TIMESTAMPTZ` | Last seen in playlist sync |
| `last_requested` | `TIMESTAMPTZ` | Last user request |
| `created_at` | `TIMESTAMPTZ` | Record creation time |
| `updated_at` | `TIMESTAMPTZ` | Record update time |

### Popularity History Storage Options

**Option A: JSONB array (simple, limited queries)**
```json
[
  {"date": "2025-01-01", "popularity": 45},
  {"date": "2025-01-08", "popularity": 47}
]
```

**Option B: Separate timeseries table (recommended for analytics)**
```sql
CREATE TABLE popularity_history (
    entity_type TEXT,
    entity_id TEXT,
    recorded_at TIMESTAMPTZ,
    popularity SMALLINT,
    PRIMARY KEY (entity_type, entity_id, recorded_at)
);
```

---

## 8. UI / UX Additional Data (Optional)

Fields that enhance the user interface and experience.

| Field | Type | Applies To | Description |
|-------|------|------------|-------------|
| `description` | `TEXT` | Playlist | User-provided description |
| `owner` | `JSONB` | Playlist | Owner info `{id, display_name}` |
| `collaborative` | `BOOLEAN` | Playlist | Collaborative playlist flag |
| `public` | `BOOLEAN` | Playlist | Public visibility |
| `track_added_at` | `TIMESTAMPTZ` | PlaylistItem | When track was added |
| `track_added_by` | `JSONB` | PlaylistItem | Who added `{id}` |
| `preview_url` | `TEXT` | Track | 30-second preview MP3 URL |
| `album_type` | `TEXT` | Album | `album`, `single`, `compilation` |
| `genres` | `TEXT[]` / `JSONB` | Artist | Artist genres array |

### Owner Structure

```json
{
  "id": "spotify_user_id",
  "display_name": "User Display Name",
  "external_urls": {
    "spotify": "https://open.spotify.com/user/..."
  }
}
```

---

## 9. Storage Types & Index Recommendations

### Recommended Column Types

| Data Type | SQLAlchemy | PostgreSQL | SQLite | Use For |
|-----------|------------|------------|--------|---------|
| Identifiers | `String(36)` | `VARCHAR(36)` | `TEXT` | IDs, URIs |
| Names | `String(255)` | `VARCHAR(255)` | `TEXT` | Titles, names |
| Long text | `Text` | `TEXT` | `TEXT` | Descriptions |
| JSON data | `JSONB` | `JSONB` | `TEXT` (JSON) | Arrays, raw payloads |
| Timestamps | `DateTime(timezone=True)` | `TIMESTAMPTZ` | `TEXT` | All dates |
| Numbers | `Integer`, `SmallInteger`, `Float` | `INTEGER`, `SMALLINT`, `FLOAT` | `INTEGER`, `REAL` | Counts, scores |
| Booleans | `Boolean` | `BOOLEAN` | `INTEGER` | Flags |

### Index Strategy

| Index Type | Fields | Purpose |
|------------|--------|---------|
| `UNIQUE` | `spotify_id` | Primary lookup |
| `UNIQUE` | `isrc` (tracks) | Deduplication |
| `UNIQUE` | `upc` (albums) | Deduplication |
| `BTREE` | `name`, `lower(name)` | Text search |
| `BTREE` | `release_date` | Date filtering |
| `BTREE` | `last_synced_at` | Incremental sync |
| `BTREE` | `match_key` | Fast dedup lookups |
| `GIN` | `artists` (JSONB) | JSONB search |
| `GIN` | `genres` (JSONB) | Genre filtering |
| Composite | `(title, artist_id)` | Title+artist lookups |

### SQLite Considerations

SQLite lacks native `JSONB` - store as `TEXT` and parse in application:

```python
import json

# Store
model.genres = json.dumps(["rock", "alternative"])

# Retrieve
genres = json.loads(model.genres) if model.genres else []
```

---

## 10. Entity-Specific Field Reference

### Artist

| Field | Priority | Type | Index | Description |
|-------|----------|------|-------|-------------|
| `spotify_id` | Minimal | `TEXT` | `UNIQUE` | Spotify artist ID |
| `name` | Minimal | `TEXT` | `BTREE`, `lower()` | Artist name |
| `genres` | Minimal | `JSONB` | `GIN` | Genre tags |
| `popularity` | Minimal | `SMALLINT` | - | 0-100 score |
| `followers_total` | Minimal | `INTEGER` | - | Follower count |
| `images` | Minimal | `JSONB` | - | Profile images |
| `external_url` | Minimal | `TEXT` | - | Spotify URL |
| `last_synced_at` | Minimal | `TIMESTAMPTZ` | `BTREE` | Sync timestamp |
| `raw_spotify_json` | Minimal | `JSONB` | - | Full response |
| `musicbrainz_id` | Optional | `TEXT` | `UNIQUE` | MusicBrainz MBID |

### Album

| Field | Priority | Type | Index | Description |
|-------|----------|------|-------|-------------|
| `spotify_id` | Minimal | `TEXT` | `UNIQUE` | Spotify album ID |
| `name` | Minimal | `TEXT` | `BTREE` | Album title |
| `album_type` | Minimal | `TEXT` | `BTREE` | album/single/compilation |
| `release_date` | Minimal | `TEXT` | `BTREE` | ISO date |
| `release_date_precision` | Minimal | `TEXT` | - | year/month/day |
| `total_tracks` | Minimal | `INTEGER` | - | Track count |
| `images` | Minimal | `JSONB` | - | Cover art URLs |
| `artists` | Minimal | `JSONB` / FK | `GIN` | Artist IDs |
| `external_ids.upc` | Minimal | `TEXT` | `BTREE` | UPC code |
| `label` | Optional | `TEXT` | - | Record label |
| `copyrights` | Optional | `JSONB` | - | Copyright info |
| `external_url` | Minimal | `TEXT` | - | Spotify URL |
| `last_synced_at` | Minimal | `TIMESTAMPTZ` | `BTREE` | Sync timestamp |
| `raw_spotify_json` | Minimal | `JSONB` | - | Full response |
| `musicbrainz_id` | Optional | `TEXT` | `UNIQUE` | MusicBrainz MBID |

### Track

| Field | Priority | Type | Index | Description |
|-------|----------|------|-------|-------------|
| `spotify_id` | Minimal | `TEXT` | `UNIQUE` | Spotify track ID |
| `name` | Minimal | `TEXT` | `BTREE`, `lower()` | Track title |
| `album_spotify_id` | Minimal | `TEXT` | `BTREE` | Album reference |
| `artists` | Minimal | `JSONB` / FK | `GIN` | Artist IDs |
| `duration_ms` | Minimal | `INTEGER` | - | Duration |
| `explicit` | Minimal | `BOOLEAN` | `BTREE` | Explicit flag |
| `track_number` | Minimal | `INTEGER` | - | Position on album |
| `disc_number` | Minimal | `INTEGER` | - | Disc number |
| `preview_url` | Optional | `TEXT` | - | 30s preview |
| `external_ids.isrc` | Minimal | `TEXT` | `UNIQUE` | ISRC code |
| `popularity` | Optional | `SMALLINT` | - | 0-100 score |
| `audio_features` | Optional | `JSONB` | `GIN` | Audio analysis |
| `external_url` | Minimal | `TEXT` | - | Spotify URL |
| `last_synced_at` | Minimal | `TIMESTAMPTZ` | `BTREE` | Sync timestamp |
| `raw_spotify_json` | Minimal | `JSONB` | - | Full response |
| `musicbrainz_id` | Optional | `TEXT` | `UNIQUE` | MusicBrainz MBID |

### Playlist

| Field | Priority | Type | Index | Description |
|-------|----------|------|-------|-------------|
| `spotify_id` | Minimal | `TEXT` | `UNIQUE` | Spotify playlist ID |
| `name` | Minimal | `TEXT` | `BTREE` | Playlist name |
| `description` | Optional | `TEXT` | - | User description |
| `owner` | Minimal | `JSONB` | - | Owner info |
| `public` | Optional | `BOOLEAN` | - | Visibility |
| `collaborative` | Optional | `BOOLEAN` | - | Collaborative flag |
| `followers_total` | Optional | `INTEGER` | - | Follower count |
| `images` | Minimal | `JSONB` | - | Cover images |
| `snapshot_id` | Minimal | `TEXT` | - | Version hash |
| `tracks_total` | Minimal | `INTEGER` | - | Track count |
| `external_url` | Minimal | `TEXT` | - | Spotify URL |
| `last_synced_at` | Minimal | `TIMESTAMPTZ` | `BTREE` | Sync timestamp |
| `raw_spotify_json` | Minimal | `JSONB` | - | Full response |

### PlaylistItem

| Field | Priority | Type | Index | Description |
|-------|----------|------|-------|-------------|
| `playlist_id` | Minimal | `FK` | Composite PK | Playlist reference |
| `position` | Minimal | `INTEGER` | `BTREE` | Track position |
| `added_at` | Minimal | `TIMESTAMPTZ` | - | When added |
| `added_by` | Optional | `JSONB` | - | Who added |
| `is_local` | Minimal | `BOOLEAN` | - | Local file flag |
| `track_spotify_id` | Minimal | `TEXT` / FK | - | Track reference |
| `track_raw` | Optional | `JSONB` | - | Track data snapshot |
| `created_at` | Internal | `TIMESTAMPTZ` | - | Record created |

---

## 11. Enrichment & Cross-Reference Sources

### External Sources for Enrichment

| Source | Data Types | Identifier | Use Case |
|--------|------------|------------|----------|
| **MusicBrainz** | MBID, genres, credits, release grouping | Recording/Release/Artist MBID | Canonical IDs, detailed credits |
| **CoverArtArchive** | Album artwork | Release MBID | Alternative cover art |
| **ISRC Registry** | Track verification | ISRC | Authoritative track identification |
| **Last.fm** | Tags, scrobbles, similar artists | Artist/Track name | Community tags, listening stats |
| **Discogs** | Vinyl-specific metadata | Release ID | Physical release data |

### Cross-Reference Flow

```
Spotify Track
    ↓ ISRC lookup
MusicBrainz Recording
    ↓ Release Group
MusicBrainz Release
    ↓ Cover Art Archive
Album Artwork
```

### MusicBrainz Matching Strategy

```python
def match_to_musicbrainz(track: SpotifyTrack) -> str | None:
    """
    Match Spotify track to MusicBrainz recording.
    
    Priority:
    1. ISRC lookup (most reliable)
    2. Artist + Title + Duration fuzzy match
    3. Album + Track number match
    """
    # 1. Try ISRC
    if track.isrc:
        mbid = lookup_by_isrc(track.isrc)
        if mbid:
            return mbid
    
    # 2. Fuzzy match
    candidates = search_recordings(
        artist=track.artist_name,
        title=track.name,
        duration_ms=track.duration_ms
    )
    
    # 3. Score and select best match
    return select_best_match(candidates, track)
```

---

## 12. Rate Limits & Auth Practicalities

### Authentication Methods

| Method | Scope | Use Case |
|--------|-------|----------|
| **Client Credentials** | Public data only | Background sync, search |
| **Authorization Code + PKCE** | User's private data | Private playlists, user library |

### Rate Limits

| Limit Type | Value | Notes |
|------------|-------|-------|
| Standard rate | ~180 requests/minute | Rolling window |
| Burst rate | Higher initially | Decreases with sustained load |
| Retry-After | Header value | Seconds to wait on 429 |

### Best Practices

1. **Use batch endpoints:**
   - `/v1/tracks?ids=id1,id2,...` (max 50)
   - `/v1/audio-features?ids=id1,id2,...` (max 100)
   - `/v1/artists?ids=id1,id2,...` (max 50)

2. **Implement exponential backoff:**
   ```python
   async def fetch_with_retry(url: str, max_retries: int = 3):
       for attempt in range(max_retries):
           response = await client.get(url)
           if response.status_code == 429:
               retry_after = int(response.headers.get("Retry-After", 1))
               await asyncio.sleep(retry_after * (2 ** attempt))
               continue
           return response
       raise RateLimitExceeded()
   ```

3. **Cache aggressively:**
   - Artist data: 24-hour cache
   - Album data: 24-hour cache
   - Track data: 24-hour cache
   - Playlist data: Check `snapshot_id` before full fetch

4. **Persist raw JSON:**
   - Store complete API responses
   - Extract additional fields later without re-fetching
   - Useful for debugging and analytics

---

## 13. Suggested Minimal Set for MVP

The following fields represent the **minimum viable data** for each entity type to support core Soulspot functionality.

### Artist (MVP)

```json
{
  "spotify_id": "0OdUWJ0sBjDrqHygGUXeCF",
  "name": "Band of Horses",
  "genres": ["indie rock", "alternative rock"],
  "popularity": 68,
  "followers_total": 1234567,
  "images": [{"url": "...", "height": 640, "width": 640}],
  "external_url": "https://open.spotify.com/artist/...",
  "last_synced_at": "2025-01-15T10:30:00Z",
  "raw_spotify_json": {...}
}
```

### Album (MVP)

```json
{
  "spotify_id": "4aawyAB9vmqN3uQ7FjRGTy",
  "name": "Everything All The Time",
  "album_type": "album",
  "release_date": "2006-03-21",
  "release_date_precision": "day",
  "total_tracks": 10,
  "images": [{"url": "...", "height": 640, "width": 640}],
  "artists": [{"id": "0OdUWJ0sBjDrqHygGUXeCF", "name": "Band of Horses"}],
  "external_ids": {"upc": "012345678901"},
  "label": "Sub Pop",
  "external_url": "https://open.spotify.com/album/...",
  "last_synced_at": "2025-01-15T10:30:00Z",
  "raw_spotify_json": {...}
}
```

### Track (MVP)

```json
{
  "spotify_id": "7GhIk7Il098yCjg4BQjzvb",
  "name": "The Funeral",
  "album_spotify_id": "4aawyAB9vmqN3uQ7FjRGTy",
  "artists": [{"id": "0OdUWJ0sBjDrqHygGUXeCF", "name": "Band of Horses"}],
  "duration_ms": 325000,
  "explicit": false,
  "track_number": 3,
  "disc_number": 1,
  "preview_url": "https://p.scdn.co/mp3-preview/...",
  "external_ids": {"isrc": "USRC11700001"},
  "popularity": 75,
  "external_url": "https://open.spotify.com/track/...",
  "last_synced_at": "2025-01-15T10:30:00Z",
  "raw_spotify_json": {...}
}
```

### Playlist (MVP)

```json
{
  "spotify_id": "37i9dQZF1DXcBWIGoYBM5M",
  "name": "Today's Top Hits",
  "description": "The hottest tracks right now",
  "owner": {"id": "spotify", "display_name": "Spotify"},
  "public": true,
  "collaborative": false,
  "followers_total": 35000000,
  "images": [{"url": "...", "height": 640, "width": 640}],
  "snapshot_id": "MTY3...",
  "tracks_total": 50,
  "external_url": "https://open.spotify.com/playlist/...",
  "last_synced_at": "2025-01-15T10:30:00Z",
  "raw_spotify_json": {...}
}
```

### PlaylistItem (MVP)

```json
{
  "playlist_id": "internal-uuid",
  "position": 0,
  "added_at": "2025-01-10T08:00:00Z",
  "added_by": {"id": "user123"},
  "is_local": false,
  "track_spotify_id": "7GhIk7Il098yCjg4BQjzvb",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

## Implementation Notes

### Current Soulspot Models

The current Soulspot database models store:

> **Note:** Model definitions can be found in `src/soulspot/infrastructure/persistence/models.py`

- **Artists**: `spotify_uri`, `musicbrainz_id`, `name`, `image_url`, `genres`, `tags`
- **Albums**: `spotify_uri`, `musicbrainz_id`, `title`, `artist_id`, `release_year`, `artwork_path`
- **Tracks**: `spotify_uri`, `musicbrainz_id`, `isrc`, `title`, `artist_id`, `album_id`, `duration_ms`, `genre`
- **Playlists**: `spotify_uri`, `name`, `description`, `source`
- **PlaylistTracks**: `playlist_id`, `track_id`, `position`, `added_at`

### Recommended Enhancements

Based on this reference, consider adding:

1. **`raw_spotify_json`**: For future-proofing and debugging
2. **`external_ids` JSONB**: For UPC (albums) storage
3. **`snapshot_id`**: For playlist change detection
4. **`popularity`**: For UI display and sorting
5. **`audio_features` JSONB**: For advanced search and recommendations
6. **`match_key`**: For efficient deduplication

---

## Related Documentation

- [Metadata Enrichment](../features/metadata-enrichment.md) - Multi-source enrichment workflow
- [API Overview](./README.md) - Soulspot API reference
- [Architecture](../project/architecture.md) - System design
