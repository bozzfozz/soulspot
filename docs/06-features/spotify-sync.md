# Spotify Sync

**Category:** Features  
**Last Updated:** 2025-11-30  
**Related Docs:** [Authentication](./authentication.md) | [API Reference: Spotify](../03-api-reference/spotify.md)

---

## Overview

Spotify Auto-Sync automatically synchronizes data from your Spotify account to SoulSpot's local database. After sync, SoulSpot works **independently** with local data (no ongoing Spotify API dependency for features).

**What Gets Synced:**

| Type | Description | Cooldown | Storage |
|------|-------------|----------|---------|
| **Followed Artists** | Artists you follow on Spotify | 5 min | `spotify_artists` table + WebP images |
| **Playlists** | Your Spotify playlists (created + followed) | 10 min | `spotify_playlists` table + covers |
| **Liked Songs** | "Liked Songs" special playlist | 10 min | Stored as playlist with `is_liked_songs=true` |
| **Saved Albums** | Albums saved in library | 10 min | `spotify_albums` table + covers |
| **Artist Albums** | All albums from followed artists | 2 min | `spotify_albums` table (gradual sync) |

---

## Architecture

```
Settings UI (settings.html)
    ├─ Master Toggle (auto_sync_enabled)
    ├─ Individual Toggles (artists, playlists, liked_songs, albums)
    ├─ Interval Settings (sync cooldowns)
    └─ Disk Usage Stats (image storage)
         ↓
Settings API (/api/settings/spotify-sync)
         ↓
SpotifySyncService + SpotifyImageService
         ↓
SpotifyClient (Spotify Web API) + SpotifyBrowseRepository
         ↓
Database (spotify_*) + File System (artwork/spotify/)
```

**Source:** `src/soulspot/application/services/spotify_sync_service.py`

---

## Sync Types

### Followed Artists

**Synced Fields:**

| Field | Description |
|-------|-------------|
| `spotify_id` | Unique Spotify artist ID |
| `name` | Artist name |
| `genres` | Array of genre strings |
| `popularity` | Spotify popularity (0-100) |
| `image_url` | URL to Spotify image |
| `image_path` | Local path to WebP (300x300px) |
| `follower_count` | Followers on Spotify |

**Endpoint:** `GET /v1/me/following?type=artist` (Spotify API)

---

### Playlists

**Synced Fields:**

| Field | Description |
|-------|-------------|
| `spotify_playlist_id` | Unique Spotify playlist ID |
| `name` | Playlist name |
| `description` | Playlist description |
| `owner_id` | Spotify ID of creator |
| `track_count` | Number of tracks |
| `cover_url` | URL to playlist cover |
| `cover_path` | Local path to WebP (300x300px) |
| `is_public` | Public or private |
| `is_collaborative` | Collaborative playlist flag |

**Endpoint:** `GET /v1/me/playlists` (Spotify API)

---

### Liked Songs

**Special Playlist:**
- Synced as playlist with `is_liked_songs=true`
- Name: "Liked Songs"
- Owner: Your Spotify user ID
- Tracks: All your liked songs

**Endpoint:** `GET /v1/me/tracks` (Spotify API)

---

### Saved Albums

**Synced Fields:**
- `is_saved=true` flag in `spotify_albums` table
- `saved_at` timestamp

**Endpoint:** `GET /v1/me/albums` (Spotify API)

---

### Artist Albums (Background Sync) ⭐ NEW

**Gradual Sync Strategy:**
- Syncs **all albums** from **all followed artists**
- Runs every **2 minutes**, syncs **5 artists per cycle**
- Prevents rate limit exhaustion (500+ artists would exceed limits)

**How It Works:**

```
1. Query artists WHERE albums_synced_at IS NULL OR > 24h old
2. Take 5 artists (ordered by last sync)
3. For each artist:
   - Fetch albums via Spotify API
   - Upsert into spotify_albums table
   - Update albums_synced_at timestamp
   - Sleep 0.5s (rate limit protection)
```

**Synced Album Fields:**

| Field | Description |
|-------|-------------|
| `spotify_id` | Unique Spotify album ID |
| `artist_id` | Link to artist |
| `name` | Album name |
| `album_type` | album, single, compilation |
| `release_date` | Release date |
| `total_tracks` | Track count |
| `image_url` | Album cover URL |

**Use Cases:**
- **Watchlists:** Check new releases locally (no API calls)
- **Discography Check:** Compare local data vs API

**Source:** `src/soulspot/application/services/spotify_sync_service.py` (sync_artist_albums_gradual)

---

## Image Storage

### Format & Sizes

