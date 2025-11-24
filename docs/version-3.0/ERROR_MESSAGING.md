# Error Messaging Standards (Version 3.0)

**Version:** 3.0.0  
**Status:** Planning Phase  
**Last Updated:** 2025-11-22

---

## 1. Overview

This document defines **comprehensive error messaging standards** for SoulSpot Version 3.0. All errors MUST provide actionable, user-friendly messages with clear resolution steps.

### 1.1 Core Principles

1. **Actionable**: Every error tells user exactly what to do
2. **Contextual**: Errors include relevant context for debugging
3. **Consistent**: Same format across all modules
4. **Documented**: Errors link to troubleshooting docs
5. **Logged**: All errors logged with full context for support
6. **i18n-ready**: Error messages support internationalization

### 1.2 Why This Matters

**Bad Error:**
```
❌ Error: Failed
```

**Good Error:**
```
🔌 Connection Failed

Code: SLSKD_CONNECTION_TIMEOUT
Message: Could not connect to slskd at http://localhost:5030
What to do:
  1. Check if slskd is running: docker ps | grep slskd
  2. Verify URL is correct in Settings → Soulseek
  3. Check network connectivity
  4. Check slskd logs for errors
Context:
  Module: soulseek
  URL: http://localhost:5030
  Timeout: 5s
  Last successful: 2025-11-22 10:30:15
Docs: https://docs.soulspot.app/troubleshooting/connection-errors
```

---

## 2. Error Structure

### 2.1 Standard Error Format

**All errors MUST use this structure:**

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

class ErrorLevel(Enum):
    """Error severity levels."""
    ERROR = "error"      # Critical error, operation failed
    WARNING = "warning"  # Non-critical issue, operation may succeed
    INFO = "info"        # Informational, no action needed

@dataclass
class SoulSpotError(Exception):
    """
    Base error class for SoulSpot.
    
    All custom errors MUST inherit from this class.
    """
    
    # Required fields
    code: str                    # Unique error code (UPPER_SNAKE_CASE)
    message: str                 # Human-readable message
    resolution: str              # What user should do
    
    # Optional fields
    context: Dict = None         # Error context (module, params, etc.)
    docs_url: str = None         # Link to troubleshooting docs
    severity: ErrorLevel = ErrorLevel.ERROR
    inner_error: Exception = None  # Original exception if wrapping
    
    def __post_init__(self):
        """Initialize context as empty dict if None."""
        if self.context is None:
            self.context = {}
    
    def to_dict(self) -> dict:
        """
        Convert error to dictionary for API responses.
        
        Returns:
            dict with error details
        """
        return {
            "code": self.code,
            "message": self.message,
            "resolution": self.resolution,
            "context": self.context,
            "docs_url": self.docs_url,
            "severity": self.severity.value,
        }
    
    def format_for_user(self) -> str:
        """
        Format error for display in UI.
        
        Returns:
            Formatted multi-line error message
        """
        emoji = {
            ErrorLevel.ERROR: "❌",
            ErrorLevel.WARNING: "⚠️",
            ErrorLevel.INFO: "ℹ️",
        }[self.severity]
        
        lines = [
            f"{emoji} {self.message}",
            "",
            f"Code: {self.code}",
        ]
        
        if self.resolution:
            lines.append("")
            lines.append("What to do:")
            for line in self.resolution.split("\n"):
                lines.append(f"  {line}")
        
        if self.context:
            lines.append("")
            lines.append("Context:")
            for key, value in self.context.items():
                lines.append(f"  {key}: {value}")
        
        if self.docs_url:
            lines.append("")
            lines.append(f"Docs: {self.docs_url}")
        
        return "\n".join(lines)
    
    def format_for_log(self) -> str:
        """
        Format error for logging.
        
        Returns:
            JSON-formatted error for structured logging
        """
        import json
        return json.dumps({
            "error_code": self.code,
            "error_message": self.message,
            "error_severity": self.severity.value,
            "context": self.context,
            "resolution": self.resolution,
            "docs_url": self.docs_url,
            "inner_error": str(self.inner_error) if self.inner_error else None,
        })
