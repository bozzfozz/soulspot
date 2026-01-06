# SoulSpot TypeScript - Full Rewrite Architecture

> **Version:** 1.0  
> **Status:** 🚀 Implementation Ready  
> **Date:** 2025-01-18  
> **Decision:** Full Rewrite (keine Migration)

---

## 🎯 Warum Full Rewrite?

| Strangler Fig | Full Rewrite |
|---------------|--------------|
| ⚠️ Zwei Systeme parallel warten | ✅ Ein System, volle Konzentration |
| ⚠️ Shared DB = Komplexität | ✅ Sauberes Schema von Anfang an |
| ⚠️ 16 Wochen | ✅ 8-10 Wochen (fokussiert) |
| ⚠️ Bugs in beiden Systemen | ✅ Nur ein System |
| ⚠️ Python-Workarounds bleiben | ✅ Clean Slate |

**Entscheidung:** Full Rewrite mit den Learnings aus Python-Version.

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SoulSpot TypeScript Architecture                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│                              ┌─────────────────┐                                │
│                              │   Bun Runtime   │                                │
│                              └────────┬────────┘                                │
│                                       │                                          │
│  ┌────────────────────────────────────┼────────────────────────────────────────┐│
│  │                          Next.js 14 App Router                              ││
│  │  ┌──────────────────────────────────────────────────────────────────────┐   ││
│  │  │                        React Server Components                        │   ││
│  │  │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │   ││
│  │  │   │  /library  │  │  /browse   │  │ /downloads │  │ /settings  │    │   ││
│  │  │   │  Artists   │  │  Releases  │  │  Queue     │  │  Providers │    │   ││
│  │  │   │  Albums    │  │  Charts    │  │  Progress  │  │  Library   │    │   ││
│  │  │   │  Tracks    │  │  Search    │  │  History   │  │  Account   │    │   ││
│  │  │   └────────────┘  └────────────┘  └────────────┘  └────────────┘    │   ││
│  │  └──────────────────────────────────────────────────────────────────────┘   ││
│  │                                    │                                         ││
│  │                                    │ Server Actions / tRPC                   ││
│  │                                    ▼                                         ││
│  │  ┌──────────────────────────────────────────────────────────────────────┐   ││
│  │  │                          API Layer (tRPC)                            │   ││
│  │  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   ││
│  │  │   │ libraryRouter│  │ browseRouter │  │downloadRouter│              │   ││
│  │  │   │ • getArtists │  │ • newReleases│  │ • queueTrack │              │   ││
│  │  │   │ • getAlbums  │  │ • charts     │  │ • getStatus  │              │   ││
│  │  │   │ • getTracks  │  │ • search     │  │ • retry      │              │   ││
│  │  │   └──────────────┘  └──────────────┘  └──────────────┘              │   ││
│  │  └──────────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                       │                                          │
│                                       │ Domain Services                          │
│                                       ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                           Domain Layer (lib/domain)                         ││
│  │  ┌──────────────────────────────────────────────────────────────────────┐   ││
│  │  │  Entities                    Events                    Services      │   ││
│  │  │  ┌────────────────┐          ┌──────────────────┐    ┌────────────┐ │   ││
│  │  │  │ Artist         │          │ TrackAdded       │    │ Library    │ │   ││
│  │  │  │ Album          │          │ PlaylistSynced   │    │ Service    │ │   ││
│  │  │  │ Track          │          │ DownloadComplete │    │            │ │   ││
│  │  │  │ Playlist       │          │ ArtistFollowed   │    │ Download   │ │   ││
│  │  │  │ Download       │          │ NewRelease       │    │ Service    │ │   ││
│  │  │  └────────────────┘          └──────────────────┘    └────────────┘ │   ││
│  │  └──────────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                       │                                          │
│                                       │ Repositories                             │
│                                       ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                    Infrastructure Layer (lib/infrastructure)                ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    ││
│  │  │    Prisma    │  │   Spotify    │  │    Deezer    │  │    slskd     │    ││
│  │  │  Repository  │  │    Client    │  │    Client    │  │    Client    │    ││
│  │  └──────┬───────┘  └──────────────┘  └──────────────┘  └──────────────┘    ││
│  │         │                                                                    ││
│  │         │          ┌──────────────┐  ┌──────────────┐                       ││
│  │         │          │  MusicBrainz │  │    BullMQ    │                       ││
│  │         │          │    Client    │  │    Queue     │                       ││
│  │         │          └──────────────┘  └──────────────┘                       ││
│  └─────────┼────────────────────────────────────┬──────────────────────────────┘│
│            │                                     │                               │
│            ▼                                     ▼                               │
│  ┌──────────────────┐                 ┌──────────────────┐                      │
│  │    PostgreSQL    │                 │      Redis       │                      │
│  │   (Primary DB)   │                 │  (Queue/Cache)   │                      │
│  └──────────────────┘                 └──────────────────┘                      │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                         Background Workers (BullMQ)                         ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    ││
│  │  │  SyncWorker  │  │DownloadWorker│  │MetadataWorker│  │ ScanWorker   │    ││
│  │  │              │  │              │  │              │  │              │    ││
│  │  │ Spotify/Deezer│ │  slskd       │  │ MusicBrainz  │  │ File System  │    ││
│  │  │ Sync Jobs    │  │  Downloads   │  │ Enrichment   │  │ Library Scan │    ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Projekt-Struktur

