# Download Manager Features Roadmap

> **Zuletzt aktualisiert:** 2025-01-13
> **Status:** Research Complete - Ready for Implementation
> **Priorität:** High (Core Feature)

## 📋 Übersicht

Dieses Dokument beschreibt alle Features, die ein moderner Download Manager haben kann.
Basierend auf Recherche von: Lidarr, SABnzbd, qBittorrent, Free Download Manager, JDownloader.

---

## 1. Queue Management (Warteschlangen-Verwaltung)

### 1.1 Priority System ✅ IMPLEMENTIERT
- Downloads nach Priorität sortieren (1-50, niedrigere Zahl = höher)
- **SoulSpot Status:** `Download.priority` Feld existiert
- **Code:** `src/soulspot/domain/entities/download.py`

### 1.2 Pause/Resume ⚠️ TEILWEISE
- Einzelne Downloads pausieren und später fortsetzen
- **SoulSpot Status:** Cancel existiert, Resume fehlt
- **TODO:** 
  - [ ] Status `PAUSED` hinzufügen
  - [ ] Resume-Logik implementieren
  - [ ] UI Button hinzufügen

### 1.3 Reorder Queue ❌ NICHT IMPLEMENTIERT
- Drag & Drop um Reihenfolge zu ändern
- **Implementierung:**
  - [ ] Frontend: Sortable.js oder SortableJS
  - [ ] Backend: `PATCH /api/downloads/reorder` Endpoint
  - [ ] DB: `queue_position` Feld hinzufügen

### 1.4 Batch Operations ❌ NICHT IMPLEMENTIERT
- Mehrere Downloads gleichzeitig:
  - Pausieren
  - Fortsetzen
  - Abbrechen
  - Priorität ändern
- **Implementierung:**
  - [ ] Checkbox Selection im UI
  - [ ] `POST /api/downloads/batch` Endpoint
  - [ ] Actions: pause_all, resume_all, cancel_selected, set_priority

### 1.5 Queue Limits ❌ NICHT IMPLEMENTIERT
- Max. gleichzeitige Downloads limitieren
- Separate Limits pro Provider
- **Implementierung:**
  - [ ] Setting: `download.max_concurrent` (Default: 3)
  - [ ] Setting: `download.max_concurrent_per_provider`
  - [ ] QueueDispatcherWorker anpassen

### 1.6 Categories/Tags ❌ NICHT IMPLEMENTIERT
- Downloads in Kategorien gruppieren (z.B. "Album", "Single", "Compilation")
- **Implementierung:**
  - [ ] `Download.category` Feld
  - [ ] Filter im UI

---

## 2. Scheduling (Zeitplanung)

### 2.1 Time-based Start ❌ NICHT IMPLEMENTIERT
- Downloads zu bestimmter Uhrzeit starten
- **Implementierung:**
  - [ ] `Download.scheduled_start` DateTime Feld
  - [ ] Worker prüft scheduled_start vor Queue
  - [ ] UI: DateTimePicker für "Start at..."

### 2.2 Time-based Stop ❌ NICHT IMPLEMENTIERT
- Downloads zu bestimmter Uhrzeit stoppen
- **Implementierung:**
  - [ ] `Download.scheduled_stop` DateTime Feld
  - [ ] StatusSyncWorker prüft und pausiert

### 2.3 Bandwidth Schedule ❌ NICHT IMPLEMENTIERT
- Bandbreite je nach Tageszeit anpassen
- **Beispiel:**
  ```yaml
  schedule:
    - time: "09:00-18:00"
      speed_limit: 500KB/s  # Arbeitszeit - langsam
    - time: "18:00-09:00"
      speed_limit: unlimited  # Nachts - volle Geschwindigkeit
  ```
- **Implementierung:**
  - [ ] `app_settings` Tabelle: `download.schedule`
  - [ ] BandwidthSchedulerWorker
  - [ ] slskd API für Speed Limit (falls unterstützt)

### 2.4 Calendar View ❌ NICHT IMPLEMENTIERT
- Kalender-Ansicht für geplante Downloads
- **Implementierung:**
  - [ ] FullCalendar.js Integration
  - [ ] `GET /api/downloads/calendar` Endpoint

---

## 3. Failed Download Handling (Lidarr-Style) 🔥 HIGH PRIORITY