```

### 2.2 Error Code Format

**Format:** `{MODULE}_{CATEGORY}_{SPECIFIC}`

**Examples:**
- `SPOTIFY_AUTH_TOKEN_EXPIRED`
- `SLSKD_CONNECTION_TIMEOUT`
- `LIBRARY_FILE_NOT_FOUND`
- `METADATA_MUSICBRAINZ_RATE_LIMIT`

**Categories:**
- `AUTH` - Authentication/authorization
- `CONNECTION` - Network connectivity
- `CONFIG` - Configuration issues
- `VALIDATION` - Input validation
- `NOT_FOUND` - Resource not found
- `RATE_LIMIT` - API rate limiting
- `PERMISSION` - Permission denied
- `INTERNAL` - Internal server error

---

## 3. Error Categories

### 3.1 User Errors

**Definition:** Errors caused by invalid user input or actions.

**Characteristics:**
- Severity: ERROR or WARNING
- Resolution: Clear instructions to fix input
- No technical jargon
- Examples in resolution steps

**Examples:**

```python
# Example 1: Empty search query
class InvalidQueryError(SoulSpotError):
    """Raised when search query is invalid."""
    pass

raise InvalidQueryError(
    code="SPOTIFY_SEARCH_EMPTY_QUERY",
    message="Search query cannot be empty",
    resolution="Enter at least 1 character to search for tracks",
    context={
        "module": "spotify.search",
        "query_length": 0,
    },
    docs_url="https://docs.soulspot.app/spotify/search#errors",
)

# Example 2: Invalid file format
raise ValidationError(
    code="LIBRARY_INVALID_FILE_FORMAT",
    message="File format 'exe' is not supported",
    resolution=(
        "Supported formats:\n"
        "- Audio: mp3, flac, m4a, ogg, wav\n"
        "- Use audio files only"
    ),
    context={
        "module": "library",
        "file_path": "/music/virus.exe",
        "file_format": "exe",
        "supported_formats": ["mp3", "flac", "m4a", "ogg", "wav"],
    },
    docs_url="https://docs.soulspot.app/library/supported-formats",
)

# Example 3: Query too long
raise ValidationError(
    code="SPOTIFY_SEARCH_QUERY_TOO_LONG",
    message=f"Search query too long ({len(query)} characters)",
    resolution="Limit query to 500 characters or less",
    context={
        "module": "spotify.search",
        "query_length": len(query),
        "max_length": 500,
    },
)
```

### 3.2 Configuration Errors

**Definition:** Errors due to missing or invalid configuration.

**Characteristics:**
- Severity: ERROR
- Resolution: Step-by-step configuration guide
- Links to onboarding or settings
- May suggest default values

**Examples:**

```python
# Example 1: Missing Spotify credentials
raise ConfigurationError(
    code="SPOTIFY_AUTH_CONFIG_MISSING",
    message="Spotify client_id or client_secret not configured",
    resolution=(
        "Configure Spotify credentials:\n"
        "1. Go to Settings → Spotify\n"
        "2. Click 'Configure'\n"
        "3. Enter your Spotify app credentials\n"
        "4. Get credentials from: https://developer.spotify.com/dashboard\n"
        "5. Click 'Test Connection' before saving"
    ),
    context={
        "module": "spotify.auth",
        "missing_config": ["client_id", "client_secret"],
    },
    docs_url="https://docs.soulspot.app/setup/spotify",
)

