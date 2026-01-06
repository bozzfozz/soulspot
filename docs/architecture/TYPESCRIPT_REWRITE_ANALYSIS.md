# SoulSpot Technology Stack Entscheidung

> **Version:** 1.0  
> **Status:** 🔍 Analyse & Entscheidung  
> **Date:** 2025-01-18  
> **Kontext:** Dream Architecture Rewrite - Python vs TypeScript

---

## 🎯 Entscheidungsfrage

**Soll SoulSpot in TypeScript (Next.js/Express/Bun) neu geschrieben werden statt die Python-Architektur zu refactoren?**

---

## 📊 Direkter Vergleich

### 1. Database & Concurrency

| Aspekt | Python (aktuell) | TypeScript (Alternative) |
|--------|------------------|--------------------------|
| **SQLite Async** | ❌ `aiosqlite` = "database is locked" | ✅ `better-sqlite3` ist synchron aber schnell |
| **PostgreSQL** | ✅ `asyncpg` ist excellent | ✅ `Prisma`/`Drizzle` sind excellent |
| **Connection Pooling** | ⚠️ NullPool nötig für SQLite | ✅ Native Pool-Support |
| **Transactions** | ✅ SQLAlchemy UoW Pattern | ✅ Prisma Transactions |
| **Migrations** | ✅ Alembic (manuell) | ✅ Prisma Migrate (auto) |

**Verdict:** 🟡 Bei PostgreSQL sind beide gleich gut. TypeScript hat Vorteil bei SQLite.

---

### 2. Type Safety & DX

| Aspekt | Python | TypeScript |
|--------|--------|------------|
| **Type Checking** | ⚠️ `mypy` opt-in, runtime untyped | ✅ Compile-time mandatory |
| **IDE Support** | ✅ Pylance ist gut | ✅ Native TypeScript Support |
| **Refactoring** | ⚠️ Rename kann Dinge übersehen | ✅ Compiler findet alles |
| **Runtime Types** | ❌ Pydantic validiert nur an Grenzen | ✅ `zod` + tRPC = E2E types |
| **Learning Curve** | ✅ Python ist einfacher | ⚠️ TypeScript hat Lernkurve |

**Verdict:** 🟢 TypeScript gewinnt bei Type Safety.

---

### 3. Frontend Integration

| Aspekt | Python + HTMX | TypeScript Full-Stack |
|--------|--------------|----------------------|
| **Rendering** | Jinja2 Templates (Server) | React/Vue/Svelte (Client) |
| **Interaktivität** | HTMX (HTML über Wire) | JavaScript (Native) |
| **State Management** | ❌ Server-State only | ✅ Client + Server State |
| **Build Process** | ⚠️ 2 Welten (Python + Vite) | ✅ 1 Build (Next.js) |
| **Hot Reload** | ⚠️ Uvicorn + Vite separat | ✅ Next.js integriert |
| **SEO** | ✅ SSR mit Jinja | ✅ SSR mit Next.js |
| **Mobile App** | ❌ Separates Projekt nötig | ✅ React Native möglich |

**Verdict:** 🟢 TypeScript Full-Stack ist kohärenter.

---

### 4. Performance & Scalability

| Aspekt | Python (FastAPI) | TypeScript (Bun/Node) |
|--------|-----------------|----------------------|
| **Requests/sec** | ~15,000 (uvicorn) | ~80,000 (Bun) |
| **Memory/Request** | ~2-5 MB | ~0.5-1 MB |
| **Startup Time** | ~2-5s | ~100-500ms |
| **GIL Impact** | ❌ Limitiert CPU-bound | ✅ Event Loop + Workers |
| **Parallel Workers** | ⚠️ Gunicorn Workers (Prozesse) | ✅ Cluster Mode (leichtgewichtig) |
| **Real Concurrency** | ❌ GIL blockiert | ✅ Echte Async |

**Verdict:** 🟢 TypeScript/Bun ist deutlich schneller.

---

### 5. Ecosystem & Libraries

| Bereich | Python | TypeScript |
|---------|--------|------------|
| **Web Framework** | FastAPI ⭐⭐⭐⭐⭐ | Express/Fastify/Hono ⭐⭐⭐⭐ |
| **ORM** | SQLAlchemy ⭐⭐⭐⭐ | Prisma ⭐⭐⭐⭐⭐ |
| **Validation** | Pydantic ⭐⭐⭐⭐⭐ | Zod ⭐⭐⭐⭐⭐ |
| **HTTP Client** | httpx ⭐⭐⭐⭐ | fetch/axios ⭐⭐⭐⭐ |
| **Job Queue** | Celery/RQ ⭐⭐⭐ | BullMQ ⭐⭐⭐⭐⭐ |
| **Testing** | pytest ⭐⭐⭐⭐⭐ | Vitest ⭐⭐⭐⭐⭐ |
| **Music/Audio** | mutagen ⭐⭐⭐⭐ | music-metadata ⭐⭐⭐ |

