# Metadata Enrichment

**Category:** Features  
**Status:** ✅ Active  
**Last Updated:** 2025-11-25  
**Related Docs:** [Local Library Enrichment](./local-library-enrichment.md) | [API Reference: Metadata](../03-api-reference/metadata.md)

---

## Overview

Metadata Enrichment enriches track, artist, and album metadata from multiple sources: Spotify, MusicBrainz, and Last.fm. Uses authority hierarchy for intelligent conflict resolution.

---

## Features

### Multi-Source Enrichment

Metadata fetched from multiple sources:

| Source | Data Types | Priority |
|--------|------------|----------|
| **Manual** | All manual changes | Highest (1) |
| **MusicBrainz** | MBID, Genres, Release Dates | High (2) |
| **Spotify** | URIs, Popularity, Audio Features | Medium (3) |
| **Last.fm** | Tags, Scrobbles, Similar Artists | Low (4) |

---

### Authority Hierarchy

Conflicts resolved by priority:

```
Manual > MusicBrainz > Spotify > Last.fm
```

**Example:** If MusicBrainz and Spotify provide different genres, MusicBrainz wins. Manual changes always override everything.

---

### Conflict Resolution

- **Automatic Resolution:** Based on authority hierarchy
- **Manual Resolution:** User chooses source or enters custom value
- **Conflict Tracking:** All conflicts logged

---

### Tag Normalization

Automatic tag standardization:
- "feat." → "featuring"
- "ft." → "featuring"
- Genre normalization

---

## Usage (Web UI)

### Enrich Track

1. Open track details
2. Click **Enrich Metadata**
3. Select desired sources
4. Click **Enrich**

---

### Resolve Conflicts

1. Open track with metadata conflicts
2. Select desired source for each field
3. Or enter custom value
4. Click **Save**

---

### Batch Enrichment

1. Navigate to **Library** → **Metadata**
2. Click **Fix All**
3. All tracks with missing metadata enriched

---

## API Endpoints

### POST `/api/metadata/enrich`

Enrich track metadata.

**Request:**
```json
{
  "track_id": "track-uuid",
  "force_refresh": false,
  "enrich_artist": true,
  "enrich_album": true,
  "use_spotify": true,
  "use_musicbrainz": true,
  "use_lastfm": true,
  "manual_overrides": {
    "genre": "Electronic"
  }
}
```

**Response:**
```json
{
  "track_id": "track-uuid",
  "enriched_fields": ["genre", "musicbrainz_id", "release_date"],
  "sources_used": ["musicbrainz", "spotify"],
  "conflicts": [
    {
      "field_name": "genre",
      "current_value": "Electronic",
      "current_source": "musicbrainz",
      "conflicting_values": {
        "spotify": "Dance",
        "lastfm": "Techno"
      }
    }
  ],
  "errors": []
}
```

---

### POST `/api/metadata/resolve-conflict`

Manually resolve metadata conflict.

**Request:**
```json
{
  "track_id": "track-uuid",
  "field_name": "genre",
  "selected_source": "manual",
  "custom_value": "Progressive House"
}
```

**Response:**
```json
{
  "message": "Conflict resolved successfully",
  "entity_type": "track",
  "field_name": "genre",
  "selected_source": "manual"
}
```

---

### POST `/api/metadata/normalize-tags`

Normalize tag list.

**Request:**
```json
["Artist feat. Other", "Band ft. Singer"]
```

**Response:**
```json
["Artist featuring Other", "Band featuring Singer"]
```

---

## Enrichment Sources

### MusicBrainz

- **MBID:** MusicBrainz IDs for tracks/artists/albums
- **Genres:** Authoritative genre data
- **Release Dates:** Accurate release information

---

### Spotify

- **URIs:** Spotify track/artist/album URIs
- **Popularity:** Track popularity scores
- **Audio Features:** Tempo, key, energy, danceability

---

### Last.fm

- **Tags:** User-generated tags
- **Scrobbles:** Listening statistics
- **Similar Artists:** Related artists

---

## Related Documentation

- **[Local Library Enrichment](./local-library-enrichment.md)** - Enrich local files
- **[API Reference: Metadata](../03-api-reference/metadata.md)** - Full endpoint documentation

---

**Last Validated:** 2025-11-25  
**Implementation Status:** ✅ Production-ready