# Example 2: Invalid slskd URL
raise ConfigurationError(
    code="SLSKD_INVALID_URL",
    message=f"slskd URL '{url}' is invalid",
    resolution=(
        "Check slskd URL format:\n"
        "✅ Correct: http://localhost:5030\n"
        "✅ Correct: http://192.168.1.100:5030\n"
        "❌ Wrong: localhost:5030 (missing http://)\n"
        "❌ Wrong: slskd:5030 (invalid hostname)"
    ),
    context={
        "module": "soulseek",
        "url": url,
        "expected_format": "http://host:port",
    },
    docs_url="https://docs.soulspot.app/setup/soulseek#url-format",
)

# Example 3: Misconfigured timeout
raise ConfigurationError(
    code="CONFIG_TIMEOUT_OUT_OF_RANGE",
    message=f"Timeout value {timeout} is out of valid range",
    resolution=(
        "Set timeout between 5 and 120 seconds.\n"
        "Recommended: 30 seconds for most connections"
    ),
    context={
        "module": "soulseek",
        "timeout": timeout,
        "min_timeout": 5,
        "max_timeout": 120,
        "recommended": 30,
    },
)
```

### 3.3 Integration Errors

**Definition:** Errors from external services or integrations.

**Characteristics:**
- Severity: ERROR or WARNING
- Resolution: Check service status and configuration
- Include service-specific troubleshooting
- May suggest retry or fallback

**Examples:**

```python
# Example 1: slskd connection timeout
raise ConnectionError(
    code="SLSKD_CONNECTION_TIMEOUT",
    message=f"Could not connect to slskd at {url}",
    resolution=(
        "Troubleshoot slskd connection:\n"
        "1. Check if slskd is running:\n"
        "   docker ps | grep slskd\n"
        "2. Verify URL is correct in Settings → Soulseek\n"
        "3. Check network connectivity:\n"
        "   curl http://localhost:5030/api/v0/session\n"
        "4. Check slskd logs:\n"
        "   docker logs slskd\n"
        "5. Restart slskd if needed:\n"
        "   docker restart slskd"
    ),
    context={
        "module": "soulseek",
        "url": url,
        "timeout": 5,
        "last_successful": "2025-11-22 10:30:15",
    },
    docs_url="https://docs.soulspot.app/troubleshooting/connection-errors",
)

# Example 2: Spotify API rate limit
raise RateLimitError(
    code="SPOTIFY_API_RATE_LIMIT",
    message="Spotify API rate limit exceeded",
    resolution=(
        "Wait before making more requests.\n"
        "Spotify allows 100 requests per hour.\n"
        "Your quota will reset in {retry_after} seconds."
    ),
    context={
        "module": "spotify",
        "retry_after": 3600,
        "requests_made": 100,
        "limit": 100,
    },
    severity=ErrorLevel.WARNING,
    docs_url="https://docs.soulspot.app/spotify/rate-limits",
)

# Example 3: MusicBrainz service unavailable
raise ServiceUnavailableError(
    code="MUSICBRAINZ_SERVICE_UNAVAILABLE",
    message="MusicBrainz API is currently unavailable",
    resolution=(
        "Metadata enrichment temporarily disabled.\n"
        "- Downloads will continue without metadata\n"
        "- Metadata will be added when service recovers\n"
        "- Check status: https://status.musicbrainz.org"
    ),
    context={
        "module": "metadata",
        "service": "musicbrainz",
        "status_url": "https://status.musicbrainz.org",
    },
    severity=ErrorLevel.WARNING,
    docs_url="https://docs.soulspot.app/metadata/fallback",
)