**Verdict:** 🟡 Beide haben gute Ecosystems.

---

### 6. Maintenance & Team

| Aspekt | Python | TypeScript |
|--------|--------|------------|
| **Codebase Size** | ~30,000 LoC aktuell | ~0 LoC (Rewrite) |
| **Migration Effort** | 4-6 Wochen Refactoring | 3-4 Monate Rewrite |
| **Knowledge Transfer** | ✅ Bestehendes Wissen | ⚠️ Lernkurve |
| **Hiring Pool** | ✅ Viele Python Devs | ✅ Noch mehr TS Devs |
| **Long-term Maint.** | ⚠️ Async-Probleme bleiben | ✅ Sauberer Start |

**Verdict:** 🟡 Rewrite ist teuer, aber zahlt sich langfristig aus.

---

## 🏗️ TypeScript Dream Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SoulSpot TypeScript Architecture                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                     Next.js 14 (App Router)                                 ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    ││
│  │  │   /app       │  │   /api       │  │  /lib        │  │  /components │    ││
│  │  │  (Pages)     │  │  (Routes)    │  │  (Logic)     │  │  (UI)        │    ││
│  │  │              │  │              │  │              │  │              │    ││
│  │  │  • library/  │  │  • trpc/     │  │  • services/ │  │  • Player    │    ││
│  │  │  • browse/   │  │  • spotify/  │  │  • repos/    │  │  • Playlist  │    ││
│  │  │  • settings/ │  │  • downloads/│  │  • events/   │  │  • Sidebar   │    ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                          │                                       │
│                                          │ tRPC (Type-Safe API)                 │
│                                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                        Backend Services                                      ││
│  │  ┌──────────────────────────────────────────────────────────────────────┐   ││
│  │  │  Domain Layer (lib/domain/)                                          │   ││
│  │  │  ├── entities/     (Artist, Album, Track, Playlist)                  │   ││
│  │  │  ├── events/       (TrackAdded, PlaylistSynced, DownloadComplete)    │   ││
│  │  │  ├── repositories/ (Interfaces)                                      │   ││
│  │  │  └── services/     (Business Logic)                                  │   ││
│  │  └──────────────────────────────────────────────────────────────────────┘   ││
│  │                                          │                                   ││
│  │  ┌──────────────────────────────────────────────────────────────────────┐   ││
│  │  │  Infrastructure (lib/infrastructure/)                                │   ││
│  │  │  ├── prisma/       (Database ORM)                                    │   ││
│  │  │  ├── spotify/      (Spotify API Client)                              │   ││
│  │  │  ├── deezer/       (Deezer API Client)                               │   ││
│  │  │  ├── slskd/        (Soulseek Client)                                 │   ││
│  │  │  └── musicbrainz/  (Metadata Client)                                 │   ││
│  │  └──────────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                          │                                       │
│                                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                        Background Workers (BullMQ)                          ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    ││
│  │  │  SyncWorker  │  │DownloadWorker│  │ MetadataWorker│ │ LibraryWorker│    ││
│  │  │              │  │              │  │              │  │              │    ││
│  │  │ • Spotify    │  │ • slskd      │  │ • MusicBrainz│  │ • File Scan  │    ││
│  │  │ • Deezer     │  │ • Retry      │  │ • Cover Art  │  │ • Dedup      │    ││
│  │  │ • Tidal      │  │ • Quality    │  │ • Genres     │  │ • Cleanup    │    ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                          │                                       │
│                    ┌─────────────────────┼─────────────────────┐                │
│                    ▼                     ▼                     ▼                │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐  │
│  │     PostgreSQL       │  │        Redis         │  │    File System       │  │
│  │  (Primary Database)  │  │  (Queue + Cache)     │  │  (Music Library)     │  │
│  └──────────────────────┘  └──────────────────────┘  └──────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Empfohlener Tech Stack

### Core Framework
```json
{
  "framework": "Next.js 14",
  "runtime": "Bun",
  "language": "TypeScript 5.3+",
  "styling": "Tailwind CSS + shadcn/ui"
}
```

