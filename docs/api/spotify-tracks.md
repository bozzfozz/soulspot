# Spotify API Tracks Documentation

> **Version:** 1.0  
> **Last Updated:** 2025-11-25

---

## Overview

This document describes how SoulSpot integrates with the Spotify Web API to fetch, store, and manage track/song data. It covers relevant endpoints, field mappings, database schema recommendations, deduplication strategies, and synchronization best practices.

---

## 1. Relevant Spotify Endpoints (Track-Related)

| Endpoint | Description | Batch Support |
|----------|-------------|---------------|
| `GET /v1/tracks/{id}` | Full track object | No |
| `GET /v1/tracks?ids={ids}` | Batch fetch (up to 50 IDs) | Yes (max 50) |
| `GET /v1/albums/{id}/tracks` | Album tracks (paginated) | N/A |
| `GET /v1/artists/{id}/top-tracks?market=XX` | Artist top tracks | No |
| `GET /v1/audio-features/{id}` | Audio features for single track | No |
| `GET /v1/audio-features?ids={ids}` | Audio features batch (up to 100) | Yes (max 100) |
| `GET /v1/audio-analysis/{id}` | Detailed audio analysis | No |

### Notes

- **Batch Limits**: `tracks?ids=` supports max 50 IDs; `audio-features?ids=` supports max 100 IDs.
- **Rate Limits**: Handle `429 Too Many Requests` with `Retry-After` header; implement exponential backoff.
- **Authorization**: Public track metadata requires Client Credentials flow; user-specific data requires OAuth.

---

## 2. Track Fields to Store

### 2.1 Required Fields (Minimal Set)

These fields are essential for identification, display, and matching:

| Field | Type | Spotify Source | Description |
|-------|------|----------------|-------------|
| `spotify_id` | `TEXT` | `id` | Unique Spotify track ID |
| `name` | `TEXT` | `name` | Track title |
| `album_spotify_id` | `TEXT` | `album.id` | FK/reference to album |
| `artists` | `JSONB` | `artists[]` | Array of `{spotify_id, name}` |
| `duration_ms` | `INTEGER` | `duration_ms` | Duration in milliseconds |
| `track_number` | `SMALLINT` | `track_number` | Position on disc |
| `disc_number` | `SMALLINT` | `disc_number` | Disc number (multi-disc albums) |
| `explicit` | `BOOLEAN` | `explicit` | Explicit content flag |
| `preview_url` | `TEXT` | `preview_url` | 30-second preview URL (nullable) |
| `isrc` | `TEXT` | `external_ids.isrc` | International Standard Recording Code |
| `external_url` | `TEXT` | `external_urls.spotify` | Spotify web page URL |
| `popularity` | `SMALLINT` | `popularity` | Track popularity (0-100) |
| `last_synced_at` | `TIMESTAMPTZ` | N/A | Last sync timestamp |
| `raw_json` | `JSONB` | entire response | Complete original payload |

### 2.2 Optional Fields (Recommended)

Additional fields useful for enhanced functionality:

| Field | Type | Spotify Source | Description |
|-------|------|----------------|-------------|
| `href` | `TEXT` | `href` | API link to track resource |
| `available_markets` | `TEXT[]` | `available_markets[]` | ISO country codes |
| `linked_from` | `JSONB` | `linked_from` | Link to alternate album editions |
| `musicbrainz_id` | `TEXT` | N/A | Enriched from MusicBrainz |
| `matched_download_id` | `TEXT` (FK) | N/A | FK to download jobs table |
| `popularity_history` | `JSONB` | N/A | Time-series popularity data |

---

## 3. Audio Features

Audio features can be stored as JSONB or normalized into separate columns.

### 3.1 Audio Feature Fields

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `danceability` | `FLOAT` | 0.0-1.0 | How suitable for dancing |
| `energy` | `FLOAT` | 0.0-1.0 | Intensity/activity measure |
| `key` | `INTEGER` | 0-11 | Musical key (pitch class notation) |
| `loudness` | `FLOAT` | dB | Overall loudness in decibels |
| `mode` | `INTEGER` | 0/1 | Major (1) or minor (0) |
| `speechiness` | `FLOAT` | 0.0-1.0 | Presence of spoken words |
| `acousticness` | `FLOAT` | 0.0-1.0 | Acoustic confidence measure |
| `instrumentalness` | `FLOAT` | 0.0-1.0 | Predicts no vocals |
| `liveness` | `FLOAT` | 0.0-1.0 | Audience presence detection |
| `valence` | `FLOAT` | 0.0-1.0 | Musical positiveness |
| `tempo` | `FLOAT` | BPM | Beats per minute |
| `time_signature` | `INTEGER` | 3-7 | Time signature (beats per bar) |

### 3.2 Storage Options

**Option A: JSONB Column** (recommended for flexibility)
```sql
audio_features JSONB
```

**Option B: Normalized Columns** (recommended for queries)
```sql
danceability REAL,
energy REAL,
key SMALLINT,
loudness REAL,
mode SMALLINT,
speechiness REAL,
acousticness REAL,
instrumentalness REAL,
liveness REAL,
valence REAL,
tempo REAL,
time_signature SMALLINT
```

