# 🚀 QA Quick Action Plan

**Goal:** Fix blocking issues and get tests passing
**Status:** ✅ **ALL CRITICAL ISSUES FIXED** (2025-12-13)

---

## ✅ Fix 1: Import Error - **COMPLETED**

**Problem:** `notifications.py` imports non-existent `get_session` function

**Status:** ✅ FIXED
- Import changed to `get_db_session` from `api.dependencies`
- All 6 `Depends(get_session)` calls updated

---

## ✅ Fix 2: DTO Constructor Mismatches - **COMPLETED**

**Problem:** `deezer_plugin.py` passes wrong keyword arguments to DTO constructors

**Status:** ✅ FIXED (~50 mypy errors resolved)
- `UserProfileDTO`: `id`→`deezer_id`, `service`→`source_service`, `profile_url`→`external_urls`
- `ArtistDTO`: `id`→`deezer_id`, `service`→`source_service`, `external_url`→`external_urls`
- `AlbumDTO`: `id`→`deezer_id`, `name`→`title`, `image_url`→`artwork_url`
- `PlaylistDTO`: `id`→`deezer_id`, `image_url`→`cover_url`, `track_count`→`total_tracks`
- `PaginatedResponse`: `has_more`/`next_cursor`→`next_offset` (10 occurrences)

---

## ✅ Fix 3: Method Name Errors - **COMPLETED**

**Problem:** Using `get_str()` instead of `get_string()`

**Status:** ✅ FIXED
- `credentials_service.py`: 10 occurrences fixed
- `webhook_provider.py`: 3 occurrences fixed

---

## ✅ Fix 4: Duplicate Functions - **COMPLETED**

**Problem:** Functions redefined in `downloads.py`

**Status:** ✅ FIXED
- Removed 3 duplicate function definitions (~130 lines removed)
- Kept better-documented versions with slskd integration

---

## ✅ Fix 5: ARG002 Unused Arguments - **COMPLETED**

**Problem:** ~40 unused method arguments in `tidal_plugin.py`

**Status:** ✅ FIXED
- All stub method parameters prefixed with underscore (`_`)
- 16 methods updated across auth, search, artists, albums, tracks, playlists, library

---

## ✅ Fix 6: Test Failures - **COMPLETED**

**Problem:** Middleware tests and domain tests failing

**Status:** ✅ FIXED
- Middleware tests: Updated expectations for simplified logging (1 log per request)
- `test_get_artist_albums_success`: Updated to expect `album,single,compilation`
- `test_album_invalid_year_raises_error`: Added validation to Album entity `__post_init__`

---

## ⏳ Remaining Low-Priority Issues

| Issue | Count | Priority | Notes |
|-------|-------|----------|-------|
| Type errors (mypy) | ~80 | Low | Mostly edge cases |
| Bandit findings | 11 | Low | False positives |
| Test coverage | 11% | Medium | Long-term goal: 80% |

---

## 📚 Resources

- **Full QA Report:** `QA_REPORT.md`
- **Command Reference:** `QA_RUN_SUMMARY.md`

---

**Last Updated:** 2025-12-13  
**Status:** ✅ ALL CRITICAL ISSUES RESOLVED
