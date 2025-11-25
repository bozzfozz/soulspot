# SoulSpot Feature Documentation

> **Version:** 1.0  
> **Last Updated:** 2025-11-25

---

## Overview

Diese Dokumentation beschreibt alle implementierten Features von SoulSpot. Jedes Feature ist mit einer eigenen Seite dokumentiert, die den Zweck, die Nutzung, API-Endpunkte und Troubleshooting-Tipps enthält.

---

## Feature-Übersicht

| Feature | Beschreibung | Status |
|---------|--------------|--------|
| [Playlist Management](./playlist-management.md) | Import, Sync und Export von Spotify-Playlists | ✅ Implementiert |
| [Download Management](./download-management.md) | Download-Queue, Priorisierung und Batch-Downloads | ✅ Implementiert |
| [Metadata Enrichment](./metadata-enrichment.md) | Multi-Source Metadaten-Anreicherung (Spotify, MusicBrainz, Last.fm) | ✅ Implementiert |
| [Automation & Watchlists](./automation-watchlists.md) | Artist-Watchlists, automatische Downloads, Filter-Regeln | ✅ Implementiert |
| [Followed Artists](./followed-artists.md) | Sync und Verwaltung gefolgter Spotify-Künstler | ✅ Implementiert |
| [Artists Roadmap](./artists-roadmap.md) | Spotify Artist API: Was nutzen wir? Was ist möglich? | 📋 Roadmap |
| [Spotify Albums Roadmap](./spotify-albums-roadmap.md) | Spotify Album API: Implementiert vs. Fehlend | 📋 Roadmap |
| [Library Management](./library-management.md) | Bibliotheks-Scan, Duplikaterkennung, defekte Dateien | ✅ Implementiert |
| [Authentication](./authentication.md) | Spotify OAuth, Session-Management, Multi-Device Support | ✅ Implementiert |
| [Track Management](./track-management.md) | Track-Suche, Download, Metadaten-Bearbeitung | ✅ Implementiert |
| [Settings](./settings.md) | Anwendungseinstellungen und Konfiguration | ✅ Implementiert |

---

## Quick Links

### Für Anwender
- [Playlist importieren](./playlist-management.md#playlist-importieren)
- [Downloads verwalten](./download-management.md#download-queue)
- [Artist folgen und Watchlist erstellen](./automation-watchlists.md#watchlist-erstellen)

### Für Entwickler
- [API-Endpunkte](../api/README.md)
- [Architektur](../project/architecture.md)

---

## Verwandte Dokumentation

- [User Guide](../guides/user/user-guide.md) - Vollständige Anleitung für alle Funktionen
- [API Documentation](../api/README.md) - REST API Referenz
- [Troubleshooting](../guides/user/troubleshooting-guide.md) - Problemlösungen