---

## 4. Audio Analysis

Audio analysis is very detailed (segments, beats, sections, bars, tatums). Store only if needed for visualization or beat-matching features.

**Recommendation**: Store as `audio_analysis JSONB` if used; fetch on-demand rather than bulk-storing.

---

## 5. Database Schema

### 5.1 Tracks Table (PostgreSQL)

```sql
CREATE TABLE tracks (
    id              SERIAL PRIMARY KEY,
    spotify_id      TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    album_spotify_id TEXT,
    duration_ms     INTEGER NOT NULL,
    track_number    SMALLINT,
    disc_number     SMALLINT DEFAULT 1,
    explicit        BOOLEAN DEFAULT FALSE,
    preview_url     TEXT,
    isrc            TEXT,
    popularity      SMALLINT,
    available_markets TEXT[],
    artists         JSONB NOT NULL,  -- [{spotify_id, name}, ...]
    href            TEXT,
    external_url    TEXT,
    audio_features  JSONB,
    raw             JSONB,
    last_synced_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.2 Recommended Indexes

```sql
-- Unique constraint on Spotify ID
CREATE UNIQUE INDEX ix_tracks_spotify_id ON tracks(spotify_id);

-- Case-insensitive name search
CREATE INDEX ix_tracks_name_lower ON tracks(LOWER(name));

-- ISRC for deduplication/matching
CREATE INDEX ix_tracks_isrc ON tracks(isrc) WHERE isrc IS NOT NULL;

-- Album relationship
CREATE INDEX ix_tracks_album_spotify_id ON tracks(album_spotify_id);

-- GIN index for JSONB artist queries
CREATE INDEX ix_tracks_artists_gin ON tracks USING GIN(artists);

-- Audio features queries (if normalized columns are used)
CREATE INDEX ix_tracks_popularity ON tracks(popularity);
```

---

## 6. Field Mapping: Spotify Response → Database

### 6.1 Track Object Mapping

| Spotify Field | Database Column |
|---------------|-----------------|
| `id` | `spotify_id` |
| `name` | `name` |
| `album.id` | `album_spotify_id` |
| `duration_ms` | `duration_ms` |
| `track_number` | `track_number` |
| `disc_number` | `disc_number` |
| `explicit` | `explicit` |
| `preview_url` | `preview_url` |
| `external_ids.isrc` | `isrc` |
| `external_urls.spotify` | `external_url` |
| `popularity` | `popularity` |
| `available_markets[]` | `available_markets` |
| `artists[].id` + `artists[].name` | `artists` (JSONB) |
| `href` | `href` |
| *(entire response)* | `raw` |

### 6.2 Audio Features Mapping

Fetch separately via `/v1/audio-features?ids={ids}` and merge into `audio_features` JSONB or dedicated columns.

---

## 7. Deduplication & Matching

### 7.1 Primary Strategy: ISRC

ISRC (International Standard Recording Code) is the best identifier for deduplication:

- Use ISRC to match against MusicBrainz, local library, and SLSKD results.
- Query: `SELECT * FROM tracks WHERE isrc = 'USRC12345678';`

### 7.2 Fallback Strategy: Fuzzy Matching

When ISRC is unavailable, use fuzzy matching:

```python
# Fuzzy match criteria
def generate_match_key(track):
    normalized_title = normalize_string(track.name)
    primary_artist = normalize_string(track.artists[0].name)
    duration_rounded = round(track.duration_ms / 1000, 0)  # seconds
    return f"{normalized_title}|{primary_artist}|{duration_rounded}"
```

**Match Tolerance:**
- Title: Normalized, case-insensitive
- Artist: Primary artist only
- Duration: ±2 seconds tolerance
- Release Year: If available

### 7.3 Match Confidence

Store match confidence for future refinement:

```sql
ALTER TABLE tracks ADD COLUMN match_confidence REAL;
ALTER TABLE tracks ADD COLUMN match_key TEXT;
```

---

## 8. Sync Strategies

### 8.1 Bulk Import/Sync

1. **Collect Spotify IDs**: From playlists, albums, artist top tracks, etc.
2. **Batch Fetch Tracks**: Call `/v1/tracks?ids=` in batches of 50.
3. **Upsert to Database**: Insert new tracks or update existing.
4. **Fetch Audio Features**: Call `/v1/audio-features?ids=` in batches of 100.
5. **Update Audio Features**: Merge into track records.

```python
# Example batch processing
async def sync_tracks(spotify_ids: list[str], access_token: str) -> None:
    # Process in batches of 50 (Spotify limit)
    for batch in chunks(spotify_ids, 50):
        ids_param = ",".join(batch)
        tracks = await spotify_client.get_tracks(ids_param, access_token)
        for track in tracks:
            await upsert_track(track)
    
    # Fetch audio features in batches of 100
    for batch in chunks(spotify_ids, 100):
        ids_param = ",".join(batch)
        features = await spotify_client.get_audio_features(ids_param, access_token)
        for feature in features:
            await update_audio_features(feature)
