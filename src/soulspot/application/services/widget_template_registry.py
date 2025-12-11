"""
⚠️  DEPRECATED - DO NOT USE ⚠️

This module is DEPRECATED and scheduled for removal.

**Deprecation Date:** November 2025
**Removal Date:** TBD (next major version)
**Migration:** ee19001hhj49_remove_widget_system.py

The widget system was removed from SoulSpot in November 2025:
- Database tables dropped (widgets, widget_instances, pages)
- UI components removed
- All references cleaned up

This file exists only for backwards compatibility and should be DELETED.

**Action Required:**
```bash
git rm src/soulspot/application/services/widget_template_registry.py
git commit -m "Remove deprecated widget_template_registry.py"
```

**Replacement:**
For live updates, use SSE (Server-Sent Events) instead:
- `/api/sse/downloads` - Real-time download updates
- `/api/sse/jobs` - Job queue updates
- `/api/sse/notifications` - System notifications

**References:**
- Deprecation Migration: alembic/versions/ee19001hhj49_remove_widget_system.py
- SSE Implementation: src/soulspot/api/routers/sse.py
- History: docs/history/ (widget system removal)
"""

# DEPRECATED - DO NOT IMPORT
raise DeprecationWarning(
    "widget_template_registry is deprecated and will be removed. "
    "Use SSE endpoints for live updates instead."
)
