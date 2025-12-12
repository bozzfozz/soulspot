"""Library scanner service for scanning and analyzing music library.

⚠️  DEPRECATED - RENAMED TO file_discovery_service.py ⚠️

This file will be removed in next major version.

**Migration:**
```python
# Old import (deprecated):
from soulspot.application.services.library_scanner import LibraryScannerService

# New import:
from soulspot.application.services.file_discovery_service import FileDiscoveryService
```

**Backwards Compatibility:**
Temporary alias provided below. Update your imports!

**Reason for Rename:**
- Clarity: This is LOW-LEVEL file discovery, not full library import
- library_scanner_service.py does full DB import (HIGH-LEVEL)
- Names were confusing - now crystal clear!
"""

# Backwards compatibility - import from renamed file
from soulspot.application.services.file_discovery_service import (
    AUDIO_EXTENSIONS,
    FileDiscoveryService,
    FileInfo,
)

# Deprecated alias
LibraryScannerService = FileDiscoveryService

__all__ = [
    "LibraryScannerService",  # Deprecated
    "FileDiscoveryService",  # New name
    "FileInfo",
    "AUDIO_EXTENSIONS",
]
