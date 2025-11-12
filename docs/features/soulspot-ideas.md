# SoulSpot — Gesamte Ideensammlung (konsolidiert & sortiert)

Status: Entwurf  
Erstellt: 2025-11-10  
Autor: Konsolidierte Ideensammlung (bozzfozz + Copilot)

Hinweis: Nur Ideensammlung — keine Architektur-Entscheidungen oder Code.

---

Inhalt
- 1. Thematische Übersicht (kompakt)
- 2. Priorisiertes Backlog (Must / Should / Could) mit Aufwandsschätzung
- 3. Konkrete nächste Schritte / Sprint-Vorschlag
- 4. Metriken, Policies & Fragen zur Entscheidung
- 5. Vorschlag für "good first issue" / "help wanted" Kennzeichnung

---

1) Thematisch sortierte Ideensammlung (kompakt)
- Quellen & Integrationen
  - Spotify: OAuth PKCE, Playlists, Liked Songs, Artists, Suche, Buttons: „Queue Album/Playlist/Artist Download"
  - Soulseek: slskd-API (Search, Download, Status, Auth), Anzeige Quelle/Username/Speed/File-Infos
  - Externe Metadaten & Artwork: MusicBrainz, Last.fm, CoverArtArchive, Fanart.tv
  - Lyrics: LRClib, Musixmatch, Genius
  - Media-Server: Plex (Rescan, Mapping)
  - Sonstiges: Last.fm Scrobbling, Telegram/Discord-Bot, Smart-Home/Webhooks

> **Hinweis:** Jellyfin und Navidrome Integration entfernt (lokal-only Betrieb).

- Suche & Matching
  - Kombinierte Suche (Spotify + Soulseek) mit klarer Quellenkennzeichnung
  - Smart-Matching: Score-System auf Basis Titel/Artist/Dauer/Bitrate/Größe
  - Optional: Audiofingerprint (AcoustID/Chromaprint) für robustes Matching & Duplikaterkennung
  - Filter & Policies: Min-Bitrate, Format-Filter (FLAC/MP3), Ausschlusskeywords (Live/Remix)
  - Missing-Song-Discovery (Playlist ↔ lokal), Export (CSV/JSON)
  - Discography / Similar-Artist-Discovery & „Download entire discography"

- Download- & Queue-Management
  - Zentrale Queue (queued / running / completed / failed) mit Progress UI
  - Parallele Downloads (konfigurierbar, z. B. 1–3 gleichzeitig)
  - Job-Priorisierung (Drag & Drop / Priority-Feld), Pause/Resume
  - Batch-Downloads: TXT/CSV/JSON/M3U/Spotify-Export
  - Retry/Resume, Resume nach Neustart, Scheduler / Nachtmodus (CRON)
  - Download-Historie & Audit-Log

