# 🔄 SoulSpot TypeScript Migration Checklist

> **Philosophie:** Feature-für-Feature Migration mit klarer Priorisierung.  
> Keine Doppelungen, keine Legacy-Schulden, saubere Architektur.

---

## 📊 Migrations-Übersicht

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MIGRATION ROADMAP                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1 (Week 1-2)    Phase 2 (Week 3-4)    Phase 3 (Week 5-6)           │
│  ├── Foundation        ├── Library Core       ├── Provider Integration    │
│  │   ├── DB Schema     │   ├── Artists        │   ├── Spotify OAuth       │
│  │   ├── Auth          │   ├── Albums         │   ├── Deezer OAuth        │
│  │   └── Settings      │   ├── Tracks         │   ├── slskd Client        │
│  │                     │   └── Playlists      │   └── MusicBrainz         │
│  │                     │                      │                            │
│  Phase 4 (Week 7-8)    Phase 5 (Week 9-10)                                │
│  ├── Downloads         ├── Automation                                      │
│  │   ├── Queue         │   ├── Watchlists                                  │
│  │   ├── Workers       │   ├── Filter Rules                                │
│  │   └── Progress      │   └── Auto-Download                               │
│  │                     │                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📝 Legende

| Symbol | Bedeutung |
|--------|-----------|
| ⬜ | Nicht gestartet |
| 🟡 | In Arbeit |
| ✅ | Abgeschlossen |
| ❌ | Übersprungen / Nicht portieren |
| 🔴 | Blocker / Problem |

---

## Phase 1: Foundation (Week 1-2)

### 1.1 Database Schema (Prisma)

> **Ziel:** Prisma Schema definieren basierend auf SQLAlchemy Models

| Status | Entity | Python Model | Prisma Model | Notizen |
|--------|--------|--------------|--------------|---------|
| ⬜ | **Artist** | `ArtistModel` | `Artist` | Multi-Provider URIs (spotify, deezer, tidal) |
| ⬜ | **Album** | `AlbumModel` | `Album` | Lidarr-style types (primary/secondary) |
| ⬜ | **Track** | `TrackModel` | `Track` | ISRC als Universal Key |
| ⬜ | **Playlist** | `PlaylistModel` | `Playlist` | Source: MANUAL, SPOTIFY, LIKED_SONGS |
| ⬜ | **PlaylistTrack** | `PlaylistTrackModel` | `PlaylistTrack` | Position-ordered |
| ⬜ | **Download** | `DownloadModel` | `Download` | Retry-Logik integriert |
| ⬜ | **ArtistDiscography** | `ArtistDiscographyModel` | `ArtistDiscography` | Discovery, nicht Ownership |
| ⬜ | **ArtistWatchlist** | `ArtistWatchlistModel` | `ArtistWatchlist` | Auto-Download bei Releases |
| ⬜ | **FilterRule** | `FilterRuleModel` | `FilterRule` | Whitelist/Blacklist |
| ⬜ | **AutomationRule** | `AutomationRuleModel` | `AutomationRule` | Trigger-basiert |
| ⬜ | **QualityUpgrade** | `QualityUpgradeCandidateModel` | `QualityUpgrade` | Bitrate-Improvements |
| ⬜ | **SpotifySession** | `SpotifySessionModel` | `SpotifySession` | OAuth Token Storage |
| ⬜ | **DeezerSession** | `DeezerSessionModel` | `DeezerSession` | OAuth Token Storage |
| ⬜ | **AppSetting** | `AppSettingModel` | `AppSetting` | Key-Value Config |
| ⬜ | **LibraryScan** | `LibraryScanModel` | `LibraryScan` | Scan-History |
| ⬜ | **FileDuplicate** | `FileDuplicateModel` | `FileDuplicate` | Duplicate-Tracking |
| ⬜ | **Blocklist** | `BlocklistModel` | `Blocklist` | Blocked Artists/Albums |
| ⬜ | **QualityProfile** | `QualityProfileModel` | `QualityProfile` | Download-Qualität |
| ⬜ | **BackgroundJob** | `BackgroundJobModel` | `BackgroundJob` | Job-Status Tracking |

