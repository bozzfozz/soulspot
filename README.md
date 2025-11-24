# SoulSpot

> 🎵 Musik von Spotify-Playlists automatisch über Soulseek herunterladen und sauber organisieren - für lokale Nutzung.

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/github/v/release/bozzfozz/soulspot?include_prereleases)](https://github.com/bozzfozz/soulspot/releases)

## Was ist SoulSpot?
SoulSpot verknüpft deine Spotify-Playlists mit dem Soulseek-Netzwerk. Die Anwendung lädt Titel automatisch herunter, reichert sie mit Metadaten an und legt sie strukturiert in deiner Musikbibliothek ab – komplett über eine moderne Weboberfläche für den lokalen Single-User Einsatz.

## Highlights für Anwender
- **Playlist-Synchronisation:** Importiere Spotify-Playlists per OAuth und halte sie aktuell.
- **Automatisierte Downloads:** Lädt Songs über den Soulseek-Dienst [slskd](https://github.com/slskd/slskd).
- **Bibliotheksverwaltung:** Verschiebt fertige Downloads automatisch in deine Musikbibliothek.
- **Metadaten & Cover:** Ergänzt Titel mit Informationen aus MusicBrainz und CoverArtArchive.
- **Moderne Web-App:** Bedienung per Browser mit intuitivem UI, Suchfiltern und Statusmeldungen.
- **Lokale Nutzung:** Optimiert für Single-User Setup ohne Cloud-Deployment.

## Systemvoraussetzungen
- Docker 20.10 oder neuer sowie Docker Compose 2.x.
- Ein Spotify-Entwicklerkonto (Client ID & Secret) für den OAuth-Zugriff.
- Ein Soulseek-Account bzw. slskd-API-Schlüssel.
- Genügend Speicherplatz für Downloads sowie zwei lokale Ordner: `mnt/downloads` und `mnt/music`.

## Schnellstart mit Docker
1. Repository klonen und wechseln:
   ```bash
   git clone https://github.com/bozzfozz/soulspot.git
   cd soulspot
   ```
2. Ordner für Downloads und Bibliothek anlegen:
   ```bash
   mkdir -p mnt/downloads mnt/music
   ```
3. Beispiel-Umgebungsdatei kopieren und bearbeiten:
   ```bash
   cp .env.example .env
   ```
   Trage mindestens folgende Werte ein:
   ```env
   SPOTIFY_CLIENT_ID=deine_spotify_client_id
   SPOTIFY_CLIENT_SECRET=dein_spotify_client_secret
   SLSKD_API_KEY=dein_slskd_api_key   # alternativ Benutzername/Passwort
   ```
4. Container starten:
   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```
5. Logs prüfen (optional):
   ```bash
   docker-compose -f docker/docker-compose.yml logs -f
   ```

Weitere Konfigurationsmöglichkeiten (z. B. Benutzer-IDs, Zeitzone, geheime Schlüssel) findest du im [Docker Setup Guide](docker/README.md).

## Zugriff nach dem Start
| Dienst | URL | Beschreibung |
| --- | --- | --- |
| Web-App | http://localhost:8765 | Hauptoberfläche zum Verwalten deiner Musik |
| API | http://localhost:8765/api | API-Endpoints der Anwendung |
| API-Dokumentation | http://localhost:8765/docs | Technische API-Ansicht (optional) |
| slskd Web UI | http://localhost:5030 | Verwaltung des Soulseek-Dienstes |

## Erste Schritte in der Anwendung
1. Öffne die Web-App und melde dich mit deinem Spotify-Konto an, um Playlists freizugeben.
2. Hinterlege deinen Soulseek-Zugang (API-Key oder Benutzername/Passwort).
3. Wähle die Playlists aus, die synchronisiert werden sollen.
4. Beobachte den Download-Status und prüfe deine `mnt/music`-Bibliothek.

Die automatische Musik-Importfunktion verschiebt fertig heruntergeladene Dateien in regelmäßigen Abständen aus `mnt/downloads` nach `mnt/music`. Unterstützte Formate sind u. a. MP3, FLAC, M4A und OGG.

## Dokumentation

### Für Anwender
- **[Setup Guide](docs/guides/user/setup-guide.md)** - Ausführliche Installations- und Konfigurationsanleitung
- **[User Guide](docs/guides/user/user-guide.md)** - Vollständige Anleitung für alle Funktionen
- **[Troubleshooting](docs/guides/user/troubleshooting-guide.md)** - Lösungen für häufige Probleme
- **[Docker Setup Guide](docker/README.md)** - Docker-spezifische Konfiguration

### Für Entwickler
- **[Architecture](docs/project/architecture.md)** - System-Architektur und Design
- **[Contributing](docs/project/contributing.md)** - Richtlinien für Beiträge
- **[Backend Roadmap](docs/development/backend-roadmap.md)** - Backend-Entwicklungsplan
- **[Frontend Roadmap](docs/development/frontend-roadmap.md)** - Frontend-Entwicklungsplan
- **[API Documentation](docs/api/)** - REST API Referenz

### Weitere Ressourcen
- **[CHANGELOG](docs/project/CHANGELOG.md)** - Versionshinweise und Änderungshistorie
- **[Complete Documentation](docs/)** - Vollständige Dokumentationsübersicht

## Lizenz
Die Lizenz ist noch in Arbeit und wird vor dem ersten Stable-Release veröffentlicht.

---
**Version:** 1.0 · **Status:** Active Development · **Verwendung:** Local Single-User · **Letzte Aktualisierung:** 2025-11-19
