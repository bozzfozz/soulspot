"""Automation API endpoints - aggregates all automation sub-routers.

Hey future me - this is the AGGREGATOR router for automation features!
ALL endpoints are now in dedicated sub-routers:
- automation_watchlists.py: Watchlist CRUD + check releases
- automation_quality_upgrades.py: Quality upgrade candidates
- automation_filters.py: Download filter rules
- automation_rules.py: Automation workflow rules

REFACTORED Jan 2026: Removed deprecated routers (discography, followed_artists).
These features are now handled by UnifiedLibraryWorker and WatchlistService.
"""

import logging

from fastapi import APIRouter

from soulspot.api.routers.automation_filters import router as filters_router
from soulspot.api.routers.automation_quality_upgrades import (
    router as quality_upgrades_router,
)
from soulspot.api.routers.automation_rules import router as rules_router
from soulspot.api.routers.automation_watchlists import router as watchlists_router

logger = logging.getLogger(__name__)

# Main router that aggregates all automation sub-routers
router = APIRouter(prefix="/automation", tags=["automation"])

# Include all sub-routers
router.include_router(watchlists_router)
router.include_router(quality_upgrades_router)
router.include_router(filters_router)
router.include_router(rules_router)

# That's it! All endpoints are in the sub-routers.
# Check the individual router files for endpoint documentation.