**Migrations-Script:**
```bash
# Nach Prisma Schema Definition
npx prisma migrate dev --name initial_schema
npx prisma generate
```

### 1.2 Authentication System

> **Ziel:** OAuth für Spotify/Deezer + Session Management

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Spotify OAuth Flow** | `spotify_auth_service.py` | `lib/providers/spotify/auth.ts` | PKCE + State |
| ⬜ | **Spotify Token Refresh** | `token_refresh_worker.py` | BullMQ Worker | Automatisch 5min vor Expiry |
| ⬜ | **Deezer OAuth Flow** | `deezer_auth_service.py` | `lib/providers/deezer/auth.ts` | Simpler als Spotify |
| ⬜ | **Session Storage (DB)** | `SpotifySessionModel` | Prisma + Cookie | Session ID in Cookie |
| ⬜ | **Session Middleware** | `api/dependencies.py` | Next.js Middleware | Auth Check per Route |
| ❌ | ~~Cookie Security~~ | - | **Eingebaut** | Next.js Cookies API |

**tRPC Procedures:**
```typescript
// lib/trpc/routers/auth.ts
router({
  spotify: {
    getAuthUrl: publicProcedure.query(),
    callback: publicProcedure.input(z.object({ code, state })).mutation(),
    logout: protectedProcedure.mutation(),
    status: publicProcedure.query(),
  },
  deezer: {
    getAuthUrl: publicProcedure.query(),
    callback: publicProcedure.input(z.object({ code })).mutation(),
    logout: protectedProcedure.mutation(),
    status: publicProcedure.query(),
  },
})
```

### 1.3 Settings & Configuration

> **Ziel:** App Settings UI + DB-basierte Config

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **App Settings Service** | `app_settings_service.py` | `lib/services/settings.ts` | Key-Value Store |
| ⬜ | **Provider Credentials** | DB `app_settings` | DB `AppSetting` | Client ID/Secret |
| ⬜ | **Download Settings** | `settings.py` | DB `AppSetting` | Paths, Quality Defaults |
| ⬜ | **slskd Configuration** | `app_settings` | DB `AppSetting` | URL, API Key |
| ⬜ | **Settings UI Page** | `templates/settings.html` | `app/settings/page.tsx` | React Components |
| ❌ | ~~.env für Credentials~~ | - | **NICHT VERWENDEN** | Nur DB-Config! |

**Kategorien migrieren:**
```typescript
const settingsCategories = {
  providers: ["spotify.*", "deezer.*", "slskd.*"],
  downloads: ["download.*", "quality.*"],
  library: ["library.*", "scan.*"],
  automation: ["automation.*", "watchlist.*"],
};
```

---

## Phase 2: Library Core (Week 3-4)

### 2.1 Artists

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **List Artists** | `artists.py` router | `trpc.artist.list` | Pagination + Filter |
| ⬜ | **Artist Detail** | `artists.py` | `trpc.artist.byId` | Include albums/tracks count |
| ⬜ | **Artist Search** | `search.py` | `trpc.artist.search` | Case-insensitive |
| ⬜ | **Artist Images** | `images/artist_image_service.py` | `lib/services/images.ts` | WebP Caching |
| ⬜ | **Artist Genres/Tags** | `ArtistModel.genres/tags` | JSON Field | Array stored as JSON |
| ⬜ | **Artist Stats** | `stats_service.py` | `trpc.artist.stats` | Track/Album counts |
| ⬜ | **Artist Merge** | `library_merge_service.py` | `trpc.artist.merge` | Combine duplicates |
| ❌ | ~~Spotify Artists Table~~ | - | **UNIFIED** | Alles in `Artist` Tabelle |