- Soulseek-Automatisierung („arr"-Style)
  - Workflow: Detect → Search → Match → Download → Tag → Sort → Sync
  - Library-Scanner: Hash/Tag/Struktur-Scan, Erkennung defekter Files
  - Watchlists: Artists/Labels/Genres → Auto-Download bei Verfügbarkeit
  - Whitelist/Blacklist und Dry-Run-Optionen

- Post-Processing / Pipeline
  - Schritte: temp-download → Auto-Tagging → Artwork → Lyrics → Audioanalyse (BPM/Loudness) → Rename → Move → Trigger Rescan → Logging
  - Ordnerstruktur-Vorschläge (Downloads, Sorting, New Artists, Unknown Album, Final Library)
  - Optional: Auto-Convert (Archiv ↔ Mobil), Auto-Cleanup

- Metadaten & Tagging
  - Multi-Source-Tagging & Merge-Logik (Spotify, MusicBrainz, Last.fm)
  - Authority-Hierarchie (manual > Spotify > MusicBrainz > Last.fm > fallback)
  - Tag-Merging, Schreibweisen-Normalisierung (feat./ft.), Batch-Fixer UI (Dry-Run + Commit)
  - Artwork: mehrere Quellen, mehrere Auflösungen, embed + cover.jpg
  - Metadata-Cache (SQLite), Hash-/Fingerprint-Keying

- Bewertungen / Nutzersignale & Ratings
  - Ratings-Sync (Plex ↔ Datei/DB), Mapping & Konfliktregeln
  - Nutzersignale (Playcount, Skips, Likes) für Auto-Playlists und Priorisierung

> **Hinweis:** Jellyfin/Navidrome Ratings-Sync entfernt.

- Library-Management & Self-Healing
  - Duplikaterkennung (hash + fingerprint), „Smart-Unify"
  - Album-Vollständigkeit & Discography-Completion
  - Multi-Library (NAS, lokal), Preferred-Version-Marking
  - Self-Healing: Auto-Re-Download, Fix Library (Tags, Cover, Struktur)
  - History / Change-Log

- UI / UX
  - Grund-UI: Tabs Search / Playlists / Downloads / Settings (+ Library, Automation, Activity)
  - Visualisierung: per-download progress, global progress, status icons, missing indicators
  - Spezialansichten: Automation Center, Metadata Manager, Rating Sync, Timeline
  - Extras: Browser-Extension „Add to SoulSpot", System-Tray, Minimal/Terminal-View

- Playlists & Cross-Provider-Sync
  - Playlist-Sync zwischen Spotify und Plex
  - Playlist-Versionierung / Snapshots / Rollback
  - Export/Import & Playlist-Rebuilder mit Matching

> **Hinweis:** Jellyfin/Navidrome Playlist-Sync entfernt.

- Konfiguration, Sicherheit & Legal
  - YAML/JSON-Konfiguration, Trennung Pfade/Secrets/Policies
  - Opt-in Legal-Hinweis vor automatischen Downloads, Legal Mode
  - Auth: OAuth / API-Key, IP-Restriktion optional, Audit-Logs

> **Hinweis:** Multi-User / Rechteverwaltung entfernt (Single-User lokal-only).

- API, Erweiterbarkeit & Automation
  - REST API + WebSocket für live updates
  - Plugin-System für neue Quellen / Tagging-Engines / Automationsregeln
  - Webhooks & Events, CLI für Headless-Betrieb

- KI & Zukunft
  - KI-Matching (audio-basiert), KI-Tagging (Genre/Mood/Language)
  - Adaptive Automation (lernt aus Nutzerentscheidungen)
  - Forecast for new releases, Audio-Repair, Smart-Home-Integration, Notifications

- Komfort-Features
  - Auto-Mix, Mood-/Genre-Cluster, Track-Notes, Download-Budget, Multi-Device-Sync

---

2) Priorisiertes Backlog (Must / Should / Could) mit Aufwandsschätzung  
Hinweis zur Schätzung: klein = wenige Tage, mittel = 1–2 Wochen, groß = mehrere Wochen / komplex.  
(Anmerkung: die mit [good first issue] und [help wanted] markierten Einträge sind Vorschläge für Issues.)

Must (Phase 1 — Grundplattform)
1. Spotify OAuth + Playlist/Track Import (klein) [good first issue]  
2. slskd-Integration: Search / Start / Monitor / Cancel (klein–mittel) [good first issue]  
3. Download-Queue mit parallel-limit, Status & Progress (klein) [good first issue]  
4. SQLite DB für Jobs + Metadaten-Cache (klein) [good first issue]  
5. Basic Auto-Tagging (Spotify + MusicBrainz lookup) (mittel) [help wanted]  
6. Basic Cover-Download + Embed (mittel) [good first issue]  
7. Grund-UI (HTMX): Tabs Search / Playlists / Downloads / Settings (mittel) [good first issue]  
8. Audit-/Download-Log & Legal-Opt-in (klein) [good first issue]  
9. Retry/Resume-Logic beim Download (mittel) [help wanted]  
10. Safe tag writes (mutagen, atomic replace) (klein) [good first issue]

Should (Phase 2 — Automatisierung + Library)
1. Missing-Song-Discovery & Library Scanner (mittel) [help wanted]  
2. Artist-/Album-Watcher + Scheduler (CRON) (mittel) [help wanted]  
3. Batch-Download (CSV/JSON/M3U) + Batch-UI (mittel) [help wanted]  
4. Metadata enrichment Last.fm + merge-logic (mittel) [help wanted]  
5. Ratings-Sync (Plex ↔ Files/DB) (mittel) [help wanted]  
6. Smart-Match heuristics + fuzzy matching (mittel) [help wanted]  
7. Auto-Cleanup & Smart-Delete policies (klein–mittel) [good first issue]  
8. Multi-folder library support (mittel) [help wanted]  
9. Webhooks & Automation API (klein–mittel) [good first issue]

Could (Phase 3 — Intelligenz & Ökosystem)
1. AcoustID / Audio-fingerprint matching (groß) [help wanted]  
2. KI-based matching & tag-repair (groß)  
3. PWA / Mobile companion app (groß) [help wanted]  
4. Plugin system for additional sources (groß) [help wanted]  
5. Observability + CI/CD + Helm/K8s (mittel–groß) [help wanted]  
6. Full cross-provider sync (groß)  
7. Audio-repair & anomaly detection (groß)

---