### Backend
```json
{
  "api": "tRPC v11 (type-safe RPC)",
  "orm": "Prisma (PostgreSQL)",
  "queue": "BullMQ (Redis)",
  "validation": "Zod",
  "auth": "NextAuth.js v5"
}
```

### Frontend
```json
{
  "ui": "React 18 + Server Components",
  "state": "Zustand (client) + React Query (server)",
  "forms": "React Hook Form + Zod",
  "tables": "TanStack Table",
  "charts": "Recharts"
}
```

### Infrastructure
```json
{
  "database": "PostgreSQL 15",
  "cache": "Redis 7",
  "container": "Docker + Docker Compose",
  "ci": "GitHub Actions"
}
```

---

## 🔄 Migration Path

### Option A: Big Bang Rewrite (Nicht empfohlen)

```
Woche 1-4:   Setup + Core Domain
Woche 5-8:   Spotify/Deezer Integration
Woche 9-12:  Download System
Woche 13-14: UI Polish
Woche 15-16: Migration + Testing
```

**Risiken:**
- 4 Monate ohne neue Features
- Bugs müssen in beiden Systemen gefixt werden
- Hohe Wahrscheinlichkeit für Feature-Verlust

---

### Option B: Strangler Fig Pattern (Empfohlen) ⭐

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      Strangler Fig Migration                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Phase 1: Coexistence (Woche 1-4)                                               │
│  ────────────────────────────────                                               │
│  ┌─────────────────┐          ┌─────────────────┐                               │
│  │  Next.js (New)  │◀── API ──│  FastAPI (Old)  │                               │
│  │  • UI only      │          │  • All Logic    │                               │
│  │  • Proxy to API │          │  • Database     │                               │
│  └─────────────────┘          └─────────────────┘                               │
│                                                                                  │
│  Phase 2: Feature Migration (Woche 5-12)                                        │
│  ────────────────────────────────────────                                       │
│  ┌─────────────────┐          ┌─────────────────┐                               │
│  │  Next.js        │          │  FastAPI        │                               │
│  │  • UI           │          │  • Downloads    │                               │
│  │  • Browse       │          │  • Sync         │                               │
│  │  • Settings     │          │                 │                               │
│  │  • tRPC API     │◀── DB ──▶│                 │                               │
│  └─────────────────┘          └─────────────────┘                               │
│         ▲                            ▲                                          │
│         │                            │                                          │
│         └────────── Shared PostgreSQL ───────────┘                              │
│                                                                                  │
│  Phase 3: Complete Migration (Woche 13-16)                                      │
│  ─────────────────────────────────────────                                      │
│  ┌─────────────────┐                                                            │
│  │  Next.js        │                                                            │
│  │  • Everything!  │                                                            │
│  │  • Workers      │                                                            │
│  │  • API          │                                                            │
│  └─────────────────┘                                                            │
│         │                                                                        │
│         ▼                                                                        │
│  ┌─────────────────┐  ┌─────────────────┐                                       │
│  │   PostgreSQL    │  │      Redis      │                                       │
│  └─────────────────┘  └─────────────────┘                                       │
│                                                                                  │
│  FastAPI → 🗑️ Deleted                                                           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Vorteile:**
- Kontinuierliche Nutzbarkeit
- Feature-by-Feature Migration
- Rollback möglich
- Beide Systeme teilen die DB

---

## 📁 Projekt-Struktur (TypeScript)