# Example 4: Authentication token expired
raise AuthenticationError(
    code="SPOTIFY_AUTH_TOKEN_EXPIRED",
    message="Your Spotify session has expired",
    resolution="Click 'Re-authenticate with Spotify' to refresh your session",
    context={
        "module": "spotify.auth",
        "expired_at": "2025-11-22 10:30:15",
        "last_refresh": "2025-11-22 09:30:15",
    },
    severity=ErrorLevel.WARNING,
    docs_url="https://docs.soulspot.app/spotify/authentication",
)
```

### 3.4 System Errors

**Definition:** Internal errors, bugs, or unexpected conditions.

**Characteristics:**
- Severity: ERROR
- Resolution: Report bug or check logs
- Include full context for debugging
- Log stack trace automatically

**Examples:**

```python
# Example 1: Database connection failed
raise DatabaseError(
    code="DATABASE_CONNECTION_FAILED",
    message="Could not connect to database",
    resolution=(
        "This is an internal error. Please:\n"
        "1. Check application logs\n"
        "2. Restart application\n"
        "3. If persists, report bug with logs"
    ),
    context={
        "module": "core",
        "database_path": "/data/soulspot.db",
        "error": str(inner_error),
    },
    inner_error=inner_error,
    docs_url="https://docs.soulspot.app/troubleshooting/database",
)

# Example 2: Unexpected null value
raise InternalError(
    code="INTERNAL_UNEXPECTED_NULL",
    message=f"Unexpected null value for {field_name}",
    resolution=(
        "This is a bug. Please report:\n"
        "1. Copy this error message\n"
        "2. Go to https://github.com/bozzfozz/soulspot/issues\n"
        "3. Create new issue with error details"
    ),
    context={
        "module": module_name,
        "field": field_name,
        "function": function_name,
        "line": line_number,
    },
    docs_url="https://docs.soulspot.app/troubleshooting/bugs",
)

# Example 3: File system error
raise FileSystemError(
    code="FILESYSTEM_PERMISSION_DENIED",
    message=f"Permission denied writing to {path}",
    resolution=(
        "Check file permissions:\n"
        "1. Verify application has write access to {directory}\n"
        "2. Check directory ownership:\n"
        "   ls -la {directory}\n"
        "3. Fix permissions if needed:\n"
        "   sudo chown -R user:user {directory}"
    ),
    context={
        "module": "library",
        "path": path,
        "directory": os.path.dirname(path),
        "user": os.getenv("USER"),
    },
    docs_url="https://docs.soulspot.app/troubleshooting/permissions",
)
```

---

## 4. Error Display Patterns

### 4.1 UI Display (Toast Notification)

```html
<!-- Toast notification for errors -->
<div class="toast toast--{{ error.severity }}" role="alert">
  <div class="toast__icon">
    {% if error.severity == 'error' %}❌{% endif %}
    {% if error.severity == 'warning' %}⚠️{% endif %}
    {% if error.severity == 'info' %}ℹ️{% endif %}
  </div>
  
  <div class="toast__content">
    <div class="toast__title">{{ error.message }}</div>
    <div class="toast__code">Code: {{ error.code }}</div>
    
    {% if error.resolution %}
      <div class="toast__resolution">
        <strong>What to do:</strong>
        <div>{{ error.resolution|safe }}</div>
      </div>
    {% endif %}
    
    {% if error.docs_url %}
      <a href="{{ error.docs_url }}" class="toast__docs-link" target="_blank">
        View troubleshooting guide →
      </a>
    {% endif %}
  </div>
  
  <button class="toast__close" onclick="this.parentElement.remove()">×</button>
</div>
```

### 4.2 UI Display (Alert Card)

```html
<!-- Alert card for persistent errors -->
<div class="card card--alert card--alert-{{ error.severity }}">
  <div class="card__header">
    <h3 class="card__title">
      {% if error.severity == 'error' %}❌{% endif %}
      {% if error.severity == 'warning' %}⚠️{% endif %}
      {{ error.message }}
    </h3>
  </div>
  
  <div class="card__body">
    <p class="alert__code">Error Code: {{ error.code }}</p>
    
    {% if error.resolution %}
      <div class="alert__resolution">
        <h4>What to do:</h4>
        <div>{{ error.resolution|safe|linebreaks }}</div>
      </div>
    {% endif %}
    
    {% if error.context %}
      <details class="alert__context">
        <summary>Technical Details</summary>
        <pre>{{ error.context|tojson(indent=2) }}</pre>
      </details>
    {% endif %}
  </div>
  
  <div class="card__footer">
    {% if error.docs_url %}
      <a href="{{ error.docs_url }}" class="btn btn--secondary" target="_blank">
        Troubleshooting Guide
      </a>
    {% endif %}
    
    <button class="btn btn--secondary" onclick="this.closest('.card').remove()">
      Dismiss
    </button>
  </div>