### 3.1 Auto-Retry ❌ NICHT IMPLEMENTIERT
- Bei Fehler automatisch nochmal versuchen
- **Implementierung:**
  - [ ] `Download.retry_count` Feld
  - [ ] `Download.max_retries` Setting (Default: 3)
  - [ ] `Download.last_error` Feld
  - [ ] StatusSyncWorker: Bei FAILED → prüfe retry_count → wenn < max_retries → zurück auf WAITING

### 3.2 Exponential Backoff ❌ NICHT IMPLEMENTIERT
- Wartezeit zwischen Retries erhöhen: 1min → 5min → 15min → 1h
- **Implementierung:**
  - [ ] `Download.next_retry_at` DateTime Feld
  - [ ] Backoff-Formel: `delay = base_delay * (2 ** retry_count)`
  - [ ] QueueDispatcherWorker prüft next_retry_at

### 3.3 Alternative Source Search ❌ NICHT IMPLEMENTIERT
- Bei Fehler andere Quelle auf slskd suchen
- **Implementierung:**
  - [ ] `Download.failed_sources` JSON Liste
  - [ ] SearchAndDownloadUseCase: Exclude failed_sources
  - [ ] Blocklist für bekannt schlechte Quellen

### 3.4 Blocklist ❌ NICHT IMPLEMENTIERT
- Fehlgeschlagene Quellen blocken (User/File)
- **Implementierung:**
  - [ ] `download_blocklist` Tabelle: user, filename, reason, created_at
  - [ ] slskd Search: Filter blocklisted users

### 3.5 Failed History ❌ NICHT IMPLEMENTIERT
- Übersicht aller Fehler mit Details
- **Implementierung:**
  - [ ] `download_errors` Tabelle: download_id, error_type, message, stack_trace, timestamp
  - [ ] `GET /api/downloads/errors` Endpoint
  - [ ] UI: Error History Page

---

## 4. Quality Management (Lidarr-Style) 🔥 HIGH PRIORITY

### 4.1 Quality Profiles ❌ NICHT IMPLEMENTIERT
- Profile definieren: "FLAC First", "320kbps Minimum", etc.
- **Beispiel-Profile:**
  ```yaml
  profiles:
    - name: "Audiophile"
      order: [FLAC, ALAC, WAV, 320kbps]
      min_quality: 320kbps
      max_size: 100MB
    
    - name: "Balanced"
      order: [320kbps, FLAC, 256kbps]
      min_quality: 256kbps
      max_size: 50MB
    
    - name: "Space Saver"
      order: [256kbps, 192kbps]
      max_size: 20MB
  ```
- **Implementierung:**
  - [ ] `quality_profiles` Tabelle: name, settings_json
  - [ ] `Download.quality_profile_id` FK
  - [ ] SearchAndDownloadUseCase: Filter nach Profile

### 4.2 Auto-Upgrade ❌ NICHT IMPLEMENTIERT
- Bessere Qualität automatisch ersetzen
- **Implementierung:**
  - [ ] Setting: `download.auto_upgrade` (Default: false)
  - [ ] UpgradeCheckerWorker: Vergleicht Track.quality mit Profile
  - [ ] Wenn bessere Qualität verfügbar → Queue neuen Download

### 4.3 File Size Limits ❌ NICHT IMPLEMENTIERT
- Min/Max Dateigröße pro Track/Album
- **Implementierung:**
  - [ ] In Quality Profile integriert
  - [ ] SearchAndDownloadUseCase: Filter nach Size

---

## 5. Bandwidth/Traffic Control

### 5.1 Speed Limit ❌ NICHT IMPLEMENTIERT
- Max Download-Geschwindigkeit global
- **Hinweis:** Muss in slskd konfiguriert werden, nicht SoulSpot
- **Alternative:** SoulSpot könnte Downloads throttlen (weniger parallel)

### 5.2 Traffic Counter ❌ NICHT IMPLEMENTIERT
- Gesamt-Traffic anzeigen (heute, Woche, Monat, gesamt)
- **Implementierung:**
  - [ ] `Download.bytes_downloaded` speichern
  - [ ] `GET /api/downloads/stats/traffic` Endpoint
  - [ ] UI Widget im Dashboard

---

## 6. Post-Processing (Nach dem Download) 🔥 HIGH PRIORITY