| Type | Format | Size | Path |
|------|--------|------|------|
| Artists | WebP | 300x300px | `artwork/spotify/artists/{spotify_id}.webp` |
| Albums | WebP | 500x500px | `artwork/spotify/albums/{spotify_id}.webp` |
| Playlists | WebP | 300x300px | `artwork/spotify/playlists/{spotify_id}.webp` |

**Why WebP?**
- ✅ ~30% smaller than JPEG (same quality)
- ✅ Transparency support
- ✅ Broad browser support

**Source:** `src/soulspot/application/services/spotify_image_service.py`

---

## Settings

### Runtime Settings (Database)

All settings stored in `app_settings` table, editable without restart:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `auto_sync_enabled` | bool | `true` | Master toggle for auto-sync |
| `auto_sync_artists` | bool | `true` | Sync followed artists |
| `auto_sync_playlists` | bool | `true` | Sync playlists |
| `auto_sync_liked_songs` | bool | `true` | Sync liked songs |
| `auto_sync_saved_albums` | bool | `true` | Sync saved albums |
| `artists_sync_interval_minutes` | int | `5` | Artist sync cooldown |
| `playlists_sync_interval_minutes` | int | `10` | Playlist sync cooldown |
| `download_images` | bool | `true` | Store images locally |
| `remove_unfollowed_artists` | bool | `true` | Remove unfollowed artists |
| `remove_unfollowed_playlists` | bool | `false` | Remove deleted playlists |
| `auto_sync_artist_albums` | bool | `true` | Gradual artist album sync |
| `artist_albums_sync_interval_minutes` | int | `2` | Album sync interval |
| `artist_albums_per_cycle` | int | `5` | Artists per sync cycle |

**Setting Keys:**
```
spotify.auto_sync_enabled
spotify.auto_sync_artists
spotify.auto_sync_playlists
spotify.auto_sync_liked_songs
spotify.auto_sync_saved_albums
spotify.artists_sync_interval_minutes
spotify.playlists_sync_interval_minutes
spotify.download_images
spotify.remove_unfollowed_artists
spotify.remove_unfollowed_playlists
spotify.auto_sync_artist_albums
spotify.artist_albums_sync_interval_minutes
spotify.artist_albums_per_cycle
```

---

## API Endpoints

### GET `/api/settings/spotify-sync`

**Response:**
```json
{
  "settings": {
    "auto_sync_enabled": true,
    "auto_sync_artists": true,
    "auto_sync_playlists": true,
    "auto_sync_liked_songs": true,
    "auto_sync_saved_albums": true,
    "artists_sync_interval_minutes": 5,
    "playlists_sync_interval_minutes": 10,
    "download_images": true,
    "remove_unfollowed_artists": true,
    "remove_unfollowed_playlists": false,
    "auto_sync_artist_albums": true,
    "artist_albums_sync_interval_minutes": 2,
    "artist_albums_per_cycle": 5
  },
  "image_stats": {
    "artists_bytes": 1258291,
    "albums_bytes": 8847200,
    "playlists_bytes": 314572,
    "total_bytes": 10420063,
    "artists_count": 42,
    "albums_count": 156,
    "playlists_count": 12
  }
}
```

### PUT `/api/settings/spotify-sync`

Update sync settings (hot-reload, no restart).

### GET `/api/settings/db-stats`

Database statistics for synced entities.

**Response:**
```json
{
  "artists": 42,
  "albums": 156,
  "tracks": 1234,
  "playlists": 12
}
```

---

## Background Worker

**SpotifySyncWorker** runs automatically:
- **Interval:** Respects per-type cooldown settings
- **Checks:** Token availability before sync
- **Error Handling:** Circuit breaker for API failures
- **Logging:** Progress and errors

**Source:** `src/soulspot/application/services/workers/spotify_sync_worker.py`

---

## Troubleshooting

### Sync Not Running

**Cause:** `auto_sync_enabled=false` or no valid token

**Solution:**
1. Check Settings → Spotify → Enable Auto-Sync
2. Ensure authenticated (green "Connected" badge)
3. Check worker status: `GET /api/workers`

### Images Not Downloading

**Cause:** `download_images=false`

**Solution:** Enable in Settings → Spotify → Download Images

### High Disk Usage

**Check:** Settings → Spotify → Disk Usage section shows breakdown

**Solution:**
- Disable image download for specific types
- Manually delete `artwork/spotify/` folder

---

## Related Documentation

- **[Authentication](./authentication.md)** - OAuth setup
- **[API Reference: Spotify](../03-api-reference/spotify.md)** - Endpoint details
- **[Worker Patterns](../04-architecture/worker-patterns.md)** - Background worker architecture

---

**Last Validated:** 2025-11-30  
**Implementation Status:** ✅ Production-ready