### 2.2 Albums

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **List Albums** | `library/*.py` | `trpc.album.list` | Filter by artist, year, type |
| ⬜ | **Album Detail** | `library/*.py` | `trpc.album.byId` | Include tracks |
| ⬜ | **Album Types** | `AlbumModel.primary_type` | Enum | album, single, ep, compilation |
| ⬜ | **Album Artwork** | `images/album_artwork_service.py` | `lib/services/images.ts` | WebP + Placeholder |
| ⬜ | **Album Completeness** | `album_completeness.py` | `trpc.album.completeness` | Missing tracks check |
| ⬜ | **Album Discography** | `ArtistDiscographyModel` | `trpc.album.discography` | All releases eines Artists |
| ❌ | ~~is_compilation Flag~~ | - | **secondary_types** | Lidarr-Style Array |

### 2.3 Tracks

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **List Tracks** | `tracks.py` | `trpc.track.list` | Heavy pagination! |
| ⬜ | **Track Detail** | `tracks.py` | `trpc.track.byId` | Full metadata |
| ⬜ | **Track Search** | `search.py` + `advanced_search.py` | `trpc.track.search` | Title, artist, album, ISRC |
| ⬜ | **Track Audio Info** | `TrackModel.audio_*` | `Track.audioInfo` | Bitrate, Format, Sample Rate |
| ⬜ | **Track File Info** | `TrackModel.file_*` | `Track.fileInfo` | Size, Hash, Path |
| ⬜ | **Broken Tracks** | `is_broken` flag | `trpc.track.broken` | Corrupt/missing files |
| ⬜ | **Duplicate Detection** | `duplicate_service.py` | `trpc.track.duplicates` | By hash, ISRC |
| ⬜ | **Metadata Editing** | `metadata.py` router | `trpc.track.updateMetadata` | Tag editing |
| ⬜ | **Track Enrichment** | `enrichment_service.py` | BullMQ Worker | MusicBrainz lookup |

### 2.4 Playlists

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **List Playlists** | `playlists.py` | `trpc.playlist.list` | Include track count |
| ⬜ | **Playlist Detail** | `playlists.py` | `trpc.playlist.byId` | Include tracks ordered |
| ⬜ | **Create Playlist** | `playlist_service.py` | `trpc.playlist.create` | Manual creation |
| ⬜ | **Add/Remove Tracks** | `playlist_service.py` | `trpc.playlist.addTrack/remove` | Position ordering |
| ⬜ | **Reorder Tracks** | `playlist_service.py` | `trpc.playlist.reorder` | Drag & drop |
| ⬜ | **Playlist Cover** | `images/*.py` | `lib/services/images.ts` | WebP |
| ⬜ | **Liked Songs** | `is_liked_songs` flag | Special handling | No Spotify URI |
| ⬜ | **Blacklist Playlist** | `is_blacklisted` | `trpc.playlist.blacklist` | Skip sync |

---

## Phase 3: Provider Integration (Week 5-6)

### 3.1 Spotify Integration

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Spotify Client** | `infrastructure/integrations/spotify_client.py` | `lib/providers/spotify/client.ts` | Rate limiting included |
| ⬜ | **Sync Playlists** | `spotify_sync_service.py` | BullMQ Worker | Full + Incremental |
| ⬜ | **Sync Liked Songs** | `spotify_sync_service.py` | BullMQ Worker | Special playlist |
| ⬜ | **Sync Followed Artists** | `spotify_sync_service.py` | BullMQ Worker | Populate Artist table |
| ⬜ | **Browse New Releases** | `browse_service.py` | `trpc.spotify.newReleases` | Regional releases |
| ⬜ | **Search Spotify** | `spotify_client.py` | `trpc.spotify.search` | Tracks, albums, artists |
| ⬜ | **Get Recommendations** | `discover_service.py` | `trpc.spotify.recommendations` | Based on seeds |
| ❌ | ~~spotify_artists Table~~ | - | **MERGED** | In unified `Artist` |
| ❌ | ~~spotify_albums Table~~ | - | **MERGED** | In unified `Album` |

