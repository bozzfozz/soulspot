# Library + Followed Artists View

**Feature:** Unified library view showing local + remote tracked artists with availability indicators

**Status:** Design Approved (2025-12-10)  
**Related ADR:** [Plugin System ADR - Appendix E](../architecture/plugin-system-adr.md#appendix-e-hybrid-library-concept)

---

## Overview

The Library view is a **hybrid** combining:
- **Local Artists** (100% downloaded)
- **Followed Artists** from Spotify/Tidal/Deezer (partially or not downloaded)
- **Availability Indicators** (Lidarr-style progress bars)

**Key Principle:** User sees everything they care about, regardless of local availability.

---

## Visual Design

### Artist Card (Grid View)

```
┌──────────────────────────────────┐
│ [🎵 Spotify]      Pink Floyd     │  ← Service badge (top-left)
│                                  │
│  [Album Cover Grid 2x2]         │  ← 4 album covers
│                                  │
│  ████████████░░░░ 80%            │  ← Progress bar (green/red)
│  16/20 Albums • 180/225 Tracks  │  ← Stats
│                                  │
│  [⬇ Download Missing]            │  ← Quick action (if <100%)
└──────────────────────────────────┘

Color States:
- Border Green:  100% complete ✅
- Border Yellow: 50-99% partial ⚠️
- Border Red:    0-49% mostly missing ❌
```

### Artist Card (List View)

```
[🎵] Pink Floyd           ████████░░ 80%    16/20 Albums    [⬇ Download Missing]
[🎵] The Beatles          ██████████ 100%   13/13 Albums    
[🎵] Radiohead            ████░░░░░░ 40%    6/15 Albums     [⬇ Download Missing]
```

---

## Progress Bar Design

**Inspired by:** Lidarr/Sonarr availability indicators

### Visual Representation

```
Complete (100%):
████████████████████ 100%  (All tracks downloaded)

Partial (60%):
████████████░░░░░░░░ 60%   (12/20 albums)

Missing (0%):
░░░░░░░░░░░░░░░░░░░░ 0%    (No local files)

Queued (download in progress):
████████████▶▶▶▶░░░░ 60% ⏳ (3 downloads active)
```

### Color Coding

| Completeness | Bar Color | Border Color | Status |
|--------------|-----------|--------------|--------|
| 100% | `#10b981` (green) | Green | ✅ Complete |
| 75-99% | `#eab308` (yellow) | Yellow | ⚠️ Almost Complete |
| 50-74% | `#f59e0b` (orange) | Orange | ⚠️ Partial |
| 1-49% | `#ef4444` (red) | Red | ❌ Mostly Missing |
| 0% | `#6b7280` (gray) | Gray | ❌ No Local Files |

---

## Service Badges

**Location:** Top-left corner of artist card

**Design:**
```
[🎵 Spotify]  ← Followed from Spotify
[🎵 Tidal]    ← Followed from Tidal
[🎵🎵]        ← Followed on multiple services (hover shows all)
```

**Badge Behavior:**
- **Click:** Filter library by this service
- **Hover:** Show tooltip: "Followed on Spotify since [date]"
- **Multiple services:** Badge shows count (e.g., "2 services"), hover shows list

---

## Filter Bar

**Location:** Top of library view (below search bar)

```
┌─────────────────────────────────────────────────────────┐
│ [All (420)] [Local (250)] [Remote (170)] [Incomplete ⚠️ (120)] │
│                                                         │
│ Services: [All] [🎵 Spotify] [🎵 Tidal] [🎵 Deezer]    │
└─────────────────────────────────────────────────────────┘
```

**Filter Logic:**

| Filter | Shows |
|--------|-------|
| **All** | All artists (local + followed) |
| **Local** | Artists with 100% completeness |
| **Remote** | Followed artists with 0% local files |
| **Incomplete** | Artists with 1-99% completeness (action needed) |

**Service Filters:**
- Combine with completeness filters (e.g., "Incomplete Spotify Artists")
- Multi-select: Show artists from Spotify OR Tidal

---

## Quick Actions

### On Artist Card

**"Download Missing" Button:**
- **Visible when:** Completeness < 100%
- **Action:** Queue all missing albums for download
- **Confirmation:** "Queue 4 albums (58 tracks) for download?"

**Context Menu (Right-click):**
```
┌──────────────────────────────┐
│ ⬇ Download All               │
│ 📥 Download Missing Albums   │
│ 🔔 Monitor New Releases      │
│ 📊 View Statistics           │
│ ──────────────────────────   │
│ 🔗 Open in Spotify           │
│ 🔗 Open in Tidal             │
│ ──────────────────────────   │
│ ❌ Unfollow Artist           │
└──────────────────────────────┘
```

---

## Artist Detail View

**Triggered by:** Click on artist card

### Layout

```
┌─────────────────────────────────────────────────────┐
│ ← Back to Library                                   │
│                                                     │
│  [Artist Cover]   Pink Floyd                       │
│                   ████████████░░░░ 80%              │
│                   16/20 Albums • 180/225 Tracks    │
│                   Followed on: 🎵 Spotify          │
│                                                     │
│  [⬇ Download All Missing] [🔔 Monitor Releases]    │
│                                                     │
│ ─────────────────────────────────────────────────── │
│                                                     │
│ Albums (sorted by release date ▼)                  │
│                                                     │
│ ┌─────────────────────────────────────┐           │
│ │ The Dark Side of the Moon (1973)    │           │
│ │ ██████████████████████ 100%         │ ✅        │
│ │ 10/10 Tracks • 320kbps MP3         │           │
│ │ [▶ Play] [⬇ Re-download FLAC]      │           │
│ └─────────────────────────────────────┘           │
│                                                     │
│ ┌─────────────────────────────────────┐           │
│ │ Wish You Were Here (1975)           │           │
│ │ ████████████░░░░░░░░░░ 50%          │ ⚠️        │
│ │ 3/6 Tracks                          │           │
│ │ [⬇ Download Missing]                │           │
│ └─────────────────────────────────────┘           │
│                                                     │
│ ┌─────────────────────────────────────┐           │
│ │ The Division Bell (1994)            │           │
│ │ ░░░░░░░░░░░░░░░░░░░░░░ 0%           │ ❌        │
│ │ 0/11 Tracks                         │           │
│ │ [⬇ Download Album]                  │           │
│ └─────────────────────────────────────┘           │
└─────────────────────────────────────────────────────┘
```

### Album Card States

**Complete Album:**
```
✅ The Dark Side of the Moon (1973)
██████████████████████ 100%
10/10 Tracks • 320kbps MP3
[▶ Play] [⬇ Re-download FLAC]
```

**Partial Album:**
```
⚠️ Wish You Were Here (1975)
████████████░░░░░░░░░░ 50%
3/6 Tracks
Missing: Shine On You Crazy Diamond (Parts 1-5), Have a Cigar, Wish You Were Here
[⬇ Download Missing]
```

**Missing Album:**
```
❌ The Division Bell (1994)
░░░░░░░░░░░░░░░░░░░░░░ 0%
0/11 Tracks
[⬇ Download Album]
```

---

## Settings Integration

**Location:** Settings → Library

```
┌─────────────────────────────────────────────────────┐
│ Library Settings                                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Followed Artists                                    │
│ ☑ Auto-download new releases from followed artists │
│ ☐ Auto-download entire discography when following  │
│                                                     │
│ New Release Handling:                              │
│ ○ Notify only (show in "New Releases" section)    │
│ ● Notify + Auto-download                          │
│ ○ Silent add to library (no notification)         │
│                                                     │
│ Quality Preferences:                               │
│ Minimum bitrate: [320kbps ▼]                       │
│ ☑ Prefer lossless (FLAC) when available           │
│                                                     │
│ Display Options:                                    │
│ Default view: [Grid ▼] (Grid / List)              │
│ Default filter: [All ▼] (All / Local / Incomplete) │
│ ☑ Show service badges on artist cards             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Notification System

### New Release Detected

```
┌────────────────────────────────────────┐
│ 🎵 New Album from Pink Floyd           │
│                                        │
│ The Endless River (2014)               │
│ 18 Tracks                              │
│                                        │
│ [⬇ Download Now] [Add to Queue] [Dismiss] │
└────────────────────────────────────────┘
```

### Download Complete

```
┌────────────────────────────────────────┐
│ ✅ Download Complete                   │
│                                        │
│ Pink Floyd - Wish You Were Here        │
│ 3 tracks added (15.2 MB)               │
│                                        │
│ Artist now 80% complete!               │
│                                        │
│ [View Artist] [Dismiss]                │
└────────────────────────────────────────┘
```

---

## Bulk Operations

**Select Multiple Artists:**
```
[✓] Pink Floyd
[✓] The Beatles
[ ] Radiohead

Selected: 2 artists

[⬇ Download All Missing] [🔔 Monitor All] [❌ Unfollow All]
```

---

## Mobile Responsive Design

**Artist Card (Mobile):**
```
┌───────────────────────┐
│ [🎵] Pink Floyd       │
│ [Album Cover]         │
│ ████████░░ 80%        │
│ 16/20 Albums          │
│ [⬇ Download Missing]  │
└───────────────────────┘
```

**Filters collapse to dropdown:**
```
[Filters ▼] (420 artists)
```

---

## Accessibility

- **Progress bars:** Include `aria-label="80% complete, 16 of 20 albums downloaded"`
- **Color coding:** Supplement with icons (✅⚠️❌) for color-blind users
- **Keyboard navigation:** Arrow keys to navigate cards, Enter to open detail view
- **Screen reader:** Announce completeness on focus: "Pink Floyd, 80% complete, 16 of 20 albums"

---

## Performance Considerations

**Large Libraries (1000+ artists):**
- **Virtualized scrolling** (render only visible cards)
- **Lazy load album covers** (load on scroll)
- **Cached completeness** (pre-calculated in `artist_completeness` table)

**Target Metrics:**
- Initial load: <500ms (1000 artists)
- Scroll performance: 60fps
- Filter change: <100ms

---

## Implementation Phases

### Phase 1: Basic Display (v2.0)
- ✅ Artist cards with progress bars
- ✅ Color coding (green/yellow/red)
- ✅ Filter: All/Local/Remote

### Phase 2: Interactions (v2.1)
- ✅ "Download Missing" button
- ✅ Service badges
- ✅ Filter by service
- ✅ Context menu

### Phase 3: Advanced (v2.2)
- ✅ Bulk operations
- ✅ New release notifications
- ✅ Auto-download settings
- ✅ Mobile responsive

---

## Related Documentation

- [Plugin System ADR](../architecture/plugin-system-adr.md) - Core architecture decisions
- [Download Management](./download-management.md) - How downloads are queued/processed
- [Settings Schema](./settings-schema.md) - User preference storage

---

**Last Updated:** 2025-12-10  
**Author:** GitHub Copilot + User Session  
**Status:** Design Approved, Awaiting Implementation