```

### 8.2 On-Demand Sync

- UI button "Sync Track" → `GET /tracks/{id}` + `GET /audio-features/{id}` → Upsert.

### 8.3 Periodic Sync

- Worker updates `popularity`, `preview_url`, `available_markets` every X hours for watched tracks.
- Track `last_synced_at` to prioritize stale records.

---

## 9. Error Handling

### 9.1 Rate Limiting

```python
async def handle_rate_limit(response: httpx.Response) -> None:
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        logger.warning(f"Rate limited. Retrying after {retry_after}s")
        await asyncio.sleep(retry_after)
```

### 9.2 Common Error Codes

| Status Code | Meaning | Action |
|-------------|---------|--------|
| 400 | Bad Request | Check request parameters |
| 401 | Unauthorized | Refresh access token |
| 403 | Forbidden | Check OAuth scopes |
| 404 | Not Found | Track removed/unavailable |
| 429 | Rate Limited | Wait and retry (see Retry-After) |
| 5xx | Server Error | Retry with exponential backoff |

### 9.3 Track Unavailability

- Tracks can be removed due to licensing, artist requests, etc.
- Mark track as `unavailable` instead of deleting.
- Preserve `raw` JSON for reference.

---

## 10. Important Constraints & Notes

### 10.1 Spotify Limitations

- **No Audio Files**: Spotify only provides `preview_url` (30s) or streaming; no full audio downloads.
- **Preview Availability**: `preview_url` can be `null` for many tracks.
- **Market Restrictions**: `available_markets` affects preview and track availability.
- **Popularity Volatility**: `popularity` changes frequently; consider tracking history.

### 10.2 Batch Limits

| Endpoint | Max Items |
|----------|-----------|
| `tracks?ids=` | 50 |
| `audio-features?ids=` | 100 |
| Pagination (tracks in playlist/album) | 50-100 per page |

### 10.3 Rate Limits

- **General**: ~180 requests/minute (varies by endpoint).
- **Best Practice**: Use batch endpoints, implement backoff, moderate concurrency.

---

## 11. Example: Spotify Track JSON

### 11.1 Track Response (Simplified)

```json
{
  "id": "3n3Ppam7vgaVa1iaRUc9Lp",
  "name": "Mr. Brightside",
  "duration_ms": 222000,
  "explicit": false,
  "track_number": 1,
  "disc_number": 1,
  "artists": [
    {
      "id": "0gxyHStUsqpMadRV0Di1Qt",
      "name": "The Killers"
    }
  ],
  "album": {
    "id": "0W3p9N8kCPLM5iW0e4r5Qp",
    "name": "Hot Fuss"
  },
  "external_ids": {
    "isrc": "USHW30400001"
  },
  "external_urls": {
    "spotify": "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp"
  },
  "preview_url": "https://p.scdn.co/mp3-preview/...",
  "popularity": 78,
  "available_markets": ["DE", "US", "GB"],
  "href": "https://api.spotify.com/v1/tracks/3n3Ppam7vgaVa1iaRUc9Lp"
}
```

### 11.2 Audio Features Response (Simplified)

```json
{
  "id": "3n3Ppam7vgaVa1iaRUc9Lp",
  "danceability": 0.355,
  "energy": 0.926,
  "key": 1,
  "loudness": -4.069,
  "mode": 1,
  "speechiness": 0.0539,
  "acousticness": 0.000986,
  "instrumentalness": 0.0000108,
  "liveness": 0.0933,
  "valence": 0.24,
  "tempo": 148.114,
  "time_signature": 4,
  "duration_ms": 222075
}
```

---

## 12. Enrichment Pipeline

### 12.1 MusicBrainz Integration

1. **Resolve ISRC**: Query MusicBrainz with ISRC to get MBID.
2. **Fetch Metadata**: Retrieve additional metadata (credits, release info).
3. **Store MBID**: Update `musicbrainz_id` column.

### 12.2 Cover Art Archive

1. **Query by MBID**: Fetch cover art from CoverArtArchive.
2. **Store URL or Path**: Link to album artwork.

---

## 13. Usage in SoulSpot

### 13.1 Track Display

- Show: title, artist(s), album, duration, popularity, preview player.
- Link to Spotify page via `external_url`.

### 13.2 Download Integration

- Use ISRC/match_key to find SLSKD candidates.
- Store `matched_download_id` when download job is created.
- Track download status per track.

### 13.3 Deduplication

- Prevent duplicate downloads using ISRC.
- Flag potential duplicates for user review.

---

## Related Documentation

- [SPOTIFY_MODULE.md](../version-3.0/SPOTIFY_MODULE.md) - Full Spotify module specification
- [Library Management API](library-management-api.md) - Library operations
- [Download Management](download-management.md) - Download queue management
- [Advanced Search API](advanced-search-api.md) - Search capabilities

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-25 | 1.0 | Initial documentation |

---

**End of Spotify Tracks API Documentation**