### 3.2 Deezer Integration

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Deezer Client** | `infrastructure/integrations/deezer_client.py` | `lib/providers/deezer/client.ts` | Public + Auth APIs |
| ⬜ | **Browse New Releases** | `deezer_sync_service.py` | `trpc.deezer.newReleases` | Editorial picks |
| ⬜ | **Browse Charts** | `deezer_sync_service.py` | `trpc.deezer.charts` | Top tracks/albums |
| ⬜ | **Search Deezer** | `deezer_client.py` | `trpc.deezer.search` | Tracks, albums, artists |
| ⬜ | **Sync Favorites** | `deezer_sync_service.py` | BullMQ Worker | Artists, albums, tracks |
| ⬜ | **Artist Discography** | `deezer_sync_service.py` | `trpc.deezer.artistDiscography` | For ArtistDiscography table |
| ❌ | ~~deezer_* Tables~~ | - | **MERGED** | In unified tables |

### 3.3 slskd Integration

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **slskd Client** | `infrastructure/integrations/slskd_client.py` | `lib/providers/slskd/client.ts` | REST API wrapper |
| ⬜ | **Search Files** | `slskd_client.py` | `trpc.slskd.search` | Query Soulseek network |
| ⬜ | **Download File** | `slskd_client.py` | `trpc.slskd.download` | Initiate download |
| ⬜ | **Download Status** | `slskd_client.py` | `trpc.slskd.status` | Progress, state |
| ⬜ | **Health Check** | `slskd_client.py` | `trpc.slskd.health` | API reachability |
| ⬜ | **Transfer Stats** | `slskd_client.py` | `trpc.slskd.stats` | Speed, queue |

### 3.4 MusicBrainz Integration

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **MB Client** | `infrastructure/integrations/musicbrainz_client.py` | `lib/providers/musicbrainz/client.ts` | Rate limited (1/sec) |
| ⬜ | **Lookup by ISRC** | `musicbrainz_client.py` | `lib/providers/musicbrainz/` | Primary enrichment |
| ⬜ | **Artist Lookup** | `musicbrainz_client.py` | `lib/providers/musicbrainz/` | MBID resolution |
| ⬜ | **Release Lookup** | `musicbrainz_client.py` | `lib/providers/musicbrainz/` | Album metadata |
| ⬜ | **Cover Art Archive** | `musicbrainz_client.py` | `lib/providers/musicbrainz/` | Album artwork fallback |

---

## Phase 4: Downloads (Week 7-8)

### 4.1 Download Queue

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Queue Management** | `download_manager.py` | BullMQ Queue | Priority-based |
| ⬜ | **Add to Queue** | `download_manager_service.py` | `trpc.download.add` | Single or batch |
| ⬜ | **Remove from Queue** | `download_manager_service.py` | `trpc.download.remove` | Cancel pending |
| ⬜ | **Prioritize Download** | `download_manager_service.py` | `trpc.download.setPriority` | Move up/down |
| ⬜ | **Queue Status** | `download_manager.py` router | `trpc.download.queueStatus` | Counts by status |
| ⬜ | **Clear Completed** | `download_manager_service.py` | `trpc.download.clearCompleted` | Cleanup |
| ⬜ | **Retry Failed** | `download_manager_service.py` | `trpc.download.retryFailed` | Bulk retry |

### 4.2 Download Workers

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Download Worker** | `download_worker.py` | `workers/download.worker.ts` | slskd + File handling |
| ⬜ | **Search Worker** | `download_queue_worker.py` | `workers/search.worker.ts` | Find best match |
| ⬜ | **Progress Tracking** | `download_status_worker.py` | SSE oder WebSocket | Real-time updates |
| ⬜ | **Post-Processing** | `postprocessing/*.py` | `workers/postprocess.worker.ts` | Tagging, organizing |
| ⬜ | **Auto-Import** | `auto_import.py` | `workers/import.worker.ts` | Move to library |
| ⬜ | **Retry Scheduler** | Retry fields in `DownloadModel` | BullMQ Delayed Jobs | Exponential backoff |

### 4.3 Quality Profiles

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Profile CRUD** | `quality_profiles.py` router | `trpc.qualityProfile.*` | Create, edit, delete |
| ⬜ | **Default Profile** | `QualityProfileModel` | `AppSetting` | System default |
| ⬜ | **Format Priority** | `QualityProfileModel` | `QualityProfile.formats` | FLAC > MP3 320 > ... |
| ⬜ | **Bitrate Thresholds** | `QualityProfileModel` | `QualityProfile.minBitrate` | Minimum acceptable |
| ⬜ | **Quality Upgrade** | `quality_upgrade_service.py` | BullMQ Worker | Detect & download better |

