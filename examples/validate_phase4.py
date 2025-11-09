#!/usr/bin/env python3
"""Validation script for Phase 4 implementation.

This script validates that all Phase 4 components are properly structured
and can be imported without errors.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def validate_imports() -> bool:
    """Validate all Phase 4 imports."""
    print("Validating Phase 4 imports...")
    
    errors = []
    
    # Test use cases
    try:
        from soulspot.application.use_cases import (
            EnrichMetadataUseCase,
            ImportSpotifyPlaylistUseCase,
            SearchAndDownloadTrackUseCase,
            UseCase,
        )
        print("✓ Use cases imported successfully")
    except Exception as e:
        errors.append(f"✗ Use cases import failed: {e}")
    
    # Test services
    try:
        from soulspot.application.services import TokenManager
        print("✓ Services imported successfully")
    except Exception as e:
        errors.append(f"✗ Services import failed: {e}")
    
    # Test workers
    try:
        from soulspot.application.workers import (
            DownloadWorker,
            JobQueue,
            JobStatus,
            JobType,
            MetadataWorker,
            PlaylistSyncWorker,
        )
        print("✓ Workers imported successfully")
    except Exception as e:
        errors.append(f"✗ Workers import failed: {e}")
    
    # Test cache
    try:
        from soulspot.application.cache import (
            BaseCache,
            MusicBrainzCache,
            SpotifyCache,
            TrackFileCache,
        )
        print("✓ Cache imported successfully")
    except Exception as e:
        errors.append(f"✗ Cache import failed: {e}")
    
    if errors:
        print("\n❌ Validation failed with errors:")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print("\n✅ All Phase 4 components validated successfully!")
        return True


def validate_structure() -> bool:
    """Validate directory structure."""
    print("\nValidating directory structure...")
    
    base_path = Path(__file__).parent / "src" / "soulspot" / "application"
    
    required_dirs = [
        base_path / "use_cases",
        base_path / "services",
        base_path / "workers",
        base_path / "cache",
    ]
    
    required_files = [
        base_path / "__init__.py",
        base_path / "use_cases" / "__init__.py",
        base_path / "use_cases" / "import_spotify_playlist.py",
        base_path / "use_cases" / "search_and_download.py",
        base_path / "use_cases" / "enrich_metadata.py",
        base_path / "services" / "__init__.py",
        base_path / "services" / "token_manager.py",
        base_path / "workers" / "__init__.py",
        base_path / "workers" / "job_queue.py",
        base_path / "workers" / "download_worker.py",
        base_path / "workers" / "metadata_worker.py",
        base_path / "workers" / "playlist_sync_worker.py",
        base_path / "cache" / "__init__.py",
        base_path / "cache" / "base_cache.py",
        base_path / "cache" / "musicbrainz_cache.py",
        base_path / "cache" / "spotify_cache.py",
        base_path / "cache" / "track_file_cache.py",
    ]
    
    errors = []
    
    # Check directories
    for directory in required_dirs:
        if not directory.is_dir():
            errors.append(f"✗ Missing directory: {directory}")
        else:
            print(f"✓ {directory.relative_to(base_path.parent)}")
    
    # Check files
    for file in required_files:
        if not file.is_file():
            errors.append(f"✗ Missing file: {file}")
        else:
            print(f"✓ {file.relative_to(base_path.parent)}")
    
    if errors:
        print("\n❌ Structure validation failed:")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print("\n✅ Directory structure validated successfully!")
        return True


def main() -> int:
    """Main validation function."""
    print("=" * 60)
    print("Phase 4 Implementation Validation")
    print("=" * 60)
    
    structure_ok = validate_structure()
    imports_ok = validate_imports()
    
    print("\n" + "=" * 60)
    if structure_ok and imports_ok:
        print("✅ Phase 4 validation PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ Phase 4 validation FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
