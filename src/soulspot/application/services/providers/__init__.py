"""Provider Services Package - Multi-provider sync and authentication services.

Hey future me - this is the REORGANIZED provider services package!

Phase 7 of SERVICE_CONSOLIDATION_PLAN_COMPLETE.md:
- Reorganized provider services into logical providers/ subpackage
- All provider-specific services in one place
- Cleaner imports and better organization

Services in this package:
- mapping_service.py: ProviderMappingService (ID translation: external → internal)
- sync_orchestrator.py: ProviderSyncOrchestrator (multi-provider coordination)
- spotify_sync_service.py: SpotifySyncService (Spotify data sync)
- deezer_sync_service.py: DeezerSyncService (Deezer data sync)
- spotify_auth_service.py: SpotifyAuthService (Spotify OAuth)
- deezer_auth_service.py: DeezerAuthService (Deezer OAuth)

All services are imported from the old locations for backward compatibility.
New code should import from this package:
    from soulspot.application.services.providers import ProviderSyncOrchestrator

Architecture:
    Routes → ProviderSyncOrchestrator → SpotifySyncService + DeezerSyncService
                                      → ProviderMappingService (ID translation)
    
    Auth: Routes → SpotifyAuthService / DeezerAuthService → OAuth flow
"""

from __future__ import annotations

# Mapping Service - External ID → Internal UUID translation
from soulspot.application.services.provider_mapping_service import (
    ProviderMappingService,
)

# Sync Orchestrator - Multi-provider coordination
from soulspot.application.services.provider_sync_orchestrator import (
    AggregatedSyncResult,
    ProviderSyncOrchestrator,
)

# Spotify Services
from soulspot.application.services.spotify_sync_service import SpotifySyncService
from soulspot.application.services.spotify_auth_service import (
    AuthUrlResult as SpotifyAuthUrlResult,
    SpotifyAuthService,
    TokenResult as SpotifyTokenResult,
)

# Deezer Services
from soulspot.application.services.deezer_sync_service import DeezerSyncService
from soulspot.application.services.deezer_auth_service import (
    DeezerAuthService,
    DeezerAuthUrlResult,
    DeezerTokenResult,
)

__all__ = [
    # Orchestration
    "ProviderMappingService",
    "ProviderSyncOrchestrator",
    "AggregatedSyncResult",
    # Spotify
    "SpotifySyncService",
    "SpotifyAuthService",
    "SpotifyAuthUrlResult",
    "SpotifyTokenResult",
    # Deezer
    "DeezerSyncService",
    "DeezerAuthService",
    "DeezerAuthUrlResult",
    "DeezerTokenResult",
]