</div>
```

### 4.3 UI Display (Inline Error)

```html
<!-- Inline error for form fields -->
<div class="form-group form-group--error">
  <label for="slskd-url">slskd URL</label>
  <input 
    type="text" 
    id="slskd-url" 
    name="slskd_url"
    class="form-control form-control--error"
    value="{{ form.slskd_url }}"
    aria-describedby="slskd-url-error"
  />
  
  <div class="form-error" id="slskd-url-error" role="alert">
    <span class="form-error__icon">⚠️</span>
    <div class="form-error__content">
      <div class="form-error__message">{{ error.message }}</div>
      <div class="form-error__hint">{{ error.resolution }}</div>
    </div>
  </div>
</div>
```

### 4.4 API Response

```json
// Error response format for API
{
  "error": {
    "code": "SPOTIFY_AUTH_TOKEN_EXPIRED",
    "message": "Your Spotify session has expired",
    "resolution": "Click 'Re-authenticate with Spotify' to refresh your session",
    "context": {
      "module": "spotify.auth",
      "expired_at": "2025-11-22T10:30:15Z",
      "last_refresh": "2025-11-22T09:30:15Z"
    },
    "docs_url": "https://docs.soulspot.app/spotify/authentication",
    "severity": "warning"
  }
}
```

### 4.5 Log Format

```python
# Structured logging format
import logging
import json

logger = logging.getLogger(__name__)

try:
    # ... operation that fails
    pass
except SoulSpotError as e:
    # Log structured error
    logger.error(
        e.message,
        extra={
            "error_code": e.code,
            "error_severity": e.severity.value,
            "resolution": e.resolution,
            "context": e.context,
            "docs_url": e.docs_url,
        },
        exc_info=e.inner_error,  # Include stack trace if wrapping
    )
    
    # Re-raise or handle
    raise

# Example log output (JSON):
{
  "timestamp": "2025-11-22T10:30:15.123Z",
  "level": "ERROR",
  "message": "Could not connect to slskd at http://localhost:5030",
  "error_code": "SLSKD_CONNECTION_TIMEOUT",
  "error_severity": "error",
  "resolution": "Troubleshoot slskd connection:\n1. Check if slskd is running...",
  "context": {
    "module": "soulseek",
    "url": "http://localhost:5030",
    "timeout": 5,
    "last_successful": "2025-11-22 10:29:45"
  },
  "docs_url": "https://docs.soulspot.app/troubleshooting/connection-errors"
}
```

---

## 5. Module-Specific Errors

### 5.1 Soulseek Module Errors

```python
# Connection errors
SLSKD_CONNECTION_TIMEOUT = "Could not connect to slskd at {url}"
SLSKD_CONNECTION_REFUSED = "Connection refused by slskd at {url}"
SLSKD_AUTH_FAILED = "Authentication failed with slskd"
SLSKD_NOT_LOGGED_IN = "slskd is not logged into Soulseek network"

# Search errors
SLSKD_SEARCH_NO_RESULTS = "No results found for '{query}'"
SLSKD_SEARCH_TIMEOUT = "Search timed out after {timeout} seconds"
SLSKD_SEARCH_RATE_LIMIT = "Too many searches in short time"

