"""Library Services Package - Consolidated library management services.

Hey future me - this is the REORGANIZED library services package!

Phase 6 of SERVICE_CONSOLIDATION_PLAN_COMPLETE.md:
- Reorganized services into logical library/ subpackage
- Removed deprecated code (~400 LOC from scanner)
- Deleted unused file_discovery_service.py (~377 LOC)
- Unified AUDIO_EXTENSIONS constant

Services in this package:
- scanner_service.py: LibraryScannerService (Lidarr folder scanning)
- cleanup_service.py: LibraryCleanupService (bulk deletes, orphan cleanup)
- import_service.py: AutoImportService (download → library import)
- view_service.py: LibraryViewService (ViewModels for templates)
- analyzer_service.py: CompilationAnalyzerService (post-scan analysis)

All services are imported from the old locations for backward compatibility.
New code should import from this package:
    from soulspot.application.services.library import LibraryScannerService

Architecture:
    scanner_service:  Scan Lidarr folders → DB entities
    cleanup_service:  Delete orphans, reset library
    import_service:   slskd downloads → music library
    view_service:     DB entities → ViewModels
    analyzer_service: Album analysis → compilation detection
"""

from __future__ import annotations

# Scanner Service - Main library scanning
from soulspot.application.services.library_scanner_service import (
    LibraryScannerService,
)

# Cleanup Service - Bulk delete operations
from soulspot.application.services.library_cleanup_service import (
    LibraryCleanupService,
)

# Import Service - Download → Library import (renamed from auto_import)
from soulspot.application.services.auto_import import (
    AutoImportService,
)

# View Service - ViewModels for templates
from soulspot.application.services.library_view_service import (
    LibraryViewService,
)

# Analyzer Service - Post-scan compilation detection
from soulspot.application.services.compilation_analyzer_service import (
    CompilationAnalyzerService,
    AlbumAnalysisResult,
)

# Shared constants (single source of truth)
# Hey future me - ALL audio extension sets should use this!
from soulspot.domain.value_objects.folder_parsing import AUDIO_EXTENSIONS

__all__ = [
    # Services
    "LibraryScannerService",
    "LibraryCleanupService",
    "AutoImportService",
    "LibraryViewService",
    "CompilationAnalyzerService",
    # DTOs/Results
    "AlbumAnalysisResult",
    # Constants
    "AUDIO_EXTENSIONS",
]
