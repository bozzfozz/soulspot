# SoulSpot Bridge - User Guide

> **Version:** 2.0  
> **Last Updated:** 2025-11-17  
> **Audience:** End Users

---

## 📖 Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Page Guide](#page-guide)
4. [Features](#features)
5. [Keyboard Shortcuts](#keyboard-shortcuts)
6. [Tips & Best Practices](#tips--best-practices)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 Introduction

SoulSpot Bridge is a web-based music management application that syncs Spotify playlists and downloads tracks via the Soulseek network. This guide will help you navigate the interface and make the most of its features.

### Key Features

- **Spotify Integration**: Connect your Spotify account to import playlists
- **Automated Downloads**: Queue tracks for download via Soulseek (slskd)
- **Library Management**: Organize and manage your music library
- **Advanced Search**: Find tracks with powerful filters
- **Real-time Updates**: Live status updates using HTMX

---

## 🚀 Getting Started

### First-Time Setup

1. **Access the Application**
   - Open your web browser and navigate to `http://localhost:8765` (or your configured URL)
   - You should see the onboarding page on first visit

2. **Connect Spotify**
   - Navigate to **Auth** page
   - Click "Connect to Spotify"
   - Authorize the application in the popup window
   - You'll be redirected back to the dashboard

3. **Configure Settings**
   - Go to **Settings** page
   - Configure your Soulseek (slskd) connection
   - Set download preferences
   - Adjust appearance settings (theme, etc.)

---

## 📄 Page Guide

### Dashboard (Home)

**URL:** `/`

The dashboard provides an overview of your music management system.

**Features:**
- **Statistics Cards**: View counts for playlists, tracks, downloads, and queue size
- **Session Status**: Check your Spotify connection status
- **Quick Actions**: Fast access to common tasks

**What You Can Do:**
- View real-time statistics
- Check Spotify connection status
- Navigate to Import Playlist or View Playlists
- Disconnect from Spotify if needed

---

### Search

**URL:** `/search`

Find tracks to download with advanced filtering options.

**Features:**
- **Search Bar**: Type track name, artist, or album
- **Autocomplete**: Get suggestions as you type (300ms debounce)
- **Advanced Filters**:
  - Quality (FLAC, 320kbps, 256kbps+, any)
  - Artist filter
  - Album filter
  - Duration range
- **Search History**: View and reuse recent searches (stored locally)
- **Bulk Download**: Select multiple tracks to download at once

**How to Use:**

1. **Simple Search**
   - Type in the search bar
   - Press Enter or click Search
   - Browse results

2. **Filter Results**
   - Click on filter categories (Quality, Artist, Album, Duration)
   - Select your preferences
   - Results update automatically

3. **Download Tracks**
   - Click "Download" button on individual tracks
   - OR: Select multiple tracks with checkboxes
   - Click "Download Selected" for batch download

4. **Search History**
   - Recent searches appear below the search bar
   - Click any history item to re-run that search
   - Maximum 10 searches stored

**Keyboard Shortcuts:**
- `Ctrl+K` / `Cmd+K`: Focus search bar
- `Escape`: Clear search or close filters

---

### Playlists

**URL:** `/playlists`

Browse and manage your Spotify playlists.

**Features:**
- **Playlist Grid**: View all imported playlists
- **Playlist Cards**: Display name, description, track count, and source
- **View Details**: Click on a playlist to see all tracks
- **Sync Function**: Update playlist with latest tracks from Spotify
- **Empty State**: Helpful message when no playlists exist

**How to Use:**

1. **View Playlists**
   - All imported playlists appear as cards
   - Each card shows:
     - Playlist name
     - Description
     - Track count
     - Source (Spotify)

2. **View Playlist Details**
   - Click "View Details" on any playlist card
   - See complete track list with metadata
   - View download status for each track
   - Export playlist to various formats

3. **Sync Playlist**
   - Click "Sync" button on any playlist card
   - The playlist will update with latest tracks from Spotify
   - Status updates appear via toast notification

4. **Import New Playlist**
   - Click "Import Playlist" button (top right)
   - OR: Click "Import Your First Playlist" in empty state
   - You'll be taken to the import page

---

### Import Playlist

**URL:** `/playlists/import`

Import Spotify playlists into SoulSpot Bridge.

**How to Use:**

1. **Ensure Spotify Connection**
   - You must be logged in to Spotify (check Auth page)

2. **Enter Playlist URL or URI**
   - Copy the Spotify playlist link
   - Paste into the input field
   - Formats accepted:
     - `https://open.spotify.com/playlist/...`
     - `spotify:playlist:...`

3. **Import**
   - Click "Import Playlist"
   - Progress indicator shows import status
   - Success message appears when complete

4. **View Imported Playlist**
   - Navigate to Playlists page
   - Your new playlist appears in the grid

---

### Playlist Detail

**URL:** `/playlists/{id}`

View and manage a specific playlist with full track details.

**Features:**
- **Playlist Stats**: Total tracks, downloaded tracks, source
- **Track Table**: Complete list of all tracks in the playlist
- **Track Information**: Title, artist, album, duration for each track
- **Status Indicators**: Downloaded (green), Missing (yellow), Broken (red)
- **Track Actions**: Download individual tracks
- **Export Options**: Export playlist to M3U, CSV, or JSON
- **Sync Button**: Update playlist with latest tracks from Spotify

**How to Use:**

1. **Navigate to Detail Page**
   - From Playlists page, click "View Details" on any playlist
   - Or click on the playlist name

2. **View Track Information**
   - Browse complete track list in table format
   - Check download status for each track
   - See track metadata (artist, album, duration)

3. **Download Missing Tracks**
   - Click "Download" next to individual tracks
   - Or click "Download Missing" to queue all missing tracks
   - Tracks update to "Downloading" status

4. **Export Playlist**
   - Click "Export" button (top right)
   - Choose export format:
     - **M3U**: For media players (VLC, Winamp, etc.)
     - **CSV**: For spreadsheets (Excel, Google Sheets)
     - **JSON**: For programmatic access
   - File downloads automatically

5. **Sync Playlist**
   - Click "Sync Now" to update with latest Spotify tracks
   - Status appears below the button
   - Useful when playlist has changed on Spotify

---

### Library

**URL:** `/library`

Overview of your music library with quick access to browse options.

**Features:**
- **Library Stats**: View total tracks, artists, albums, downloaded, and broken files
- **Browse Options**: Quick links to view artists, albums, or tracks
- **Scan Library**: Trigger a scan of your music folder
- **Management Actions**: Access broken files, duplicates, and incomplete albums
- **Re-download**: Queue broken files for re-download

**How to Use:**

1. **View Statistics**
   - Check total tracks in your library
   - See how many artists and albums you have
   - Monitor downloaded and broken file counts

2. **Browse Your Library**
   - Click "Browse Artists" to see artist grid
   - Click "Browse Albums" to see album grid
   - Click "Browse Tracks" to see complete track list

3. **Scan Library**
   - Click "Scan Library" to analyze your music folder
   - Status updates appear below
   - Detects new files and checks for issues

4. **Manage Library**
   - **View Broken Files**: See corrupted or incomplete files
   - **View Duplicates**: Find duplicate tracks
   - **Incomplete Albums**: Check albums missing tracks
   - **Re-download Broken**: Queue all broken files for re-download

---

### Library Artists

**URL:** `/library/artists`

Browse all artists in your library in a visual grid layout.

**Features:**
- **Artist Grid**: Visual cards for each artist
- **Artist Avatars**: Color-coded initials for visual identification
- **Track/Album Counts**: See how many albums and tracks per artist
- **Search Filter**: Instantly filter artists by name
- **Breadcrumb Navigation**: Easy navigation back to library

**How to Use:**

1. **Browse Artists**
   - Scroll through the grid of artist cards
   - Each card shows artist name, album count, and track count

2. **Search for Artist**
   - Type in the search box at top right
   - Results filter instantly as you type
   - Searches artist names

3. **Navigate**
   - Use breadcrumb navigation to return to Library
   - Click on artist name (future: will show artist detail page)

---

### Library Albums

**URL:** `/library/albums`

Browse all albums in your library with visual cover art placeholders.

**Features:**
- **Album Grid**: Visual grid of album cards
- **Cover Art Placeholders**: Gradient backgrounds with music icons
- **Album Information**: Title, artist, track count, year
- **Search Filter**: Filter albums by title or artist
- **Breadcrumb Navigation**: Easy navigation back to library

**How to Use:**

1. **Browse Albums**
   - Scroll through the grid of album cards
   - Each card shows album cover, title, artist, and track count

2. **Search for Album**
   - Type in the search box at top right
   - Results filter instantly as you type
   - Searches both album titles and artist names

3. **Navigate**
   - Use breadcrumb navigation to return to Library
   - Click on album (future: will show album detail page)

---

### Library Tracks

**URL:** `/library/tracks`

Browse and manage all tracks in your library with advanced filtering and sorting.

**Features:**
- **Track Table**: Complete list of all library tracks
- **Search Filter**: Search across title, artist, and album
- **Status Filter**: Filter by All, Downloaded, Missing, or Broken
- **Sortable Columns**: Click headers to sort by title, artist, or album
- **Track Actions**: Download missing/broken tracks, view details
- **Status Badges**: Visual indicators for track status
- **Breadcrumb Navigation**: Easy navigation back to library

**How to Use:**

1. **Browse Tracks**
   - View complete track list in table format
   - See title, artist, album, duration, and status for each track

2. **Search for Tracks**
   - Type in the search box at top right
   - Searches title, artist, and album fields
   - Results filter instantly

3. **Filter by Status**
   - Use status dropdown to filter:
     - **All Tracks**: Show everything
     - **Downloaded**: Only tracks with files
     - **Missing**: Tracks without files
     - **Broken**: Corrupted or incomplete files

4. **Sort Tracks**
   - Click column headers (Title, Artist, Album) to sort
   - Click again to reverse sort order
   - Visual indicators show sort direction

5. **Manage Tracks**
   - Click "Download" to download missing/broken tracks
   - Click "Details" to view track metadata
   - Status badges show current state

---

### Downloads

**URL:** `/downloads`

Manage your download queue with priority controls and batch operations.

**Features:**
- **Queue Display**: View all downloads with status indicators
- **Status Filters**: Filter by All, Queued, Downloading, Completed, Failed
- **Batch Operations**: Select multiple downloads for bulk actions
- **Priority Management**: Set download priorities (P0, P1, P2)
- **Progress Tracking**: Real-time progress bars for active downloads
- **Global Controls**: Pause All / Resume All buttons

**Status Types:**
- **Queued** (📋): Waiting to start
- **Downloading** (⬇️): Currently downloading
- **Completed** (✓): Successfully downloaded
- **Failed** (✗): Download failed (with error message)
- **Paused** (⏸️): Manually paused
- **Cancelled** (⊘): Cancelled by user

**Priority Levels:**
- **P0** (High): Downloads first
- **P1** (Medium): Downloads after P0
- **P2** (Low): Downloads after P1 and P2

**How to Use:**

1. **View Queue**
   - All downloads appear in the main area
   - Status badges show current state
   - Progress bars for active downloads

2. **Filter Downloads**
   - Click filter buttons (All, Queued, Downloading, etc.)
   - View only downloads matching that status

3. **Sort Downloads**
   - Use the "Sort" dropdown
   - Options: Date Added, Priority, Status, Progress

4. **Individual Actions**
   - **Pause**: Click ⏸️ to pause an active download
   - **Resume**: Click ▶️ to resume a paused download
   - **Retry**: Click 🔄 to retry a failed download
   - **Cancel**: Click ❌ to cancel a download

5. **Batch Operations**
   - Select multiple downloads using checkboxes
   - Batch operations bar appears at top
   - Available actions:
     - Pause selected
     - Resume selected
     - Cancel selected
     - Set priority for selected
   - Click "Clear" to deselect all

6. **Set Priority**
   - For individual: (Not yet implemented in UI)
   - For batch:
     - Select downloads
     - Choose priority from dropdown (P0, P1, P2)
     - Click "Set Priority"

7. **Global Controls**
   - **Pause All**: Pauses all active downloads
   - **Resume All**: Resumes all paused downloads

**Real-time Updates:**
- Progress bars update automatically
- Status changes reflect immediately
- No need to refresh the page

---

### Settings

**URL:** `/settings`

Configure application preferences and integrations.

**Features:**
- **Tabbed Interface**: Organized by category
- **Form Validation**: Real-time validation feedback
- **Reset to Defaults**: Restore default settings
- **Save Changes**: Persist your configuration

**Settings Tabs:**

#### 1. General
- **Application Name**: Display name for the app
- **Log Level**: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- **Debug Mode**: Enable detailed debug information

#### 2. Integration
- **Spotify Settings**:
  - Client ID
  - Client Secret
  - Redirect URI
  - Scopes
- **Soulseek (slskd) Settings**:
  - API URL
  - API Key (or Username/Password)
  - Connection timeout

#### 3. Downloads
- **Download Path**: Where to save downloaded files
- **File Organization**: Folder structure pattern
- **Quality Preferences**: Preferred audio quality
- **Concurrent Downloads**: Max simultaneous downloads
- **Retry Settings**: Retry attempts and delays

#### 4. Appearance
- **Theme**: Light, Dark, or Auto (system preference)
- **Color Scheme**: Primary color customization
- **Layout Density**: Compact, Normal, or Comfortable
- **Font Size**: Adjust text size

#### 5. Advanced
- **Database Settings**
- **Cache Configuration**
- **API Rate Limiting**
- **Feature Flags**

**How to Use:**

1. **Navigate Tabs**
   - Click tab names to switch categories
   - Current tab is highlighted

2. **Edit Settings**
   - Type in text fields
   - Select from dropdowns
   - Toggle checkboxes
   - Settings are NOT saved automatically

3. **Show/Hide Sensitive Data**
   - Click eye icon to reveal API keys/passwords
   - Click again to hide

4. **Save Changes**
   - Click "Save Changes" button (top right)
   - Success message confirms save
   - Settings take effect immediately

5. **Reset to Defaults**
   - Click "Reset to Defaults" button
   - Confirm in dialog
   - All settings revert to default values
   - You must click "Save Changes" after reset

**Validation:**
- Required fields show error messages if empty
- Invalid formats are highlighted
- Form cannot be submitted with errors

---

### Auth

**URL:** `/auth`

Manage Spotify authentication and authorization.

**Features:**
- **Login to Spotify**: OAuth2 authentication flow
- **Session Status**: View current connection state
- **Disconnect**: Logout from Spotify
- **Token Management**: Automatic token refresh

**How to Use:**

1. **Connect to Spotify**
   - Click "Connect to Spotify" button
   - Popup window opens Spotify authorization
   - Grant permissions
   - Window closes, you're redirected back
   - Success message confirms connection

2. **Check Status**
   - Connection status appears on page
   - Token expiration time shown
   - Scopes granted are listed

3. **Disconnect**
   - Click "Disconnect" button
   - Confirm in dialog
   - Session is cleared
   - You'll need to reconnect to use Spotify features

**Auto-Refresh:**
- Tokens automatically refresh when expired
- No action needed from you
- If refresh fails, you'll be prompted to reconnect

---

### Onboarding

**URL:** `/onboarding`

First-run setup wizard for new users.

**Features:**
- **Step-by-step Guide**: Walk through initial configuration
- **Quick Setup**: Get up and running fast
- **Skip Option**: Bypass onboarding if you prefer

**Steps:**

1. **Welcome**
   - Introduction to SoulSpot Bridge
   - Overview of features

2. **Connect Spotify**
   - Authorize Spotify connection
   - Grant necessary permissions

3. **Configure Soulseek**
   - Enter slskd API credentials
   - Test connection

4. **Choose Preferences**
   - Set download path
   - Select quality preferences
   - Choose theme

5. **Complete**
   - Summary of configuration
   - Button to go to Dashboard

**How to Use:**
- Click "Next" to proceed through steps
- Click "Back" to review previous steps
- Click "Skip" to bypass onboarding (you can configure settings later)
- Progress indicator shows current step

---

## 🎹 Keyboard Shortcuts

| Shortcut | Action | Page |
|----------|--------|------|
| `Ctrl+K` / `Cmd+K` | Focus search bar | Search |
| `Escape` | Close modals / Clear search | All |
| `Tab` | Navigate through elements | All |
| `Enter` | Submit forms / Activate buttons | All |
| `Space` | Toggle checkboxes | All |
| `/` | Focus main search (future) | All |

**Accessibility:**
- All interactive elements are keyboard accessible
- Tab order follows logical flow
- Focus indicators are visible
- Skip links available for screen readers

---

## 💡 Tips & Best Practices

### Search Tips

1. **Use Specific Queries**: Include artist name for better results
2. **Apply Filters**: Quality filters help narrow down results
3. **Check History**: Reuse recent searches for common queries
4. **Autocomplete**: Let it suggest while you type

### Download Management

1. **Set Priorities**: Use P0 for urgent downloads
2. **Batch Operations**: Select multiple items for efficiency
3. **Monitor Progress**: Check Downloads page for status
4. **Retry Failed**: Don't give up on failed downloads, retry might succeed

### Playlist Management

1. **Sync Regularly**: Keep playlists up-to-date with Spotify
2. **Organize**: Use descriptive playlist names
3. **Import Selectively**: Only import playlists you want to download

### Performance

1. **Limit Concurrent Downloads**: Too many can slow things down
2. **Use Filters**: Filter views instead of scrolling through everything
3. **Clear Completed**: Remove completed downloads to reduce clutter

---

## 🔧 Troubleshooting

### Common Issues

#### "Spotify Connection Failed"
- **Cause**: Token expired or invalid credentials
- **Solution**: 
  1. Go to Auth page
  2. Click "Disconnect"
  3. Click "Connect to Spotify" again
  4. Re-authorize the application

#### "Download Stuck in Queue"
- **Cause**: slskd might be offline or overloaded
- **Solution**:
  1. Check slskd status (Settings > Integration)
  2. Test connection
  3. Restart slskd if needed
  4. Retry the download

#### "Search Returns No Results"
- **Cause**: Spotify API might be rate-limited or query is too specific
- **Solution**:
  1. Wait a moment and try again
  2. Simplify your search query
  3. Remove some filters

#### "Settings Won't Save"
- **Cause**: Validation errors or network issue
- **Solution**:
  1. Check for red error messages in form
  2. Fix any validation issues
  3. Check browser console for errors
  4. Try refreshing the page

#### "Page Looks Broken"
- **Cause**: CSS not loaded or cache issue
- **Solution**:
  1. Hard refresh: `Ctrl+Shift+R` / `Cmd+Shift+R`
  2. Clear browser cache
  3. Check browser console for errors

### Getting Help

If you encounter issues not covered here:

1. **Check Logs**: Look at server logs for error details
2. **Browser Console**: Open developer tools (F12) and check Console tab
3. **GitHub Issues**: Report bugs at repository issues page
4. **Documentation**: Review other docs in `/docs` folder

---

## 📚 Additional Resources

- [Keyboard Navigation Guide](keyboard-navigation.md)
- [Advanced Search Guide](advanced-search-guide.md)
- [Design Guidelines](design-guidelines.md)
- [API Documentation](/docs)
- [Frontend Development Roadmap](../frontend-development-roadmap.md)

---

**Happy Music Managing! 🎵**
