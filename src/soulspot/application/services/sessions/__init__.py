"""Session Services Package - Token and session management services.

Hey future me - this is the REORGANIZED session services package!

Phase 8 of SERVICE_CONSOLIDATION_PLAN_COMPLETE.md:
- Reorganized session services into logical sessions/ subpackage
- Token management and session storage in one place
- Cleaner imports and better organization

Services in this package:
- token_manager.py: TokenManager, DatabaseTokenManager (OAuth token lifecycle)
- session_store.py: Session, SessionStore (browser session management)

Key Concepts:
- TokenManager: In-memory token storage for user sessions
- DatabaseTokenManager: DB-backed token storage for background workers
- SessionStore: Browser session management (session_id, state, code_verifier)

All services are imported from the old locations for backward compatibility.
New code should import from this package:
    from soulspot.application.services.sessions import TokenManager, SessionStore

Architecture:
    Browser → SessionStore (session_id cookie) → TokenManager (OAuth tokens)
                                               → DatabaseTokenManager (for workers)
"""

from __future__ import annotations

# Token Management
from soulspot.application.services.token_manager import (
    DatabaseTokenManager,
    TokenInfo,
    TokenManager,
    TokenStatus,
)

# Session Management
from soulspot.application.services.session_store import (
    Session,
    SessionStore,
)

__all__ = [
    # Token Management
    "TokenManager",
    "DatabaseTokenManager",
    "TokenInfo",
    "TokenStatus",
    # Session Management
    "Session",
    "SessionStore",
]