3) Konkrete nächste Schritte / Sprint-Vorschlag (empfohlen)
Kurzfristig (1–2 Sprints)
- Sprint 1 (Setup & Integrationen)
  - Spotify OAuth + Playlist import, slskd client (Search/Download start/status)
  - DB-Modelle (jobs, cache), einfache Queue-API
  - Akzeptanzkriterien: OAuth flow manuell testbar, slskd search & start returns job id, jobs persisted in SQLite

- Sprint 2 (Tagging & UI)
  - MusicBrainz client + cache; mutagen-based tag write (safe replace)
  - Cover download & embed
  - Grund-UI: Search / Downloads / Playlists (HTMX)
  - Akzeptanzkriterien: single-track enrichment dry-run + commit, UI zeigt job status + progress

Mittelfristig (Phase 2)
- Missing-song-discovery, batch-downloads, ratings-sync connector (Plex), Last.fm enrichers, batch-fixer UI

Langfristig (Phase 3)
- AcoustID, KI-Features, plugin-architecture

> **Hinweis:** Multi-User support und Production Infra entfernt (lokal-only).

---

4) Metriken, Policies & offene Fragen
Wichtige Metriken:
- Job throughput, avg enrichment time, cache hit-rate, external API calls/sec, failed-job ratio

Policies / Defaults (vorschlagen):
- MusicBrainz rate-limit: 1 req/sec (beachten + worker-queue)  
- Default merge-priorität: manual > MusicBrainz > Spotify > fallback  
- Default parallel downloads: 2 (configurable)  
- Retry policy: 3 retries with exponential backoff

Offene Design-/Policy-Fragen:
- Ratings-Sync initial: one-way (Plex→SoulSpot) oder direkt two-way?  
- AcoustID: Phase2 empfohlen oder später?  
- Merge-Priorität: Soll „Spotify" höher priorisiert werden als MusicBrainz in einigen Feldern (z. B. popularity)?  
- Legal: Formulierung der Opt-in / welche Funktionen sollten per Legal Mode eingeschränkt sein?

---

5) Vorschlag für "good first issue" & "help wanted" Kennzeichnung  
(Die folgenden Issues sind Vorschläge für sofort anlegbare Issues — Titel + kurze Beschreibung.)

Empfohlene "good first issue" (klein, klar umrissen)
- issue: spotify-oauth-setup
  - Kurz: Implementiere OAuth PKCE flow skeleton + redirect endpoint; dokumentiere manuelle Testschritte.
- issue: slskd-basic-client
  - Kurz: Minimaler slskd client: Suche anfragen, einfache Start-Download-API, stub responses.
- issue: jobs-sqlite-models
  - Kurz: Erstelle SQLite-Tabellen / SQLAlchemy-Modelle für Jobs + cache; simple CRUD tests.
- issue: queue-basic-api
  - Kurz: Endpoints: POST /jobs (enqueue), GET /jobs/{id}, GET /jobs (list). Persistenz in SQLite.
- issue: safe-tag-writes
  - Kurz: Implementiere sichere Tag-Write-Utility (mutagen) mit atomic temp-write + replace.
- issue: cover-download-basic
  - Kurz: Endpoint + worker task, lade CoverArtArchive-Cover und speichere cover.jpg im Album-Ordner.

Empfohlene "help wanted" (mittel, netter Einstieg für Contributor)
- issue: musicbrainz-enricher
  - Kurz: MusicBrainz client + cache integration + unit tests (rate-limit handling).
- issue: retry-resume-download
  - Kurz: Implementiere retry + resume behavior im Download-Worker (exponential backoff).
- issue: batch-download-ui
  - Kurz: HTMX fragment zur Anzeige von Batch-Job-Preview / start-action.
- issue: ratings-sync-connector
  - Kurz: Connector-Skeleton für Plex API → sync ratings to local DB (dry-run).
- issue: missing-song-discovery
  - Kurz: Library scanner skeleton: vergleiche playlist entries vs. local DB, report missing.

Wie ich die Kennzeichnung vornehmen würde
- Wenn du möchtest, kann ich diese Issue-Meta direkt als Draft-Issues vorbereiten (github-draft-issue) — je 1 JSON pro Issue.  
- Alternativ lege ich die Datei hier final ab (wenn du zufrieden bist) und danach erstelle ich die Issues.

---

6) Nächste Schritte (was du tun musst / ich für dich tun kann)
- Wenn ok: bestätige, ob ich die Datei ins Repo committen soll (Draft PR) oder ob du noch Änderungen willst.  
- Wenn du möchtest, kann ich anschließend die vorgeschlagenen Issues als Draft-Issues erzeugen (nützlich für Contributors).

Wenn du "OK, commit" gibst, erstelle ich die Draft-PR mit dieser Datei. Wenn du „Issues" willst, sag wie viele Issues ich vorbereiten soll (z. B. 6 good-first + 5 help-wanted).  