### 6.1 Auto-Move ⚠️ TEILWEISE
- Dateien automatisch verschieben
- **SoulSpot Status:** `Track.file_path` wird gesetzt, aber kein Move
- **TODO:**
  - [ ] Post-Processing Worker
  - [ ] Move nach Schema: `{artist}/{album}/{track}.flac`
  - [ ] Setting: `download.destination_folder`

### 6.2 Auto-Rename ❌ NICHT IMPLEMENTIERT
- Dateien nach Schema umbenennen
- **Beispiel-Schema:** `{artist} - {album} - {track_number} - {title}.{ext}`
- **Implementierung:**
  - [ ] Setting: `download.rename_pattern`
  - [ ] PostProcessingWorker: Rename nach Pattern

### 6.3 Metadata Tagging ❌ NICHT IMPLEMENTIERT
- ID3 Tags automatisch setzen (Artist, Album, Title, Year, Genre, Cover)
- **Implementierung:**
  - [ ] `mutagen` Library für ID3 Tagging
  - [ ] MetadataTaggerService
  - [ ] Tags aus Track Entity übernehmen

### 6.4 Album Art Embed ❌ NICHT IMPLEMENTIERT
- Cover Art in Datei einbetten
- **Implementierung:**
  - [ ] CoverArtService: Download von CoverArtArchive/Spotify
  - [ ] mutagen: Cover in ID3 einbetten
  - [ ] Optional: Cover als folder.jpg speichern

### 6.5 Notifications ❌ NICHT IMPLEMENTIERT
- Benachrichtigung bei Fertigstellung
- **Optionen:**
  - Toast (In-App)
  - Email
  - Webhook (Discord, Slack, Pushover)
  - Desktop Notification
- **Implementierung:**
  - [ ] NotificationService
  - [ ] `app_settings`: Notification Provider konfigurieren
  - [ ] Events: download_complete, album_complete, error

### 6.6 Custom Scripts ❌ NICHT IMPLEMENTIERT
- Post-Download Scripts ausführen
- **Implementierung:**
  - [ ] Setting: `download.post_script_path`
  - [ ] Subprocess mit Parametern: track_path, artist, album, etc.

---

## 7. Import/Monitoring

### 7.1 Folder Monitoring ❌ NICHT IMPLEMENTIERT
- Ordner auf neue Dateien überwachen (Hot Folder)
- **Implementierung:**
  - [ ] watchdog Library
  - [ ] FolderMonitorWorker
  - [ ] Bei neuer Datei → Import in Library

### 7.2 Import Lists ✅ IMPLEMENTIERT
- Spotify Playlists automatisch importieren
- **SoulSpot Status:** Spotify Sync Worker existiert

### 7.3 Missing Albums Detection ⚠️ TEILWEISE
- Fehlende Alben erkennen
- **SoulSpot Status:** CheckAlbumCompletenessUseCase existiert
- **TODO:** 
  - [ ] Automatische Erkennung für alle Artists
  - [ ] UI: "Missing Albums" Tab

### 7.4 Automatic Download ❌ NICHT IMPLEMENTIERT
- Neue Releases automatisch downloaden (Watchlist)
- **SoulSpot Status:** Watchlist-Tabelle existiert (bb16770eeg26 Migration)
- **TODO:**
  - [ ] NewReleaseMonitorWorker
  - [ ] Bei neuem Album in Watchlist → Auto-Download

---

## 8. UI/UX Features

### 8.1 Live Progress ✅ IMPLEMENTIERT
- Echtzeit-Fortschritt via SSE
- **SoulSpot Status:** `/api/downloads/manager/events` existiert

### 8.2 Speed Graph ❌ NICHT IMPLEMENTIERT
- Geschwindigkeit als Chart (letzte 24h)
- **Implementierung:**
  - [ ] Chart.js Integration
  - [ ] `download_speed_history` Tabelle: timestamp, speed
  - [ ] SpeedHistoryWorker: Speichert alle 10s

### 8.3 ETA ✅ IMPLEMENTIERT
- Geschätzte Restzeit
- **SoulSpot Status:** DownloadProgress.eta existiert

### 8.4 Toast Notifications ⚠️ TEILWEISE
- In-App Benachrichtigungen
- **TODO:** Einheitliches Toast-System implementieren