# Download errors
SLSKD_DOWNLOAD_NOT_FOUND = "Download {download_id} not found"
SLSKD_DOWNLOAD_FAILED = "Download failed: {reason}"
SLSKD_DOWNLOAD_TIMEOUT = "Download timed out after {timeout} seconds"
SLSKD_DOWNLOAD_DISK_FULL = "Insufficient disk space for download"
SLSKD_DOWNLOAD_USER_OFFLINE = "User {username} is offline"
```

### 5.2 Spotify Module Errors

```python
# Authentication errors
SPOTIFY_AUTH_CONFIG_MISSING = "Spotify credentials not configured"
SPOTIFY_AUTH_INVALID_CREDENTIALS = "Invalid Spotify credentials"
SPOTIFY_AUTH_TOKEN_EXPIRED = "Spotify session expired"
SPOTIFY_AUTH_REFRESH_FAILED = "Could not refresh Spotify token"
SPOTIFY_AUTH_USER_CANCELLED = "User cancelled Spotify login"

# Search errors
SPOTIFY_SEARCH_EMPTY_QUERY = "Search query cannot be empty"
SPOTIFY_SEARCH_QUERY_TOO_LONG = "Search query too long"
SPOTIFY_SEARCH_NO_RESULTS = "No results found for '{query}'"

# Playlist errors
SPOTIFY_PLAYLIST_NOT_FOUND = "Playlist not found"
SPOTIFY_PLAYLIST_PRIVATE = "Cannot access private playlist"
SPOTIFY_PLAYLIST_SYNC_FAILED = "Failed to sync playlist"

# Rate limit errors
SPOTIFY_API_RATE_LIMIT = "Spotify API rate limit exceeded"
```

### 5.3 Library Module Errors

```python
# File errors
LIBRARY_FILE_NOT_FOUND = "File not found: {path}"
LIBRARY_FILE_CORRUPTED = "File appears to be corrupted"
LIBRARY_INVALID_FILE_FORMAT = "File format '{format}' not supported"
LIBRARY_DUPLICATE_FILE = "File already exists in library"

# Import errors
LIBRARY_IMPORT_FAILED = "Failed to import file to library"
LIBRARY_IMPORT_PERMISSION_DENIED = "Permission denied importing file"
LIBRARY_IMPORT_DISK_FULL = "Insufficient disk space to import"

# Metadata errors
LIBRARY_METADATA_MISSING = "File has no metadata tags"
LIBRARY_METADATA_READ_ERROR = "Could not read file metadata"
LIBRARY_METADATA_WRITE_ERROR = "Could not write file metadata"
```

### 5.4 Metadata Module Errors

```python
# MusicBrainz errors
MUSICBRAINZ_NOT_FOUND = "No match found in MusicBrainz database"
MUSICBRAINZ_RATE_LIMIT = "MusicBrainz rate limit exceeded"
MUSICBRAINZ_SERVICE_UNAVAILABLE = "MusicBrainz service unavailable"
MUSICBRAINZ_MULTIPLE_MATCHES = "Multiple matches found, manual selection required"

# Cover art errors
COVERART_NOT_FOUND = "No cover art found"
COVERART_DOWNLOAD_FAILED = "Failed to download cover art"
COVERART_INVALID_IMAGE = "Downloaded image is invalid"
```

---

## 6. Error Handling Best Practices

### 6.1 Catching and Re-raising

```python
# Good: Catch, add context, re-raise as SoulSpotError
try:
    response = await httpx_client.get(url, timeout=5)
    response.raise_for_status()
except httpx.TimeoutException as e:
    raise ConnectionError(
        code="SLSKD_CONNECTION_TIMEOUT",
        message=f"Could not connect to slskd at {url}",
        resolution=(
            "Troubleshoot slskd connection:\n"
            "1. Check if slskd is running\n"
            "2. Verify URL in settings"
        ),
        context={
            "module": "soulseek",
            "url": url,
            "timeout": 5,
        },
        inner_error=e,  # Preserve original exception
        docs_url="https://docs.soulspot.app/troubleshooting/connection-errors",
    )
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        raise AuthenticationError(
            code="SLSKD_AUTH_FAILED",
            message="Authentication failed with slskd",
            resolution=(
                "Check slskd credentials:\n"
                "1. Verify API key or username/password\n"
                "2. Update in Settings → Soulseek"
            ),
            context={
                "module": "soulseek",
                "status_code": 401,
            },
            inner_error=e,
        )
    raise  # Re-raise if not handled
