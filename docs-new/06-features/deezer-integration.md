# Deezer Integration

**Category:** Features  
**Status:** ⚠️ PLANNED (Design Phase - Not Implemented)  
**Last Updated:** 2025-12-05

---

## Overview

Deezer integration is **planned** for enriching local library entries with metadata and artwork from Deezer. **Deezer is the ideal fallback** when Spotify has no match, especially for:

- **Various Artists / Compilations** - Album search without artist name
- **Obscure Releases** - Different catalog than Spotify
- **Artwork Enrichment** - High-resolution covers (1000x1000px)

---

## Why Deezer?

| Feature | Deezer | Spotify | Tidal |
|---------|--------|---------|-------|
| **Auth for Metadata** | ❌ No! | ✅ Yes | ✅ Yes |
| **Artwork Size** | 1000x1000 | 640x640 | 1280x1280 |
| **ISRC Available** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Rate Limit** | 50/5s | 180/min | Variable |
| **ToS for Enrichment** | ✅ Allowed | ⚠️ Restricted | ⚠️ Restricted |

**Key Advantage:** Deezer's public API works **without authentication** for search and metadata.

---

## Planned API Client

### Basic Usage (Planned)

```python
from soulspot.infrastructure.integrations import DeezerClient

# Client creation (no auth!)
client = DeezerClient()

# Album search
albums = await client.search_albums("Bravo Hits 100")
for album in albums:
    print(f"{album.title} - {album.artist_name}")
    print(f"Artwork: {album.cover_xl}")  # 1000x1000!

# Artist search
artists = await client.search_artists("Armin van Buuren")
artist = artists[0]
print(f"Image: {artist.picture_xl}")

# Track by ISRC (exact matching!)
track = await client.get_track_by_isrc("USQY51613007")
if track:
    print(f"{track.title} by {track.artist_name}")

await client.close()
```

### Enrichment Convenience Methods (Planned)

```python
# Find album artwork (perfect for Various Artists!)
artwork_url = await client.find_album_artwork(
    album_title="Bravo Hits 100",
    artist_name=None  # Leave empty for Various Artists
)

# Find artist image
image_url = await client.find_artist_image("Paul Elstak")
```

---

## Data Models (Planned)

### DeezerAlbum

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Deezer album ID |
| `title` | str | Album title |
| `artist_name` | str | Artist name |
| `artist_id` | int | Deezer artist ID |
| `cover_xl` | str | 1000x1000 artwork URL |
| `cover_big` | str | 500x500 artwork URL |
| `cover_medium` | str | 250x250 artwork URL |
| `release_date` | str | Release date (YYYY-MM-DD) |
| `nb_tracks` | int | Track count |
| `record_type` | str | album, ep, single, compile |
| `upc` | str | Universal Product Code |

### DeezerArtist

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Deezer artist ID |
| `name` | str | Artist name |
| `picture_xl` | str | 1000x1000 image URL |
| `nb_album` | int | Album count |
| `nb_fan` | int | Fan count |

### DeezerTrack

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Deezer track ID |
| `title` | str | Track title |
| `artist_name` | str | Artist name |
| `album_title` | str | Album title |
| `isrc` | str | ISRC code (for matching!) |
| `duration` | int | Duration in seconds |
| `preview` | str | 30s preview URL |

---

## Rate Limiting

Deezer allows **50 requests per 5 seconds** per IP address.

Planned client features:
- 100ms pause between requests
- Lock for concurrent requests
- Automatic retry on rate limit

---

## Library Enrichment Integration (Planned)

### Fallback Chain

```
1. Spotify (if connected and match found)
   ↓ no match
2. Deezer (always available, no auth)
   ↓ no match
3. MusicBrainz/CoverArtArchive
   ↓ no match
4. Local cover.jpg
```

### Various Artists Enrichment Example

```python
# In local_library_enrichment_service.py (planned)

async def _enrich_compilation_album(self, album: Album) -> str | None:
    """Enrich Various Artists compilation with Deezer artwork."""
    
    # Spotify often doesn't work for Various Artists
    # → Go directly to Deezer
    artwork_url = await self._deezer_client.find_album_artwork(
        album_title=album.title,
        artist_name=None  # Ignore for compilations
    )
    
    return artwork_url
```

---

## Configuration (Planned)

No configuration needed! Deezer's public API is free and requires no credentials.

Optional `.env` setting:
```env
# Rate limit delay (optional, default 0.1s)
DEEZER_RATE_LIMIT_MS=100
```

---

## Known Limitations

1. **No Full-Length Streaming** - Only 30s previews
2. **No User Playlists** - Requires OAuth (not planned)
3. **Catalog Differences** - Not all Spotify albums are on Deezer
4. **No German Localization** - Search results are international

---

## Artwork Source Comparison

| Source | Size | Quality | Availability | Auth Required |
|--------|------|---------|--------------|---------------|
| **Deezer** | 1000x1000 | High | Good | ❌ No |
| **Spotify** | 640x640 | Medium | Excellent | ✅ Yes |
| **Tidal** | 1280x1280 | Best | Good | ✅ Yes |
| **MusicBrainz** | Variable | Variable | Good | ❌ No |

---

## Implementation Status

**Current Status:** Design/Specification Phase

**Planned Components:**
- [ ] `DeezerClient` class (HTTP API wrapper)
- [ ] Data models (DeezerAlbum, DeezerArtist, DeezerTrack)
- [ ] Rate limiting implementation
- [ ] Enrichment service integration
- [ ] Fallback chain logic

**Timeline:** TBD

---

## Related Documentation

- **[Plugin System](../04-architecture/plugin-system.md)** - Multi-provider architecture
- **[Data Standards](../04-architecture/data-standards.md)** - DTO definitions
- **[Metadata Enrichment](./metadata-enrichment.md)** - Enrichment strategies

---

**Last Updated:** 2025-12-05  
**Implementation Status:** ⚠️ PLANNED (Not Started)
