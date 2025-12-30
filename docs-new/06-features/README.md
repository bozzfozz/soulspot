# SoulSpot Feature Documentation

**Category:** Features Index  
**Last Updated:** 2025-01-06  
**Version:** 2.0

---

## Overview

This documentation describes all implemented features of SoulSpot. Each feature has its own page documenting purpose, usage, API endpoints, and troubleshooting tips.

---

## Feature Overview

| Feature | Description | Status |
|---------|-------------|--------|
| [Authentication](./authentication.md) | OAuth integration for Spotify & Deezer, session management | ✅ Active |
| [Spotify Sync](./spotify-sync.md) | Auto-sync artists, playlists, liked songs, albums + image storage | ✅ Active |
| [Deezer Integration](./deezer-integration.md) | Deezer browse, search, and user features | ✅ Active |
| [Playlist Management](./playlist-management.md) | Import, sync, and export Spotify playlists | ✅ Active |
| [Followed Artists](./followed-artists.md) | Sync and manage followed Spotify artists | ✅ Active |
| [Automation Watchlists](./automation-watchlists.md) | Artist watchlists, automatic downloads, filter rules | ✅ Active |
| [Download Management](./download-management.md) | Download queue, prioritization, batch downloads | ✅ Active |
| [Auto-Import](./auto-import.md) | Automatic import downloads → music library | ✅ Active |
| [Track Management](./track-management.md) | Track search, download, metadata editing | ✅ Active |
| [Library Management](./library-management.md) | Library scan, duplicate detection, broken files | ✅ Active |
| [Metadata Enrichment](./metadata-enrichment.md) | Multi-source metadata enrichment (Spotify, MusicBrainz, Last.fm) | ✅ Active |
| [Local Library Enrichment](./local-library-enrichment.md) | Enrich local files with Spotify metadata | ✅ Active |
| [Album Completeness](./album-completeness.md) | Detect incomplete albums (multi-source: Spotify + MusicBrainz) | ✅ Active |
| [Compilation Analysis](./compilation-analysis.md) | Post-scan compilation detection via track artist diversity | ✅ Active |
| [Batch Operations](./batch-operations.md) | Generic batching for API calls (rate-limit optimization) | ✅ Active |
| [Notifications](./notifications.md) | Notification system (currently: stub / logging-only) | 🚧 Stub |
| [Settings](./settings.md) | Application settings and configuration | ✅ Active |
| [Download Manager Roadmap](./download-manager-roadmap.md) | Future download manager features | 🚧 Planned |

---

## Quick Links

### For Users
- [Set up Spotify Auto-Sync](./spotify-sync.md)
- [Import Playlists](./playlist-management.md)
- [Manage Downloads](./download-management.md)
- [Follow Artists and Create Watchlists](./automation-watchlists.md)

---

### For Developers
- [API Endpoints](../03-api-reference/)
- [Architecture](../02-architecture/)

---

## Related Documentation

- **[User Guide](../05-guides/user-guide.md)** - Complete guide for all functions
- **[API Documentation](../03-api-reference/)** - REST API reference
- **[Troubleshooting](../05-guides/troubleshooting-guide.md)** - Problem solutions

---

**Last Validated:** 2025-01-06  
**Status:** ✅ Active Documentation
