# Local Library Enrichment

**Category:** Features  
**Status:** ✅ Active  
**Last Updated:** 2025-11-29  
**Related Docs:** [Metadata Enrichment](./metadata-enrichment.md) | [Spotify Sync](./spotify-sync.md)

---

## Overview

Local Library Enrichment enriches local music files with Spotify metadata. Unlike Spotify Sync (which imports followed artists/playlists), this feature searches Spotify for matches for **all** local files—regardless of whether you follow the artist on Spotify.

---

## Why Useful?

1. **Local Files Without Spotify Link:** MP3s on disk without Spotify URIs
2. **Missing Artwork:** Local files often lack album covers
3. **Missing Genres:** ID3 tags rarely contain genre info
4. **Consistent Library:** All entries have same metadata fields

---

## Features

### Automatic Enrichment

- **After Every Library Scan:** If enabled, auto-starts enrichment job
- **Batch Processing:** Processes 50 items per run (configurable)
- **Rate Limiting:** 50ms pause between Spotify API calls
- **Error Tolerance:** Single errors don't stop entire process

---

### Matching Algorithm

#### For Artists

- **Name Normalization:** Removes typical prefixes (DJ, The, MC, Dr, Lil) and suffixes (Band, Orchestra)
  - Example: "DJ Paul Elstak" → "paul elstak" = 100% match with "Paul Elstak"
- **Fuzzy Name Matching** (85% weight, configurable)
- **Spotify Popularity** (15% weight, configurable)
- Filters "Various Artists" automatically
- **Followed Artists Hint:** If artist in Followed Artists, direct 100% match

---

#### For Albums

- **Name Normalization:** Like artists, removes DJ/The/MC from artist name
  - Example: "DJ Paul Elstak - Party Animals" = "Paul Elstak - Party Animals"
- Album title matching (45% weight)
- Artist name matching with normalization (45% weight)
- Year bonus (10% weight) - Exact year +10%, ±1 year +5%
- Searches via Spotify Track Search API (limit configurable, default 20)
- **Followed Albums Hint:** If album from followed artist exists, direct 100% match

---

#### For Various Artists / Compilations

- **Automatic Detection:** "Various Artists", "VA", "V.A.", "Verschiedene Künstler", etc.
- **Title-Only Search:** Searches only album title (ignores artist)
  - Example: `album:"Bravo Hits 100"` instead of `artist:Various Artists album:Bravo Hits`
- **Adjusted Scoring:**
  - Album title matching (80% weight) - Main identifier!
  - Year bonus (20% weight) - Distinguishes e.g. "Bravo Hits 99" from "Bravo Hits 100"
  - Artist name **completely ignored**
- **Supported Patterns:** Various Artists, VA, V.A., V/A, Diverse, Verschiedene, Soundtrack, OST, Sampler, Compilation

---

### Name Normalization

Following prefixes automatically ignored when matching:
- **DJ:** "DJ Paul Elstak" = "Paul Elstak"
- **The:** "The Prodigy" = "Prodigy"
- **MC:** "MC Hammer" = "Hammer"
- **Dr/Dr.:** "Dr. Dre" = "Dre"
- **Lil/Lil':** "Lil Wayne" = "Wayne"
- **Others:** Big, Young, Old, King, Queen, Sir, Lady, Miss, Mr, Mrs, Ms

Suffixes like "Band", "Orchestra", "Trio" also removed.

---

### Confidence Scoring

- **≥75%:** Automatic match application (configurable)
- **50-74%:** Candidate saved for manual review
- **<50%:** No match found

---

### Deezer Fallback

If Spotify finds no match, automatically uses Deezer as fallback:

**Fallback Chain:**
```
1. Spotify (primary source)
   ↓ no match or below confidence threshold
2. Deezer (fallback, no auth needed!)
   ↓ no match
3. No enrichment possible
```

**Deezer Fallback Benefits:**
- **No OAuth Required** - Works immediately without setup
- **Good Catalog** - Some albums Spotify doesn't have
- **High-Resolution Artwork** - 1000x1000px covers

**When Deezer Used?**
- Spotify finds no albums (no tracks with this artist+album)
- Spotify finds candidates, but none reach confidence threshold

**Statistics Tracking:**
Enrichment stats show separately how many matches via Deezer:
```json
{
  "albums_enriched": 50,
  "deezer_albums_enriched": 8,
  "deezer_artists_enriched": 0,
  ...
}
```

See: [Deezer Integration](./deezer-integration.md)

---

### Dual Album Type System (Lidarr-Compatible)

System uses two type dimensions like Lidarr/MusicBrainz:

**Primary Type** (exclusive):
- `album` - Standard album
- `ep` - Extended Play
- `single` - Single
- `broadcast` - Radio recording
- `other` - Other

**Secondary Types** (combinable):
- `compilation` - Compilation/Various Artists
- `soundtrack` - Soundtrack
- `live` - Live recording
- `remix` - Remix album
- `dj-mix` - DJ mix
- `mixtape` - Mixtape
- `demo` - Demo
- `spokenword` - Audiobook/Spoken Word

**Example:** Live album of a compilation has:
- `primary_type = "album"`
- `secondary_types = ["live", "compilation"]`

---

### Various Artists Detection (Lidarr-Style)

System automatically recognizes compilations via multiple heuristics (priority order):

#### 1. Explicit Compilation Flags (highest priority)
- **TCMP** Tag (ID3 - iTunes Compilation)
- **cpil** Tag (MP4)
- **COMPILATION** Tag (Vorbis/FLAC)

#### 2. Album Artist Pattern Matching
Recognized patterns (case-insensitive):
- "Various Artists", "VA", "V.A.", "V/A"
- "Diverse", "Verschiedene", "Verschiedene Künstler" (German)
- "Varios Artistas" (Spanish)

---

## Usage (Web UI)

### Enable Auto-Enrichment

1. Navigate to **Settings** → **Library**
2. Toggle **Auto-Enrich Local Library** → **Enabled**
3. Every library scan triggers automatic enrichment

---

### Manual Enrichment

1. Navigate to **Library** → **Enrichment**
2. Click **Enrich All**
3. Monitor progress bar

---

## Configuration

```bash
# Auto-enrichment after scan
AUTO_ENRICH_LOCAL_LIBRARY=true

# Batch size
ENRICHMENT_BATCH_SIZE=50

# Confidence threshold
ENRICHMENT_CONFIDENCE_THRESHOLD=0.75

# Rate limiting
ENRICHMENT_API_DELAY_MS=50
```

---

## Related Documentation

- **[Metadata Enrichment](./metadata-enrichment.md)** - Multi-source enrichment
- **[Spotify Sync](./spotify-sync.md)** - Followed artists sync
- **[Deezer Integration](./deezer-integration.md)** - Fallback provider

---

**Last Validated:** 2025-11-29  
**Implementation Status:** ✅ Production-ready