```
soulspot/
├── app/                              # Next.js App Router
│   ├── (auth)/                       # Auth Layout Group
│   │   ├── login/page.tsx
│   │   └── callback/[provider]/page.tsx
│   │
│   ├── (dashboard)/                  # Main App Layout
│   │   ├── layout.tsx                # Sidebar + Header
│   │   │
│   │   ├── page.tsx                  # Dashboard Home
│   │   │
│   │   ├── library/
│   │   │   ├── page.tsx              # Library Overview
│   │   │   ├── artists/
│   │   │   │   ├── page.tsx          # Artist Grid
│   │   │   │   └── [id]/page.tsx     # Artist Detail
│   │   │   ├── albums/
│   │   │   │   ├── page.tsx          # Album Grid
│   │   │   │   └── [id]/page.tsx     # Album Detail
│   │   │   └── tracks/page.tsx       # Track Table
│   │   │
│   │   ├── browse/
│   │   │   ├── page.tsx              # Browse Home
│   │   │   ├── new-releases/page.tsx
│   │   │   ├── charts/page.tsx
│   │   │   └── search/page.tsx
│   │   │
│   │   ├── downloads/
│   │   │   ├── page.tsx              # Download Queue
│   │   │   └── history/page.tsx
│   │   │
│   │   └── settings/
│   │       ├── page.tsx              # Settings Overview
│   │       ├── providers/page.tsx    # Spotify/Deezer Config
│   │       ├── library/page.tsx      # Library Paths
│   │       └── downloads/page.tsx    # Download Settings
│   │
│   ├── api/
│   │   ├── trpc/[trpc]/route.ts      # tRPC Handler
│   │   └── webhooks/
│   │       └── slskd/route.ts        # slskd Webhooks
│   │
│   ├── layout.tsx                    # Root Layout
│   ├── loading.tsx                   # Global Loading
│   └── error.tsx                     # Global Error
│
├── lib/                              # Shared Logic (Domain + Infrastructure)
│   │
│   ├── domain/                       # Pure Business Logic (no deps!)
│   │   │
│   │   ├── entities/                 # Domain Entities
│   │   │   ├── index.ts
│   │   │   ├── artist.ts
│   │   │   ├── album.ts
│   │   │   ├── track.ts
│   │   │   ├── playlist.ts
│   │   │   └── download.ts
│   │   │
│   │   ├── events/                   # Domain Events
│   │   │   ├── index.ts
│   │   │   ├── library.events.ts     # TrackAdded, AlbumCreated
│   │   │   ├── sync.events.ts        # PlaylistSynced, ArtistFollowed
│   │   │   └── download.events.ts    # DownloadQueued, DownloadComplete
│   │   │
│   │   ├── repositories/             # Repository Interfaces
│   │   │   ├── index.ts
│   │   │   ├── artist.repository.ts
│   │   │   ├── album.repository.ts
│   │   │   ├── track.repository.ts
│   │   │   └── download.repository.ts
│   │   │
│   │   ├── services/                 # Domain Services
│   │   │   ├── library.service.ts
│   │   │   └── download.service.ts
│   │   │
│   │   └── value-objects/            # Value Objects
│   │       ├── spotify-uri.ts
│   │       ├── isrc.ts
│   │       └── file-path.ts
│   │
│   ├── infrastructure/               # External Dependencies
│   │   │
│   │   ├── db/                       # Database (Prisma)
│   │   │   ├── client.ts             # Prisma Client
│   │   │   └── repositories/         # Prisma Implementations
│   │   │       ├── artist.repository.impl.ts
│   │   │       ├── album.repository.impl.ts
│   │   │       └── track.repository.impl.ts
│   │   │
│   │   ├── providers/                # External APIs
│   │   │   ├── spotify/
│   │   │   │   ├── client.ts
│   │   │   │   ├── types.ts
│   │   │   │   └── auth.ts
│   │   │   ├── deezer/
│   │   │   │   ├── client.ts
│   │   │   │   └── types.ts
│   │   │   ├── slskd/
│   │   │   │   ├── client.ts
│   │   │   │   └── types.ts
│   │   │   └── musicbrainz/
│   │   │       └── client.ts
│   │   │
│   │   ├── queue/                    # BullMQ
│   │   │   ├── client.ts
│   │   │   ├── queues.ts
│   │   │   └── events.ts
│   │   │
│   │   └── fs/                       # File System
│   │       ├── scanner.ts
│   │       └── metadata.ts
│   │
│   ├── trpc/                         # tRPC Setup
│   │   ├── index.ts                  # Root Router
│   │   ├── context.ts                # Request Context
│   │   ├── trpc.ts                   # tRPC Instance
│   │   └── routers/
│   │       ├── library.router.ts
│   │       ├── browse.router.ts
│   │       ├── download.router.ts
│   │       └── settings.router.ts
│   │
│   └── utils/                        # Shared Utilities
│       ├── logger.ts
│       ├── errors.ts
│       └── validation.ts
│
├── workers/                          # Background Workers (separate process)
│   ├── index.ts                      # Worker Entry Point
│   ├── sync.worker.ts                # Spotify/Deezer Sync
│   ├── download.worker.ts            # slskd Downloads
│   ├── metadata.worker.ts            # MusicBrainz Enrichment
│   └── scan.worker.ts                # Library File Scan
│
├── components/                       # React Components
│   ├── ui/                           # shadcn/ui (auto-generated)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── table.tsx
│   │   └── ...
│   │
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   ├── header.tsx
│   │   └── player.tsx
│   │
│   ├── library/
│   │   ├── artist-card.tsx
│   │   ├── album-card.tsx
│   │   ├── track-row.tsx
│   │   └── playlist-card.tsx
│   │
│   ├── browse/
│   │   ├── release-card.tsx
│   │   └── search-results.tsx
│   │
│   └── downloads/
│       ├── queue-item.tsx
│       └── progress-bar.tsx
│
├── hooks/                            # React Hooks
│   ├── use-library.ts
│   ├── use-downloads.ts
│   └── use-player.ts
│
├── stores/                           # Zustand Stores
│   ├── player.store.ts
│   └── ui.store.ts
│
├── prisma/
│   ├── schema.prisma                 # Database Schema
│   └── migrations/                   # Auto-generated
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
├── public/                           # Static Assets
│   └── icons/
│
├── .env.example
├── .env.local
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js
└── README.md
```