```
soulspot-ts/
├── app/                          # Next.js App Router
│   ├── (dashboard)/              # Dashboard Layout Group
│   │   ├── library/
│   │   │   ├── artists/
│   │   │   ├── albums/
│   │   │   └── tracks/
│   │   ├── browse/
│   │   │   ├── new-releases/
│   │   │   └── charts/
│   │   ├── downloads/
│   │   └── settings/
│   ├── api/
│   │   ├── trpc/[trpc]/route.ts  # tRPC Handler
│   │   └── webhooks/
│   ├── auth/
│   │   └── [...nextauth]/
│   ├── layout.tsx
│   └── page.tsx
│
├── lib/                          # Shared Logic
│   ├── domain/                   # Domain Layer (Pure)
│   │   ├── entities/
│   │   │   ├── artist.ts
│   │   │   ├── album.ts
│   │   │   ├── track.ts
│   │   │   └── playlist.ts
│   │   ├── events/
│   │   │   ├── index.ts
│   │   │   ├── library.events.ts
│   │   │   └── download.events.ts
│   │   ├── repositories/         # Interfaces only
│   │   │   ├── artist.repository.ts
│   │   │   └── ...
│   │   └── services/             # Domain Services
│   │       ├── library.service.ts
│   │       └── download.service.ts
│   │
│   ├── infrastructure/           # External Dependencies
│   │   ├── prisma/
│   │   │   ├── schema.prisma
│   │   │   └── client.ts
│   │   ├── repositories/         # Prisma Implementations
│   │   │   ├── artist.repository.impl.ts
│   │   │   └── ...
│   │   ├── spotify/
│   │   │   ├── client.ts
│   │   │   └── types.ts
│   │   ├── deezer/
│   │   ├── slskd/
│   │   └── musicbrainz/
│   │
│   ├── trpc/                     # tRPC Setup
│   │   ├── root.ts
│   │   ├── context.ts
│   │   └── routers/
│   │       ├── library.router.ts
│   │       ├── browse.router.ts
│   │       └── download.router.ts
│   │
│   └── utils/                    # Shared Utilities
│
├── workers/                      # Background Workers
│   ├── sync.worker.ts
│   ├── download.worker.ts
│   └── metadata.worker.ts
│
├── components/                   # React Components
│   ├── ui/                       # shadcn/ui Components
│   ├── library/
│   ├── player/
│   └── layout/
│
├── prisma/
│   ├── schema.prisma
│   └── migrations/
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── package.json
├── tsconfig.json
└── README.md
```

---

## 🛠️ Code-Beispiele

### Entity mit Zod

```typescript
// lib/domain/entities/track.ts

import { z } from "zod";

export const TrackSchema = z.object({
  id: z.string().uuid(),
  title: z.string().min(1),
  artistId: z.string().uuid(),
  albumId: z.string().uuid().nullable(),
  
  // Multi-provider IDs
  isrc: z.string().nullable(),
  spotifyUri: z.string().nullable(),
  deezerId: z.string().nullable(),
  
  // Ownership
  ownershipState: z.enum(["owned", "discovered", "ignored"]),
  downloadState: z.enum(["not_needed", "pending", "downloading", "downloaded", "failed"]),
  localPath: z.string().nullable(),
  
  // Metadata
  durationMs: z.number().nullable(),
  trackNumber: z.number().nullable(),
  genre: z.string().nullable(),
  
  createdAt: z.date(),
  updatedAt: z.date(),
});

export type Track = z.infer<typeof TrackSchema>;

// Domain Events
export const TrackAddedEvent = z.object({
  type: z.literal("TrackAdded"),
  trackId: z.string(),
  artistId: z.string(),
  source: z.string(),
  timestamp: z.date(),
});
```

### tRPC Router

```typescript
// lib/trpc/routers/library.router.ts

import { z } from "zod";
import { router, protectedProcedure } from "../trpc";
import { TrackSchema } from "@/lib/domain/entities/track";

export const libraryRouter = router({
  // Get all artists with counts
  getArtists: protectedProcedure
    .input(z.object({
      search: z.string().optional(),
      page: z.number().default(1),
      limit: z.number().default(50),
    }))
    .query(async ({ ctx, input }) => {
      return ctx.artistRepository.findMany({
        where: { name: { contains: input.search } },
        skip: (input.page - 1) * input.limit,
        take: input.limit,
        include: { _count: { select: { albums: true, tracks: true } } },
      });
    }),

  // Add track to library
  addTrack: protectedProcedure
    .input(z.object({
      spotifyUri: z.string().optional(),
      deezerId: z.string().optional(),
      autoDownload: z.boolean().default(false),
    }))
    .mutation(async ({ ctx, input }) => {
      // Business logic here
      const track = await ctx.libraryService.addTrack(input);
      
      // Event is published automatically via service
      return track;
    }),
});
```

### Prisma Schema

```prisma
// prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model Artist {
  id              String   @id @default(uuid())
  name            String
  source          String   // 'local', 'spotify', 'deezer', 'hybrid'
  ownershipState  String   @default("discovered")
  
  // Multi-provider IDs
  spotifyUri      String?  @unique
  deezerId        String?  @unique
  tidalId         String?  @unique
  musicbrainzId   String?
  
  // Metadata
  imageUrl        String?
  imagePath       String?
  genres          String[] @default([])
  
  // Relations
  albums          Album[]
  tracks          Track[]
  
  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt

  @@index([name])
  @@index([spotifyUri])
  @@index([deezerId])
}

model Track {
  id              String   @id @default(uuid())
  title           String
  
  // Relations
  artist          Artist   @relation(fields: [artistId], references: [id])
  artistId        String
  album           Album?   @relation(fields: [albumId], references: [id])
  albumId         String?
  
  // Multi-provider IDs
  isrc            String?
  spotifyUri      String?  @unique
  deezerId        String?  @unique
  
  // Ownership & Download
  ownershipState  String   @default("discovered")
  downloadState   String   @default("not_needed")
  localPath       String?
  
  // Metadata
  durationMs      Int?
  trackNumber     Int?
  genre           String?
  
  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt

  @@index([artistId])
  @@index([albumId])
  @@index([isrc])
}
```

