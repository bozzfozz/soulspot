# SoulSpot User Guide

**Category:** User Guide  
**Version:** 2.0  
**Last Updated:** 2025-01  
**Audience:** End Users

---

## Quick Start

**SoulSpot** is a web-based music management application that:
- Syncs **Spotify playlists** (import your favorite collections)
- Downloads tracks via **Soulseek** network (high-quality files)
- Manages your local **music library** (organize and browse)
- Provides **real-time updates** (live status using HTMX)

**First-Time Setup:**
1. Access `http://localhost:8765` (or your configured URL)
2. Connect Spotify account (Auth page)
3. Configure Soulseek (Settings → Integration)
4. Import first playlist

---

## Page Guide

### Dashboard (/)
**Purpose:** Overview of your music system

**Features:**
- **Statistics:** Playlists, tracks, downloads, queue size
- **Session Status:** Spotify connection state
- **Quick Actions:** Navigate to Import Playlist, View Playlists

**Usage:**
- View real-time library statistics
- Check Spotify connection (green = connected)
- Disconnect from Spotify if needed

---

### Search (/search)
**Purpose:** Find tracks to download with advanced filtering

**Features:**
- **Search Bar:** Type track/artist/album name (autocomplete after 300ms)
- **Filters:** Quality (FLAC/320kbps/256kbps+), Artist, Album, Duration
- **Search History:** Last 10 searches stored locally (click to re-run)
- **Bulk Download:** Select multiple tracks with checkboxes

**Usage:**
1. **Simple:** Type → Enter → Browse results
2. **Filtered:** Apply quality/artist filters → Results update automatically
3. **Download:** Click "Download" OR select multiple → "Download Selected"

**Keyboard Shortcuts:**
- `Ctrl+K` / `Cmd+K` = Focus search bar
- `Escape` = Clear search or close filters

---

### Playlists (/playlists)
**Purpose:** Browse and manage imported Spotify playlists

**Features:**
- **Grid View:** Cards showing name, description, track count, source
- **Sync Function:** Update playlist with latest Spotify tracks
- **View Details:** See complete track list with download status

**Usage:**
1. **View:** All imported playlists shown as cards
2. **Details:** Click "View Details" → See tracks + metadata + download status
3. **Sync:** Click "Sync" → Fetches latest changes from Spotify
4. **Import New:** Click "Import Playlist" (top right)

---

### Import Playlist (/playlists/import)
**Purpose:** Import Spotify playlists

**Usage:**
1. **Ensure Spotify connected** (check Auth page)
2. **Enter Playlist URL:** `https://open.spotify.com/playlist/...` OR `spotify:playlist:...`
3. **Import:** Progress indicator shows status
4. **View:** Playlist appears in Playlists page

---

### Playlist Detail (/playlists/{id})
**Purpose:** Manage specific playlist with full track details

**Features:**
- **Stats:** Total tracks, downloaded tracks, source
- **Track Table:** Title, artist, album, duration, status
- **Status Indicators:** Downloaded (green), Missing (yellow), Broken (red)
- **Export:** M3U (media players), CSV (spreadsheets), JSON (programmatic)

**Usage:**
1. **View Tracks:** Browse complete list with metadata
2. **Download:** Click "Download" next to tracks OR "Download Missing" for all
3. **Export:** Choose format → File downloads automatically
4. **Sync:** Click "Sync Now" to update from Spotify

---

### Library (/library)
**Purpose:** Overview of your music library

**Features:**
- **Stats:** Total tracks, artists, albums, downloaded, broken files
- **Browse:** Quick links to Artists, Albums, Tracks
- **Scan:** Trigger music folder analysis
- **Management:** Access broken files, duplicates, incomplete albums

**Usage:**
1. **View Statistics:** Check library size and health
2. **Browse:** "Browse Artists" → Grid view, "Browse Albums" → Album covers, "Browse Tracks" → Complete list
3. **Scan:** Click "Scan Library" → Detects new files + issues
4. **Manage:** "View Broken Files" → Corrupted/incomplete, "Re-download Broken" → Queue all for re-download

---

### Library Artists (/library/artists)
**Purpose:** Browse artists in grid layout

**Features:**
- **Visual Cards:** Color-coded initials for each artist
- **Counts:** Albums + tracks per artist
- **Search Filter:** Instant filter by artist name

**Usage:**
- **Browse:** Scroll grid of artist cards
- **Search:** Type at top right → Results filter instantly

---

### Library Albums (/library/albums)
**Purpose:** Browse albums with cover art

**Features:**
- **Album Grid:** Gradient backgrounds with music icons
- **Info:** Title, artist, track count, year
- **Search Filter:** Filter by album title or artist name

**Usage:**
- **Browse:** Scroll grid of album cards
- **Search:** Type at top right → Results filter instantly

---

### Library Tracks (/library/tracks)
**Purpose:** Browse and manage all library tracks

**Features:**
- **Track Table:** Title, artist, album, duration, status
- **Search:** Across title/artist/album
- **Status Filter:** All, Downloaded, Missing, Broken
- **Sortable:** Click headers (Title, Artist, Album) to sort

**Usage:**
1. **Browse:** View complete track list
2. **Search:** Type at top right → Instant filter
3. **Filter:** Status dropdown → Show only Downloaded/Missing/Broken
4. **Sort:** Click column headers → Sort ascending/descending
5. **Download:** Click "Download" for missing/broken tracks

---

### Downloads (/downloads)
**Purpose:** Manage download queue with priority controls