---

## 📦 Tech Stack Details

### Package.json

```json
{
  "name": "soulspot",
  "version": "2.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev --turbo",
    "build": "next build",
    "start": "next start",
    "workers": "bun run workers/index.ts",
    "db:generate": "prisma generate",
    "db:push": "prisma db push",
    "db:migrate": "prisma migrate dev",
    "db:studio": "prisma studio",
    "lint": "biome check .",
    "format": "biome format . --write",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "14.2.x",
    "react": "18.3.x",
    "react-dom": "18.3.x",
    
    "@trpc/server": "11.x",
    "@trpc/client": "11.x",
    "@trpc/react-query": "11.x",
    "@tanstack/react-query": "5.x",
    
    "@prisma/client": "5.x",
    "bullmq": "5.x",
    "ioredis": "5.x",
    
    "next-auth": "5.x",
    "zod": "3.x",
    
    "@radix-ui/react-*": "latest",
    "tailwindcss": "3.x",
    "class-variance-authority": "latest",
    "clsx": "latest",
    "tailwind-merge": "latest",
    "lucide-react": "latest",
    
    "zustand": "4.x",
    "music-metadata": "10.x",
    "pino": "9.x"
  },
  "devDependencies": {
    "typescript": "5.x",
    "@types/node": "20.x",
    "@types/react": "18.x",
    "prisma": "5.x",
    "@biomejs/biome": "1.x",
    "autoprefixer": "10.x",
    "postcss": "8.x"
  }
}
```