---

## Phase 5: Automation (Week 9-10)

### 5.1 Watchlists

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Artist Watchlist** | `watchlist_service.py` | `trpc.watchlist.*` | Monitor for releases |
| ⬜ | **Add to Watchlist** | `automation_watchlists.py` | `trpc.watchlist.add` | Per artist |
| ⬜ | **Check Frequency** | `ArtistWatchlistModel` | `ArtistWatchlist.checkFrequency` | Hours between checks |
| ⬜ | **Auto-Download Toggle** | `ArtistWatchlistModel` | `ArtistWatchlist.autoDownload` | Enable/disable |
| ⬜ | **Release Monitor Worker** | `automation_workers.py` | `workers/watchlist.worker.ts` | Periodic check |

### 5.2 Filter Rules

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Filter CRUD** | `automation_filters.py` | `trpc.filter.*` | Create, edit, delete |
| ⬜ | **Whitelist/Blacklist** | `filter_type` enum | `FilterRule.type` | Include/Exclude |
| ⬜ | **Target Types** | `target` field | `FilterRule.target` | keyword, user, format, bitrate |
| ⬜ | **Regex Support** | `is_regex` flag | `FilterRule.isRegex` | Pattern matching |
| ⬜ | **Apply Filters** | `filter_service.py` | `lib/services/filter.ts` | During search/download |

### 5.3 Automation Rules

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Rule CRUD** | `automation_rules.py` | `trpc.automation.*` | Create, edit, delete |
| ⬜ | **Triggers** | `trigger` field | Enum | new_release, missing_album, quality_upgrade |
| ⬜ | **Actions** | `action` field | Enum | search_and_download, notify_only, add_to_queue |
| ⬜ | **Rule Execution** | `automation_workflow_service.py` | `workers/automation.worker.ts` | Process triggers |
| ⬜ | **Execution History** | `AutomationRuleModel` stats | `AutomationRule` | Counts, last triggered |

### 5.4 Library Management

| Status | Feature | Python Source | TypeScript Target | Notizen |
|--------|---------|---------------|-------------------|---------|
| ⬜ | **Library Scan** | `library_scanner_service.py` | BullMQ Worker | Full + Incremental |
| ⬜ | **File Discovery** | `file_discovery_service.py` | `workers/scan.worker.ts` | Find audio files |
| ⬜ | **Duplicate Detection** | `deduplication_checker.py` | `workers/dedupe.worker.ts` | Hash-based |
| ⬜ | **Library Cleanup** | `library_cleanup_service.py` | `trpc.library.cleanup` | Remove orphans |
| ⬜ | **Blocklist** | `blocklist.py` router | `trpc.blocklist.*` | Blocked items |

---

## Phase 6: UI & Polish (Week 9-10, parallel)

### 6.1 Core UI Components

| Status | Component | Python Template | React Component | Notizen |
|--------|-----------|-----------------|-----------------|---------|
| ⬜ | **Layout** | `base.html` | `app/layout.tsx` | Sidebar + Header |
| ⬜ | **Navigation** | `_nav.html` | `components/layout/nav.tsx` | shadcn/ui |
| ⬜ | **Track Card** | `_track_card.html` | `components/tracks/track-card.tsx` | Reusable |
| ⬜ | **Album Card** | `_album_card.html` | `components/albums/album-card.tsx` | Reusable |
| ⬜ | **Artist Card** | `_artist_card.html` | `components/artists/artist-card.tsx` | Reusable |
| ⬜ | **Download Progress** | `_download_item.html` | `components/downloads/download-item.tsx` | Progress bar |
| ⬜ | **Search Bar** | `_search.html` | `components/search/search-bar.tsx` | Global search |
| ⬜ | **Pagination** | Custom | `components/ui/pagination.tsx` | shadcn/ui |
| ⬜ | **Loading States** | Custom | `components/ui/skeleton.tsx` | shadcn/ui |

