# Automation Watchlists

**Category:** Features  
**Status:** ✅ Active  
**Last Updated:** 2025-11-30  
**Related Docs:** [Followed Artists](./followed-artists.md) | [API Reference: Automation](../03-api-reference/automation.md)

---

## Overview

Automation Watchlists monitor artists for new releases and automatically download them based on configured rules. Uses cached `spotify_albums` data from Artist Albums Background Sync to avoid excessive API calls.

---

## Features

### Artist Watchlists

Monitor artists for new releases:

- **Automatic Checks:** Regular checks for new albums/singles
- **Auto-Download:** New releases automatically downloaded
- **Quality Profiles:** Configurable quality settings per watchlist
- **Local Data First:** Uses cached `spotify_albums` instead of API calls ⭐

---

### Filter Rules

Control which downloads are allowed:

- **Whitelist:** Only allow downloads matching patterns
- **Blacklist:** Block downloads matching patterns
- **Regex Support:** Define patterns with regular expressions

---

### Discography Check

Check if you have all albums from an artist:

- **Completeness Check:** Compare with local `spotify_albums` table ⭐
- **Missing Albums:** List all albums you're missing
- **No API Calls:** Uses cached data from Background Sync

---

### Quality Upgrades

Identify tracks for quality upgrades:

- **Upgrade Candidates:** Find tracks with low quality
- **Automatic Upgrades:** Optional automatic re-downloads

---

## Usage (Web UI)

### Create Watchlist

1. Navigate to **Automation** → **Watchlists**
2. Click **Create Watchlist**
3. Select artist
4. Configure settings:
   - **Check Interval:** How often to check (minimum 1 hour)
   - **Auto-Download:** Automatically download or notify only
   - **Quality Profile:** `low`, `medium`, `high`, `lossless`
5. Click **Create**

⚠️ **Note:** Watchlist quality profiles (`low`, `medium`, `high`, `lossless`) differ from download quality settings (`best`, `good`, `any`). Watchlists define minimum quality for auto-downloads, while download settings determine search order.

---

### Create Filter

1. Navigate to **Automation** → **Filters**
2. Click **Create Filter**
3. Configure:
   - **Name:** Descriptive name
   - **Type:** Whitelist or Blacklist
   - **Target:** What to filter (Keyword, User, Format, Bitrate)
   - **Pattern:** Match pattern
   - **Regex:** Is pattern a regex?
4. Click **Create**

---

### Create Automation Rule

1. Navigate to **Automation** → **Rules**
2. Click **Create Rule**
3. Configure:
   - **Name:** Descriptive name
   - **Trigger:** `new_release`, `missing_album`, `quality_upgrade`, `manual`
   - **Action:** `search_and_download`, `notify_only`, `add_to_queue`
   - **Apply Filters:** Apply filters?
   - **Auto-Process:** Execute automatically?
4. Click **Create**

---

## API Endpoints

### POST `/api/automation/watchlist`

Create new watchlist.

**Request:**
```json
{
  "artist_id": "artist-uuid",
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high"
}
```

⚠️ **Validation:** `check_frequency_hours` minimum 1, `quality_profile` must be `low`, `medium`, `high`, or `lossless`.

**Response:**
```json
{
  "id": "watchlist-uuid",
  "artist_id": "artist-uuid",
  "status": "active",
  "check_frequency_hours": 24,
  "auto_download": true,
  "quality_profile": "high",
  "last_checked_at": null,
  "last_release_date": null,
  "total_releases_found": 0,
  "total_downloads_triggered": 0,
  "created_at": "2025-01-15T10:00:00Z"
}
```

---

### GET `/api/automation/watchlist`

List all watchlists.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Max results |
| `offset` | int | 0 | Pagination offset |
| `active_only` | bool | false | Only active watchlists |

---

### GET `/api/automation/watchlist/{watchlist_id}`

Get watchlist details.

---

### POST `/api/automation/watchlist/{watchlist_id}/check`

Manually trigger check for new releases.

---

### DELETE `/api/automation/watchlist/{watchlist_id}`

Delete watchlist.

---

## Quality Profiles

| Profile | Description | Minimum Quality |
|---------|-------------|-----------------|
| `low` | Low quality acceptable | 128 kbps MP3 |
| `medium` | Medium quality | 256 kbps MP3 |
| `high` | High quality | 320 kbps MP3 |
| `lossless` | Lossless only | FLAC |

---

## Related Documentation

- **[Followed Artists](./followed-artists.md)** - Bulk watchlist creation
- **[API Reference: Automation](../03-api-reference/automation.md)** - Full endpoint documentation

---

**Last Validated:** 2025-11-30  
**Implementation Status:** ✅ Production-ready