---

## 🗃️ Prisma Schema

```prisma
// prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// === ENUMS ===

enum OwnershipState {
  OWNED
  DISCOVERED
  IGNORED
}

enum DownloadState {
  NOT_NEEDED
  PENDING
  DOWNLOADING
  DOWNLOADED
  FAILED
}

enum ProviderType {
  SPOTIFY
  DEEZER
  TIDAL
  LOCAL
}

// === MAIN ENTITIES ===

model Artist {
  id              String          @id @default(cuid())
  name            String
  
  // Ownership
  ownershipState  OwnershipState  @default(DISCOVERED)
  primarySource   ProviderType?
  
  // Provider IDs
  spotifyUri      String?         @unique
  deezerId        String?         @unique
  tidalId         String?         @unique
  musicbrainzId   String?
  
  // Metadata
  imageUrl        String?
  imagePath       String?
  genres          String[]        @default([])
  tags            String[]        @default([])
  disambiguation  String?
  
  // Relations
  albums          Album[]
  tracks          Track[]
  discography     ArtistDiscography?
  
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt

  @@index([name])
  @@index([ownershipState])
  @@map("artists")
}

model Album {
  id              String          @id @default(cuid())
  title           String
  
  // Ownership
  ownershipState  OwnershipState  @default(DISCOVERED)
  primarySource   ProviderType?
  
  // Provider IDs
  spotifyUri      String?         @unique
  deezerId        String?         @unique
  tidalId         String?         @unique
  musicbrainzId   String?
  
  // Metadata
  albumType       String?         // album, single, ep, compilation
  releaseDate     DateTime?
  releaseYear     Int?
  totalTracks     Int?
  artworkUrl      String?
  artworkPath     String?
  
  // Relations
  artist          Artist          @relation(fields: [artistId], references: [id], onDelete: Cascade)
  artistId        String
  tracks          Track[]
  
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt

  @@index([artistId])
  @@index([title])
  @@index([releaseYear])
  @@map("albums")
}

model Track {
  id              String          @id @default(cuid())
  title           String
  
  // Ownership & Download
  ownershipState  OwnershipState  @default(DISCOVERED)
  downloadState   DownloadState   @default(NOT_NEEDED)
  primarySource   ProviderType?
  localPath       String?
  
  // Provider IDs
  isrc            String?
  spotifyUri      String?         @unique
  deezerId        String?         @unique
  tidalId         String?         @unique
  musicbrainzId   String?
  
  // Metadata
  durationMs      Int?
  trackNumber     Int?
  discNumber      Int?
  explicit        Boolean         @default(false)
  genre           String?
  
  // Audio Quality (for downloaded tracks)
  audioFormat     String?         // flac, mp3, etc.
  bitrate         Int?
  sampleRate      Int?
  bitDepth        Int?
  
  // Relations
  artist          Artist          @relation(fields: [artistId], references: [id], onDelete: Cascade)
  artistId        String
  album           Album?          @relation(fields: [albumId], references: [id], onDelete: SetNull)
  albumId         String?
  downloads       Download[]
  playlistTracks  PlaylistTrack[]
  
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt

  @@index([artistId])
  @@index([albumId])
  @@index([isrc])
  @@index([downloadState])
  @@map("tracks")
}

model Playlist {
  id              String          @id @default(cuid())
  name            String
  description     String?
  
  // Provider
  source          ProviderType
  spotifyUri      String?         @unique
  deezerId        String?         @unique
  
  // Metadata
  imageUrl        String?
  imagePath       String?
  isPublic        Boolean         @default(false)
  
  // Sync
  syncEnabled     Boolean         @default(true)
  lastSyncedAt    DateTime?
  
  // Relations
  tracks          PlaylistTrack[]
  
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt

  @@index([source])
  @@map("playlists")
}

model PlaylistTrack {
  id              String          @id @default(cuid())
  position        Int
  addedAt         DateTime        @default(now())
  
  playlist        Playlist        @relation(fields: [playlistId], references: [id], onDelete: Cascade)
  playlistId      String
  track           Track           @relation(fields: [trackId], references: [id], onDelete: Cascade)
  trackId         String

  @@unique([playlistId, trackId])
  @@index([playlistId])
  @@map("playlist_tracks")
}

// === DOWNLOADS ===

model Download {
  id              String          @id @default(cuid())
  
  // Status
  status          DownloadState   @default(PENDING)
  progress        Int             @default(0)  // 0-100
  error           String?
  
  // Source
  searchQuery     String
  selectedFile    String?         // slskd file path
  
  // Priority & Retry
  priority        Int             @default(0)
  retryCount      Int             @default(0)
  maxRetries      Int             @default(3)
  
  // Timing
  queuedAt        DateTime        @default(now())
  startedAt       DateTime?
  completedAt     DateTime?
  
  // Relations
  track           Track           @relation(fields: [trackId], references: [id], onDelete: Cascade)
  trackId         String

  @@index([status])
  @@index([trackId])
  @@map("downloads")
}

// === PROVIDER SESSIONS ===

model ProviderSession {
  id              String          @id @default(cuid())
  provider        ProviderType
  
  // Session
  sessionId       String          @unique
  
  // OAuth Tokens
  accessToken     String
  refreshToken    String?
  expiresAt       DateTime?
  
  // User Info
  userId          String?
  displayName     String?
  
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt

  @@index([provider])
  @@index([sessionId])
  @@map("provider_sessions")
}

// === SETTINGS ===

model Setting {
  key             String          @id
  value           String
  type            String          @default("string")  // string, number, boolean, json
  
  updatedAt       DateTime        @updatedAt

  @@map("settings")
}

// === ARTIST DISCOGRAPHY TRACKING ===

model ArtistDiscography {
  id              String          @id @default(cuid())
  
  artist          Artist          @relation(fields: [artistId], references: [id], onDelete: Cascade)
  artistId        String          @unique
  
  // Sync Status
  lastSyncedAt    DateTime?
  lastFullSyncAt  DateTime?
  albumCount      Int             @default(0)
  trackCount      Int             @default(0)
  
  // Sources Synced
  spotifySynced   Boolean         @default(false)
  deezerSynced    Boolean         @default(false)
  
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt

  @@map("artist_discography")
}

// === AUTOMATION ===

model AutomationRule {
  id              String          @id @default(cuid())
  name            String
  enabled         Boolean         @default(true)
  
  // Rule Definition (JSON)
  conditions      Json            // [{field, operator, value}]
  actions         Json            // [{type, params}]
  
  // Stats
  lastTriggeredAt DateTime?
  triggerCount    Int             @default(0)
  
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt

  @@map("automation_rules")
}

model ArtistWatchlist {
  id              String          @id @default(cuid())
  
  // What to watch
  artistName      String
  spotifyUri      String?
  deezerId        String?
  
  // Notification settings
  notifyNewAlbum  Boolean         @default(true)
  notifyNewSingle Boolean         @default(true)
  autoDownload    Boolean         @default(false)
  
  // Tracking
  lastCheckedAt   DateTime?
  
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt

  @@map("artist_watchlist")
}

// === QUALITY PROFILES ===

model QualityProfile {
  id              String          @id @default(cuid())
  name            String
  isDefault       Boolean         @default(false)
  
  // Preferences (ordered by priority)
  formatPriority  String[]        @default(["flac", "mp3"])
  minBitrate      Int?            // kbps
  maxBitrate      Int?
  preferLossless  Boolean         @default(true)
  
  // Upgrade settings
  upgradeAllowed  Boolean         @default(true)
  upgradeUntil    String?         // format to upgrade until
  
  createdAt       DateTime        @default(now())
  updatedAt       DateTime        @updatedAt

  @@map("quality_profiles")
}

// === BLOCKLIST ===

model BlocklistEntry {
  id              String          @id @default(cuid())
  
  // What's blocked
  scope           String          // artist, album, track, user
  pattern         String          // name pattern or ID
  reason          String?
  
  createdAt       DateTime        @default(now())

  @@index([scope])
  @@map("blocklist")
}
```