### 6.2 Pages

| Status | Page | Python Template | Next.js Route | Notizen |
|--------|------|-----------------|---------------|---------|
| ⬜ | **Dashboard** | `index.html` | `app/page.tsx` | Overview stats |
| ⬜ | **Library** | `library.html` | `app/library/page.tsx` | Artists/Albums/Tracks tabs |
| ⬜ | **Artist Detail** | `artist.html` | `app/library/artists/[id]/page.tsx` | Albums + tracks |
| ⬜ | **Album Detail** | `album.html` | `app/library/albums/[id]/page.tsx` | Track list |
| ⬜ | **Playlists** | `playlists.html` | `app/playlists/page.tsx` | All playlists |
| ⬜ | **Playlist Detail** | `playlist.html` | `app/playlists/[id]/page.tsx` | Track list + ordering |
| ⬜ | **Downloads** | `downloads.html` | `app/downloads/page.tsx` | Queue + history |
| ⬜ | **Search** | `search.html` | `app/search/page.tsx` | Multi-provider |
| ⬜ | **Settings** | `settings.html` | `app/settings/page.tsx` | All config |
| ⬜ | **Automation** | `automation.html` | `app/automation/page.tsx` | Rules + watchlists |

---

## 🚫 Was NICHT migriert wird

| Feature | Grund | Alternative |
|---------|-------|-------------|
| **HTMX Partials** | React Components | Server Components + Client Components |
| **Jinja2 Templates** | React | Next.js App Router |
| **SQLite** | PostgreSQL | Keine DB Locks mehr |
| **Python Workers** | BullMQ | Type-safe Workers |
| **aiosqlite** | Prisma | ORM mit Connection Pooling |
| **In-Memory Sessions** | DB Sessions | Persistent across restarts |
| **Multiple Artist Tables** | Unified Library | Ein `Artist` Tabelle |
| **Widget System** | Removed | War bereits deprecated |

---

## 📋 Migration Checklist Template

Für jedes Feature:

```markdown
### Feature: [Name]

**Python Source:** `path/to/source.py`
**TypeScript Target:** `path/to/target.ts`

#### Tasks:
- [ ] Analyze Python implementation
- [ ] Define Zod schema
- [ ] Create tRPC procedure OR BullMQ worker
- [ ] Implement business logic
- [ ] Add to router/queue
- [ ] Create React component (if UI)
- [ ] Manual testing
- [ ] Update this checklist

#### Breaking Changes:
- [ ] None
- [ ] List changes...

#### Dependencies:
- Requires: [list features]
- Blocks: [list features]
```

---

## 🔄 Sync Strategy

### Für bestehende Python-DB:

1. **Export Python Data** → JSON/CSV
2. **Prisma Seed Script** → Import
3. **Verify Counts** → Artists, Albums, Tracks, Playlists

```typescript
// prisma/seed.ts
import { PrismaClient } from "@prisma/client";
import pythonExport from "./python-export.json";

const prisma = new PrismaClient();

async function main() {
  // Import artists first (FK constraint)
  for (const artist of pythonExport.artists) {
    await prisma.artist.create({
      data: {
        id: artist.id,  // Keep same UUIDs!
        name: artist.name,
        spotifyUri: artist.spotify_uri,
        deezerId: artist.deezer_id,
        // ... map all fields
      },
    });
  }
  // Then albums, tracks, playlists...
}
```

---

## 📊 Progress Tracking

| Phase | Features | Completed | Percentage |
|-------|----------|-----------|------------|
| **Phase 1** | 18 | 0 | 0% |
| **Phase 2** | 25 | 0 | 0% |
| **Phase 3** | 21 | 0 | 0% |
| **Phase 4** | 16 | 0 | 0% |
| **Phase 5** | 17 | 0 | 0% |
| **Phase 6** | 20 | 0 | 0% |
| **TOTAL** | **117** | **0** | **0%** |

---

**Letzte Aktualisierung:** $(date +%Y-%m-%d)