**Features:**
- **Queue Display:** All downloads with status indicators
- **Status Filters:** All, Queued, Downloading, Completed, Failed
- **Batch Operations:** Select multiple → Pause/Resume/Cancel/Set Priority
- **Priority Levels:** P0 (High), P1 (Medium), P2 (Low)
- **Global Controls:** Pause All / Resume All

**Status Types:**
- 📋 **Queued:** Waiting to start
- ⬇️ **Downloading:** Currently active
- ✓ **Completed:** Successfully downloaded
- ✗ **Failed:** Error (with message)
- ⏸️ **Paused:** Manually paused
- ⊘ **Cancelled:** User cancelled

**Usage:**
1. **View Queue:** All downloads with progress bars
2. **Filter:** Click status buttons (All, Queued, etc.)
3. **Sort:** Use dropdown (Date, Priority, Status, Progress)
4. **Individual Actions:** ⏸️ Pause, ▶️ Resume, 🔄 Retry, ❌ Cancel
5. **Batch Operations:** Select multiple → Choose action → Execute
6. **Global:** "Pause All" / "Resume All" for bulk management

**Real-time Updates:** Progress bars + status update automatically (no refresh needed)

---

### Settings (/settings)
**Purpose:** Configure application preferences

**Tabs:**
1. **General:** App name, log level, debug mode
2. **Integration:** Spotify (Client ID/Secret/Redirect), Soulseek (slskd URL/API Key)
3. **Downloads:** Path, organization, quality preferences, concurrent downloads, retries
4. **Appearance:** Theme (Light/Dark/Auto), color scheme, layout density, font size
5. **Advanced:** Database, cache, rate limiting, feature flags

**Usage:**
1. **Navigate Tabs:** Click tab names
2. **Edit Settings:** Type in fields, select from dropdowns, toggle checkboxes
3. **Save:** Click "Save Changes" (top right) → Settings take effect immediately
4. **Reset:** "Reset to Defaults" → Confirm → Must click "Save Changes" after

**Important:** Settings NOT saved automatically!

---

### Auth (/auth)
**Purpose:** Manage Spotify authentication

**Features:**
- **Login:** OAuth2 authorization flow
- **Session Status:** Connection state, token expiration, scopes granted
- **Disconnect:** Logout from Spotify

**Usage:**
1. **Connect:** Click "Connect to Spotify" → Grant permissions in popup → Success message
2. **Check Status:** View connection state, token expiration, granted scopes
3. **Disconnect:** Click "Disconnect" → Confirm → Session cleared (must reconnect for Spotify features)

**Auto-Refresh:** Tokens refresh automatically when expired (no action needed)

---

### Onboarding (/onboarding)
**Purpose:** First-run setup wizard

**Steps:**
1. **Welcome:** Introduction to SoulSpot
2. **Connect Spotify:** Authorize connection
3. **Configure Soulseek:** Enter slskd credentials
4. **Preferences:** Download path, quality, theme
5. **Complete:** Summary + navigate to Dashboard

**Usage:**
- **Next:** Proceed through steps
- **Back:** Review previous steps
- **Skip:** Bypass onboarding (configure in Settings later)

---

## Keyboard Shortcuts

| Shortcut | Action | Page |
|----------|--------|------|
| `Ctrl+K` / `Cmd+K` | Focus search bar | Search |
| `Escape` | Close modals / Clear search | All |
| `Tab` | Navigate elements | All |
| `Enter` | Submit forms / Activate buttons | All |
| `Space` | Toggle checkboxes | All |

**Accessibility:** All interactive elements keyboard accessible, logical tab order, visible focus indicators

---

## Tips & Best Practices

### Search
- **Specific Queries:** Include artist name for better results
- **Apply Filters:** Quality filters narrow down results
- **Autocomplete:** Let it suggest while typing

### Downloads
- **Set Priorities:** P0 for urgent downloads
- **Batch Operations:** Select multiple for efficiency
- **Monitor Progress:** Check Downloads page for status

### Playlists
- **Sync Regularly:** Keep up-to-date with Spotify
- **Organize:** Use descriptive names
- **Import Selectively:** Only import playlists you want

### Performance
- **Limit Concurrent Downloads:** Too many slows things down
- **Use Filters:** Instead of scrolling through everything
- **Clear Completed:** Remove completed downloads to reduce clutter

---

## Troubleshooting

### "Spotify Connection Failed"
**Cause:** Token expired or invalid credentials  
**Solution:** Auth page → Disconnect → Connect to Spotify → Re-authorize

### "Download Stuck in Queue"
**Cause:** slskd might be offline/overloaded  
**Solution:** Settings → Integration → Test connection → Restart slskd → Retry download

### "Search Returns No Results"
**Cause:** Spotify API rate-limited or query too specific  
**Solution:** Wait a moment → Simplify query → Remove some filters

### "Settings Won't Save"
**Cause:** Validation errors or network issue  
**Solution:** Check red error messages → Fix validation issues → Check browser console → Refresh page

### "Page Looks Broken"
**Cause:** CSS not loaded or cache issue  
**Solution:** Hard refresh `Ctrl+Shift+R` / `Cmd+Shift+R` → Clear browser cache → Check console (F12)

---

## Related Documentation

- [Setup Guide](./setup-guide.md) - Installation and configuration
- [Troubleshooting Guide](./troubleshooting-guide.md) - Comprehensive issue resolution
- [Spotify Auth Troubleshooting](./spotify-auth-troubleshooting.md) - OAuth specific issues
- [API Documentation](/api/endpoints/) - REST API reference

---

**Happy Music Managing! 🎵**