```

### 6.2 Logging Errors

```python
# Always log errors before raising or handling
logger = logging.getLogger(__name__)

try:
    result = await risky_operation()
except SoulSpotError as e:
    # Log with full context
    logger.error(
        e.message,
        extra={
            "error_code": e.code,
            "context": e.context,
            "resolution": e.resolution,
        },
        exc_info=e.inner_error if e.inner_error else True,
    )
    
    # Re-raise or handle
    raise
```

### 6.3 User-Facing vs. Technical Errors

```python
# User-facing: Simple, actionable
raise ValidationError(
    code="SPOTIFY_SEARCH_EMPTY_QUERY",
    message="Search query cannot be empty",
    resolution="Enter at least 1 character to search",
    # ... context omitted in UI, logged only
)

# Technical (for logs): Detailed debugging info
raise InternalError(
    code="DATABASE_QUERY_FAILED",
    message="Database query failed",
    resolution="Check logs and report bug if persists",
    context={
        "query": sql_query,
        "params": query_params,
        "table": table_name,
        "error": str(db_error),
        "stack_trace": traceback.format_exc(),
    },
    inner_error=db_error,
)
```

---

## 7. Internationalization (i18n)

### 7.1 Translation Keys

```python
# Error messages should use translation keys
from flask_babel import gettext as _

raise ValidationError(
    code="SPOTIFY_SEARCH_EMPTY_QUERY",
    message=_("error.spotify.search.empty_query"),
    resolution=_("error.spotify.search.empty_query.resolution"),
    context={"module": "spotify.search"},
)

# Translation files (messages.po):
# English
msgid "error.spotify.search.empty_query"
msgstr "Search query cannot be empty"

msgid "error.spotify.search.empty_query.resolution"
msgstr "Enter at least 1 character to search"

# German
msgid "error.spotify.search.empty_query"
msgstr "Suchanfrage darf nicht leer sein"

msgid "error.spotify.search.empty_query.resolution"
msgstr "Geben Sie mindestens 1 Zeichen ein, um zu suchen"
```

---

## 8. Testing Error Messages

### 8.1 Unit Tests

```python
import pytest
from soulspot.errors import ValidationError

def test_error_format_for_user():
    """Test error formatting for UI display."""
    error = ValidationError(
        code="SPOTIFY_SEARCH_EMPTY_QUERY",
        message="Search query cannot be empty",
        resolution="Enter at least 1 character to search",
        context={"module": "spotify.search"},
    )
    
    formatted = error.format_for_user()
    
    assert "❌" in formatted
    assert "Code: SPOTIFY_SEARCH_EMPTY_QUERY" in formatted
    assert "What to do:" in formatted
    assert "Enter at least 1 character" in formatted

def test_error_to_dict():
    """Test error serialization for API responses."""
    error = ValidationError(
        code="TEST_ERROR",
        message="Test message",
        resolution="Test resolution",
    )
    
    error_dict = error.to_dict()
    
    assert error_dict["code"] == "TEST_ERROR"
    assert error_dict["message"] == "Test message"
    assert error_dict["resolution"] == "Test resolution"
    assert error_dict["severity"] == "error"
```

---

## 9. Summary

**Key Requirements:**
- ✅ All errors use structured `SoulSpotError` format
- ✅ Every error has unique code, message, and resolution
- ✅ Context included for debugging (logged, not always shown to user)
- ✅ Documentation links for complex issues
- ✅ i18n-ready with translation keys
- ✅ Consistent display across UI (toast, alert card, inline)
- ✅ Structured logging for support and debugging

**Benefits:**
- Users know exactly what to do
- Support team has full context from logs
- Errors are searchable by code
- Documentation is discoverable
- Multi-language support ready

---

**End of Error Messaging Standards**
