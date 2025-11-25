# API Documentation

> **Version:** 1.0  
> **Last Updated:** 2025-11-25

---

## Overview

This directory contains API documentation for SoulSpot version 1.0.

---

## Available APIs

### [Advanced Search API](advanced-search-api.md)
Advanced search capabilities for tracks, albums, and artists with filtering, sorting, and pagination.

**Key Features:**
- Multi-field search queries
- Filter by metadata (genre, year, format, bitrate)
- Sort by relevance, date, popularity
- Pagination support
- Autocomplete suggestions

### [Library Management API](library-management-api.md)
Manage your music library including scanning, organizing, and metadata management.

**Key Features:**
- Library scanning and indexing
- Metadata editing and enrichment
- Duplicate detection
- File organization
- Bulk operations

### [Download Management](download-management.md)
Control and monitor download operations from the Soulseek network.

**Key Features:**
- Queue management
- Download prioritization
- Progress tracking
- Retry logic
- Bandwidth controls

### [Spotify Metadata Reference](spotify-metadata-reference.md)
Comprehensive reference for Spotify API metadata fields used in Soulspot.

**Key Features:**
- Field reference by entity type (Artist, Album, Track, Playlist)
- Priority levels (Minimal vs. Optional)
- Index recommendations
- Storage type guidance
- Cross-source matching strategies (ISRC, UPC, MusicBrainz)
- Rate limits and authentication practicalities
### [Spotify Tracks API](spotify-tracks.md)
Integration with Spotify Web API for track/song data management.

**Key Features:**
- Track metadata fetching and storage
- Audio features integration
- ISRC-based deduplication
- Batch sync strategies
- Field mappings and schema recommendations
### [Spotify Artist API](spotify-artist-api.md)
Integration with Spotify Web API for artist metadata synchronization.

**Key Features:**
- Artist metadata sync from Spotify
- Field mapping and data model documentation
- Authentication flows (Client Credentials, PKCE)
- Rate limiting and exponential backoff
- On-demand and periodic sync strategies
- Database schema reference

---

## API Access

### Base URL
```
http://localhost:8765/api
```

### Authentication
Most endpoints require authentication. See the [User Guide](../guides/user/user-guide.md) for authentication setup.

### Response Format
All API endpoints return JSON responses with the following structure:

**Success Response:**
```json
{
  "status": "success",
  "data": { ... }
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Error description",
  "code": "ERROR_CODE"
}
```

---

## Interactive API Documentation

SoulSpot includes interactive API documentation powered by FastAPI:

**Swagger UI:** http://localhost:8765/docs  
**ReDoc:** http://localhost:8765/redoc

These interfaces allow you to:
- Browse all available endpoints
- View request/response schemas
- Test API calls directly from the browser
- Download OpenAPI specification

---

## Rate Limiting

API endpoints may be rate-limited to ensure fair usage:
- **Standard endpoints:** 100 requests/minute
- **Search endpoints:** 30 requests/minute
- **Download endpoints:** 10 requests/minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1634567890
```

---

## Pagination

List endpoints support pagination using query parameters:

```
GET /api/tracks?page=1&per_page=50
```

**Response includes pagination metadata:**
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1250,
    "pages": 25,
    "has_next": true,
    "has_prev": false
  }
}
```

---

## Error Codes

Common error codes across all APIs:

| Code | Description |
|------|-------------|
| `AUTH_REQUIRED` | Authentication required |
| `AUTH_INVALID` | Invalid authentication credentials |
| `NOT_FOUND` | Resource not found |
| `VALIDATION_ERROR` | Request validation failed |
| `RATE_LIMIT` | Rate limit exceeded |
| `SERVER_ERROR` | Internal server error |

---

## SDK Support

Currently, API access is available via:
- Direct HTTP requests
- JavaScript/TypeScript (HTMX integration)
- Python (internal service layer)

Third-party SDK development is welcome. See [Contributing Guide](../project/contributing.md).

---

## Versioning

The API follows semantic versioning. Breaking changes will be introduced in major version updates with appropriate migration guides.

**Current Version:** 1.0  
**API Stability:** Stable

---

## Related Documentation

- [User Guide](../guides/user/user-guide.md) - How to use the API through the UI
- [Development Guide](../development/) - API development guidelines
- [Architecture](../project/architecture.md) - System architecture overview

---

For questions or issues with the API, please refer to the [Troubleshooting Guide](../guides/user/troubleshooting-guide.md) or open an issue on GitHub.
