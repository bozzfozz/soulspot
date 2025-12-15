# Browse API

> **Version:** 2.0  
> **Last Updated:** 2025-12-15

---

## Overview

The Browse API provides endpoints for discovering new music from **your library artists only**. It aggregates new releases from both Deezer and Spotify, filtering them to show only albums from artists you already follow or have in your library.

---

## Architecture

```
Route (/browse/new-releases)
    ↓
Load Library Artists (ArtistModel)
    ↓
DeezerPlugin + SpotifyPlugin (dependency injection)
    ↓
Filter by artist_name matching
    ↓
Deduplicate + Sort by date
```

---

## Key Features

- **Library-filtered** - Only shows releases from artists in your library
- **Multi-service aggregation** - Combines Deezer + Spotify sources
- **Deduplication** - Same album from multiple services shown once
- **Source badges** - Shows which service provided each release
- **No spam** - No random global releases, only your followed artists
- **Date filtering** - Configurable lookback period (7-365 days)

---

## Endpoints

### GET `/browse/new-releases`

Fetch new album releases **from your library artists only**. Aggregates releases from Deezer + Spotify, filtering to show only albums from artists in your library.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 90 | Days to look back (7-365) |
| `include_compilations` | boolean | true | Include compilation albums |
| `include_singles` | boolean | true | Include singles/EPs |

#### Response

Returns HTML page with album grid. Each album includes:
- Album cover artwork
- Title and artist name
- Release date (hidden if unknown)
- Track count
- Album type (album, single, EP, compilation)
- Source badge (deezer/spotify)
- External link

#### Example Request

```http
GET /browse/new-releases?days=90&include_singles=true&include_compilations=false
```

#### Data Sources

**Step 1: Load Library Artists**
- Queries `soulspot_artists` table for all artist names
- Creates normalized set for case-insensitive matching

**Step 2: Fetch from Deezer**
- Uses `DeezerClient.get_browse_new_releases()` (editorial + charts)
- **Filters** to only show albums where `artist_name` matches library artists
- Enriches missing `release_date` via detail API

**Step 3: Fetch from Spotify**
- Queries `soulspot_albums` table with `source='spotify'`
- Joins with `soulspot_artists` where `spotify_uri IS NOT NULL`
- Already library-filtered by design

**Step 4: Deduplicate & Sort**
- Combines both sources
- Deduplicates by normalized `artist_name::album_title` key
- Sorts by `release_date` descending (newest first)

---

## Album Data Structure

Each album in the response contains:

```json
{
  "id": "123456789",
  "name": "Album Title",
  "artist_name": "Artist Name",
  "artist_id": "987654",
  "artwork_url": "https://...",
  "release_date": "2025-01-15",
  "album_type": "album",
  "total_tracks": 12,
  "external_url": "https://www.deezer.com/album/123456789",
  "source": "deezer"
}
```

**Notes:**
- `release_date` = `"1900-01-01"` is hidden in UI (fallback for missing dates)
- `source` = `"deezer"` or `"spotify"` (shown as badge in UI)
- `id` is service-specific (Deezer ID or Spotify ID)

---

## Record Types

| Type | Description |
|------|-------------|
| `album` | Full-length album |
| `single` | Single track release |
| `ep` | Extended play (typically 4-6 tracks) |
| `compile` | Compilation/collection |

---

## Error Handling

If service fetch fails, the page shows partial results from working services:

```html
<div class="alert alert-warning">
    <i class="bi bi-exclamation-triangle"></i> Some sources failed: [error message]
</div>
```

Graceful degradation:
- ✅ Deezer fails → Show Spotify releases only
- ✅ Spotify fails → Show Deezer releases only
- ✅ Both fail → Show empty state with error message
- ✅ No library artists → Shows empty (intentional)

---

## Rate Limits

**Deezer API:**
- **50 requests per 5 seconds** per IP
- No authentication required for browse

**Spotify:**
- Uses local database (no API calls during page load)
- Already synced via background worker

---

## Implementation Notes

**Why library filtering?**
- Prevents spam from random global releases
- Users only see relevant new music
- Respects user's music taste (curated library)

**Why 200 limit for Deezer?**
- Fetches more releases to compensate for filtering
- Most will be filtered out (not in library)
- Ensures enough results after filtering

**Name matching:**
- Case-insensitive and trimmed: `"Artist Name"` → `"artist name"`
- Works across all services (Spotify, Deezer, local)
- Simple but effective for 95% of cases

---

## Future Enhancements

Planned additions:
1. ~~**Spotify New Releases**~~ ✅ Already implemented!
2. **Genre filtering** - Browse by specific genre
3. **Regional charts** - Country-specific new releases
4. **Fuzzy name matching** - Better artist matching across services
5. **Download queue integration** - One-click add to download queue

---

## Related Endpoints

- `GET /spotify/discover` - Similar artists (requires Spotify auth)
- `GET /search` - Search across all sources
- `GET /downloads` - Download queue management