---

## 🎯 Feature Roadmap

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Next.js 14 Setup mit Bun
- [ ] Prisma + PostgreSQL Schema
- [ ] tRPC Setup mit React Query
- [ ] shadcn/ui Component Library
- [ ] Docker Compose (dev + prod)

### Phase 2: Library Management (Week 3-4)
- [ ] Artist/Album/Track CRUD
- [ ] Library Views (Grid, Table)
- [ ] Search & Filter
- [ ] Ownership States
- [ ] Local File Scan

### Phase 3: Provider Integration (Week 5-6)
- [ ] Spotify OAuth + API
- [ ] Deezer OAuth + API
- [ ] Playlist Sync
- [ ] Artist Follow Sync
- [ ] Browse/Search

### Phase 4: Download System (Week 7-8)
- [ ] slskd Integration
- [ ] BullMQ Queue
- [ ] Download Workers
- [ ] Progress Tracking
- [ ] Retry Logic

### Phase 5: Automation & Polish (Week 9-10)
- [ ] Automation Rules
- [ ] Artist Watchlist
- [ ] Quality Profiles
- [ ] Metadata Enrichment
- [ ] UI Polish

---

## 🐳 Docker Setup

```yaml
# docker/docker-compose.yml

services:
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://soulspot:secret@postgres:5432/soulspot
      REDIS_URL: redis://redis:6379
      NEXTAUTH_URL: http://localhost:3000
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - music:/music
      - downloads:/downloads
  
  workers:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: bun run workers/index.ts
    environment:
      DATABASE_URL: postgresql://soulspot:secret@postgres:5432/soulspot
      REDIS_URL: redis://redis:6379
    depends_on:
      - app
    volumes:
      - music:/music
      - downloads:/downloads

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: soulspot
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: soulspot
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U soulspot"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  slskd:
    image: slskd/slskd:latest
    ports:
      - "5030:5030"
      - "5031:5031"
    environment:
      SLSKD_REMOTE_CONFIGURATION: "true"
    volumes:
      - slskd_data:/app/data
      - downloads:/downloads
      - music:/music:ro

volumes:
  postgres_data:
  redis_data:
  slskd_data:
  music:
  downloads:
```

---

## 🚀 Nächste Schritte

1. **Repository erstellen**: `soulspot` (oder neuer Branch `typescript-rewrite`)
2. **Next.js Init**: `bunx create-next-app@latest --typescript --tailwind --app`
3. **Dependencies installieren**: tRPC, Prisma, BullMQ, shadcn/ui
4. **Prisma Schema** implementieren
5. **Erste Route**: `/library` mit Artist Grid

Soll ich mit dem Setup beginnen?
