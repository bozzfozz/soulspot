# API Documentation

> **Version:** 2.0  
> **Last Updated:** 2025-01-06

---

## Overview

This directory contains comprehensive API documentation for SoulSpot v2.0.

---

## Core APIs

### [Library Management API](library-management-api.md)
Manage your music library including scanning, organizing, and metadata management.

### [Download Management](download-management.md)
Control and monitor download operations from the Soulseek network.

### [Advanced Search API](advanced-search-api.md)
Advanced search capabilities with filtering, sorting, and pagination.

### [Settings API](settings-api.md)
Application settings and configuration management.

---

## Spotify Integration

### [Spotify Tracks API](spotify-tracks.md)
Track metadata fetching, ISRC-based deduplication, batch sync strategies.

### [Spotify Artist API](spotify-artist-api.md)
Artist metadata sync, authentication flows, rate limiting.

### [Spotify Playlist API](spotify-playlist-api.md)
Playlist sync with snapshot_id-based change detection.

---

## Automation & Monitoring

### [Automation API](automation-api.md) ⭐ NEW
Watchlists, discography tracking, quality upgrades, followed artists, automation rules.

**Key Features:**
- Artist watchlist management
- Discography completeness checking
- Quality upgrade identification
- Followed artists sync
- Bulk operations

### [Workers API](workers-api.md) ⭐ NEW
Background worker monitoring and status.

**Key Features:**
- Token refresh worker status
- Spotify sync worker status
- Download monitor status
- Automation workers status
- Service connectivity checks

### [Stats API](stats-api.md) ⭐ NEW
Dashboard statistics and trend data.

**Key Features:**
- Current counts for all metrics
- Trend indicators (↑/↓)
- Download activity tracking
- Spotify sync statistics

---

## Discovery & Browse

### [Browse API](browse-api.md)
Discover new music releases without authentication (uses Deezer).

### [Compilations API](compilations-api.md)
Compilation detection and filtering.

### [Metadata API](metadata-api.md)
Multi-source metadata enrichment.

---

## Authentication & Infrastructure

### [Auth API](auth-api.md)
OAuth flows for Spotify and Deezer.

### [Onboarding API](onboarding-api.md)
First-run setup and configuration wizard.

### [Infrastructure API](infrastructure-api.md)
Health checks, logs, and system status.

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
