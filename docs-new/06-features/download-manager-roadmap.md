# Download Manager Features

**Category:** Features (Roadmap)  
**Status:** 🚧 Research Complete - Ready for Implementation  
**Priority:** High (Core Feature)  
**Last Updated:** 2025-01-13

---

## Overview

This document describes all features a modern download manager can have. Based on research from: Lidarr, SABnzbd, qBittorrent, Free Download Manager, JDownloader.

---

## 1. Queue Management

### Priority System ✅ IMPLEMENTED
- Sort downloads by priority (1-50, lower = higher)
- **SoulSpot Status:** `Download.priority` field exists
- **Code:** `src/soulspot/domain/entities/download.py`

---

### Pause/Resume ⚠️ PARTIAL
- Pause individual downloads and resume later
- **SoulSpot Status:** Cancel exists, Resume missing
- **TODO:**
  - [ ] Add `PAUSED` status
  - [ ] Implement resume logic
  - [ ] Add UI button

---

### Reorder Queue ❌ NOT IMPLEMENTED
- Drag & drop to change order
- **Implementation:**
  - [ ] Frontend: Sortable.js
  - [ ] Backend: `PATCH /api/downloads/reorder` endpoint
  - [ ] DB: `queue_position` field

---

### Batch Operations ❌ NOT IMPLEMENTED
- Operate on multiple downloads:
  - Pause
  - Resume
  - Cancel
  - Change priority
- **Implementation:**
  - [ ] Checkbox selection in UI
  - [ ] `POST /api/downloads/batch` endpoint
  - [ ] Actions: pause_all, resume_all, cancel_selected, set_priority

---

### Queue Limits ❌ NOT IMPLEMENTED
- Limit max concurrent downloads
- Separate limits per provider
- **Implementation:**
  - [ ] Setting: `download.max_concurrent` (Default: 3)
  - [ ] Setting: `download.max_concurrent_per_provider`
  - [ ] Adjust QueueDispatcherWorker

---

### Categories/Tags ❌ NOT IMPLEMENTED
- Group downloads in categories (e.g. "Album", "Single", "Compilation")
- **Implementation:**
  - [ ] `Download.category` field
  - [ ] Filter in UI

---

## 2. Scheduling

### Time-based Start ❌ NOT IMPLEMENTED
- Start downloads at specific time
- **Implementation:**
  - [ ] `Download.scheduled_start` DateTime field
  - [ ] Worker checks scheduled_start before queue
  - [ ] UI: DateTimePicker for "Start at..."

---

### Time-based Stop ❌ NOT IMPLEMENTED
- Stop downloads at specific time
- **Implementation:**
  - [ ] `Download.scheduled_stop` DateTime field
  - [ ] StatusSyncWorker checks and pauses

---

### Bandwidth Schedule ❌ NOT IMPLEMENTED
- Adjust bandwidth by time of day
- **Example:**
  ```yaml
  schedule:
    - time: "09:00-18:00"
      speed_limit: 500KB/s  # Work hours - slow
    - time: "18:00-09:00"
      speed_limit: unlimited  # Night - full speed
  ```
- **Implementation:**
  - [ ] `app_settings` table: `download.schedule`
  - [ ] BandwidthSchedulerWorker
  - [ ] slskd API for speed limit (if supported)

---

### Calendar View ❌ NOT IMPLEMENTED
- Calendar view for scheduled downloads
- **Implementation:**
  - [ ] FullCalendar.js integration
  - [ ] `GET /api/downloads/calendar` endpoint

---

## 3. Failed Download Handling (Lidarr-Style) 🔥 HIGH PRIORITY

### Auto-Retry ❌ NOT IMPLEMENTED
- Automatically retry on failure
- **Implementation:**
  - [ ] `Download.retry_count` field
  - [ ] `Download.max_retries` setting (Default: 3)
  - [ ] `Download.last_error` field
  - [ ] StatusSyncWorker: On FAILED → check retry_count → if < max_retries → back to WAITING

---

### Exponential Backoff ❌ NOT IMPLEMENTED
- Increase wait time between retries: 1min → 5min → 15min → 1h
- **Implementation:**
  - [ ] `Download.next_retry_at` DateTime field
  - [ ] Backoff formula: `delay = base_delay * (2 ** retry_count)`
  - [ ] QueueDispatcherWorker checks next_retry_at

---

### Alternative Source Search ❌ NOT IMPLEMENTED
- Search different source on slskd on failure
- **Implementation:**
  - [ ] `Download.failed_sources` JSON list
  - [ ] SearchAndDownloadUseCase: Exclude failed_sources
  - [ ] Blocklist for known bad sources

---

### Blocklist ❌ NOT IMPLEMENTED
- Block failed sources (User/File)
- **Implementation:**
  - [ ] `download_blocklist` table: user, filename, reason, created_at
  - [ ] slskd Search: Filter blocklisted users

---

### Failed History ❌ NOT IMPLEMENTED
- Overview of all failures with details
- **Implementation:**
  - [ ] `download_errors` table: download_id, error_type, message, stack_trace, timestamp
  - [ ] `GET /api/downloads/errors` endpoint
  - [ ] UI: Error History Page

---

## 4. Quality Management (Lidarr-Style) 🔥 HIGH PRIORITY

### Quality Profiles ❌ NOT IMPLEMENTED
- Define profiles: "FLAC First", "320kbps Minimum", etc.
- **Example Profiles:**
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
  ```

---

## Implementation Priority

| Feature | Priority | Difficulty | Impact |
|---------|----------|------------|--------|
| Auto-Retry | 🔴 Critical | Medium | High |
| Quality Profiles | 🔴 Critical | High | High |
| Batch Operations | 🟡 High | Low | Medium |
| Failed History | 🟡 High | Low | Medium |
| Pause/Resume | 🟡 High | Medium | Medium |
| Reorder Queue | 🟢 Medium | Low | Low |
| Scheduling | 🟢 Medium | Medium | Low |

---

## Related Documentation

- **[Download Management](./download-management.md)** - Current implementation
- **[Quality Profiles](../feat-library/QUALITY_PROFILES.md)** - Planned quality system

---

**Last Validated:** 2025-01-13  
**Implementation Status:** 🚧 Research Complete