### 8.5 Keyboard Shortcuts ❌ NICHT IMPLEMENTIERT
- Tastaturkürzel für schnelle Aktionen
- **Beispiele:**
  - `P` = Pause/Resume
  - `Delete` = Cancel
  - `1-9` = Set Priority
- **Implementierung:**
  - [ ] Hotkeys.js Library
  - [ ] Keyboard Shortcuts Help Modal

---

## 9. History & Statistics

### 9.1 Download History ✅ IMPLEMENTIERT
- Verlauf aller Downloads
- **SoulSpot Status:** Downloads in DB mit Timestamps

### 9.2 Statistics Dashboard ⚠️ TEILWEISE
- Statistiken (total GB, count, etc.)
- **TODO:**
  - [ ] `GET /api/downloads/stats` erweitern
  - [ ] Total downloaded (count, size)
  - [ ] By status, by provider, by quality

### 9.3 Graphs/Charts ❌ NICHT IMPLEMENTIERT
- Downloads pro Tag/Woche als Chart
- **Implementierung:**
  - [ ] Chart.js
  - [ ] `GET /api/downloads/stats/history?period=week`

### 9.4 Export History ❌ NICHT IMPLEMENTIERT
- CSV/JSON Export
- **Implementierung:**
  - [ ] `GET /api/downloads/export?format=csv`

---

## 10. Advanced Features

### 10.1 Multiple Providers ⚠️ NUR SLSKD
- Unterstützung für mehrere Download-Provider
- **SoulSpot Status:** Provider-Registry existiert, nur slskd implementiert
- **Future Providers:**
  - [ ] Usenet (SABnzbd/NZBGet Integration)
  - [ ] Torrent (qBittorrent Integration)
  - [ ] Direct HTTP Downloads

### 10.2 Provider Fallback ❌ NICHT IMPLEMENTIERT
- Bei Fehler automatisch anderen Provider nutzen
- **Implementierung:**
  - [ ] Provider Priority in Settings
  - [ ] SearchAndDownloadUseCase: Try providers in order

### 10.3 Remote Control ✅ IMPLEMENTIERT
- API für externe Apps
- **SoulSpot Status:** REST API existiert

### 10.4 Webhooks ❌ NICHT IMPLEMENTIERT
- Events an externe Services senden
- **Beispiel-Events:**
  - download.started
  - download.completed
  - download.failed
  - album.completed
- **Implementierung:**
  - [ ] WebhookService
  - [ ] `webhooks` Tabelle: url, events[], secret
  - [ ] POST mit Payload + HMAC Signature

### 10.5 RSS Feed Monitoring ❌ NICHT IMPLEMENTIERT
- RSS Feeds für neue Releases überwachen
- **Implementierung:**
  - [ ] feedparser Library
  - [ ] RSSMonitorWorker
  - [ ] `rss_feeds` Tabelle: url, artist_filter, last_check

---

## 🎯 Implementation Roadmap

### Phase 1: Core Improvements (Sprint 1-2)
1. **Auto-Retry mit Exponential Backoff** 
2. **Quality Profiles (Basic)**
3. **Batch Operations**
4. **Queue Limits**
5. **Failed History Page**

### Phase 2: Post-Processing (Sprint 3-4)
6. **Metadata Tagging (ID3)**
7. **Album Art Embed**
8. **Auto-Move & Rename**
9. **Notifications (Toast + Webhook)**

### Phase 3: Advanced (Sprint 5-6)
10. **Scheduler (Time-based)**
11. **Statistics Dashboard**
12. **Speed Graphs**
13. **Alternative Source Search**

### Phase 4: Multi-Provider (Future)
14. **Usenet Provider**
15. **Provider Fallback**
16. **RSS Monitoring**

---

## 📚 Referenzen

- [Lidarr Documentation](https://wiki.servarr.com/lidarr)
- [SABnzbd Wiki](https://sabnzbd.org/wiki/)
- [qBittorrent WebUI API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1))
- [Free Download Manager](https://www.freedownloadmanager.org/features.htm)
- [JDownloader](https://jdownloader.org/)

---

## 🔗 Verwandte Dokumente

- [Download Manager Implementation](../implementation/download-manager.md)
- [Architecture Overview](../architecture/README.md)
- [API Documentation](../api/downloads.md)