### BullMQ Worker

```typescript
// workers/download.worker.ts

import { Worker, Queue } from "bullmq";
import { prisma } from "@/lib/infrastructure/prisma/client";
import { SlskdClient } from "@/lib/infrastructure/slskd/client";
import { EventBus } from "@/lib/domain/events";

const connection = { host: "localhost", port: 6379 };

// Queue für Downloads
export const downloadQueue = new Queue("downloads", { connection });

// Worker der Downloads verarbeitet
const worker = new Worker(
  "downloads",
  async (job) => {
    const { trackId, searchQuery, priority } = job.data;
    
    console.log(`Processing download for track ${trackId}`);
    
    // 1. Track aus DB holen
    const track = await prisma.track.findUnique({
      where: { id: trackId },
      include: { artist: true, album: true },
    });
    
    if (!track) throw new Error(`Track ${trackId} not found`);
    
    // 2. Download State updaten
    await prisma.track.update({
      where: { id: trackId },
      data: { downloadState: "downloading" },
    });
    
    try {
      // 3. Download via slskd
      const slskd = new SlskdClient();
      const result = await slskd.search(searchQuery);
      
      if (!result.files.length) {
        throw new Error("No results found");
      }
      
      const downloadPath = await slskd.download(result.files[0]);
      
      // 4. Success - update DB
      await prisma.track.update({
        where: { id: trackId },
        data: {
          downloadState: "downloaded",
          localPath: downloadPath,
        },
      });
      
      // 5. Publish Event
      await EventBus.publish({
        type: "DownloadCompleted",
        trackId,
        localPath: downloadPath,
        timestamp: new Date(),
      });
      
      return { success: true, path: downloadPath };
      
    } catch (error) {
      // Failure - update DB
      await prisma.track.update({
        where: { id: trackId },
        data: { downloadState: "failed" },
      });
      
      await EventBus.publish({
        type: "DownloadFailed",
        trackId,
        error: error.message,
        timestamp: new Date(),
      });
      
      throw error;
    }
  },
  {
    connection,
    concurrency: 5, // 5 parallel downloads
    limiter: {
      max: 10,
      duration: 1000, // Max 10 per second
    },
  }
);

worker.on("completed", (job) => {
  console.log(`Download completed: ${job.id}`);
});

worker.on("failed", (job, err) => {
  console.error(`Download failed: ${job?.id}`, err);
});
```

---

## ✅ Empfehlung

### Für SoulSpot empfehle ich: **TypeScript Rewrite mit Strangler Fig Pattern**

**Begründung:**

1. **SQLite-Probleme sind fundamental**
   - "database is locked" ist ein SQLite-Design-Problem
   - Python's GIL + async + SQLite = Pain
   - TypeScript + PostgreSQL = kein Problem

2. **Ein Stack statt zwei Welten**
   - HTMX + Jinja2 ist clever, aber limitiert
   - React/Next.js ermöglicht reichere UX
   - Keine Context-Switches mehr

3. **Type Safety End-to-End**
   - Prisma Types → tRPC → React = keine Lücken
   - Refactoring wird sicher
   - IDE-Support ist besser

4. **Performance**
   - Bun ist 4-5x schneller als Python
   - BullMQ ist production-ready
   - Keine GIL-Limitierung

5. **Zukunftssicherheit**
   - React Native möglich
   - Besserer Hiring Pool
   - Aktiver Ecosystem

---

## 🚀 Nächste Schritte

1. **Entscheidung treffen** - TypeScript Rewrite: Ja/Nein?
2. **Wenn Ja:**
   - Neues Repo `soulspot-ts` erstellen
   - Next.js 14 + Prisma Setup
   - Phase 1: UI Proxy zu bestehendem FastAPI
   - Phase 2: Feature-by-Feature Migration

Soll ich mit dem TypeScript-Setup beginnen?
