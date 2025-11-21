"""Widget registry initialization and management."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Widget
from soulspot.infrastructure.persistence.models import WidgetModel

logger = logging.getLogger(__name__)

# Hey future me, this registry is a STATIC list of ALL available widgets! It's defined at module
# level (not in DB yet) and gets loaded into DB at startup via initialize_widget_registry(). Each
# widget is a self-contained UI component for the dashboard - active_jobs shows downloads, spotify_search
# is a search box, etc. The type is the UNIQUE identifier (like CSS class). The template_path points
# to the Jinja2 template (make sure these exist!). default_config holds widget-specific settings
# (refresh_interval, display options, etc.) - users can override these per widget instance. If you
# add a new widget, add it here AND create the template! Don't edit this directly in production - it's
# source code, not config!
# Widget registry - defines all available widgets
WIDGET_REGISTRY: list[dict[str, Any]] = [
    {
        "type": "active_jobs",
        "name": "Active Jobs",
        "template_path": "partials/widgets/active_jobs.html",
        "default_config": {
            "refresh_interval": 5,
            "max_items": 10,
        },
    },
    {
        "type": "spotify_search",
        "name": "Spotify Search",
        "template_path": "partials/widgets/spotify_search.html",
        "default_config": {
            "search_type": "tracks",
            "max_results": 10,
        },
    },
    {
        "type": "missing_tracks",
        "name": "Missing Tracks",
        "template_path": "partials/widgets/missing_tracks.html",
        "default_config": {
            "auto_detect": True,
            "show_found": False,
        },
    },
    {
        "type": "quick_actions",
        "name": "Quick Actions",
        "template_path": "partials/widgets/quick_actions.html",
        "default_config": {
            "actions": ["import", "scan", "fix"],
            "layout": "grid",
        },
    },
    {
        "type": "metadata_manager",
        "name": "Metadata Manager",
        "template_path": "partials/widgets/metadata_manager.html",
        "default_config": {
            "scope": "all",
            "auto_fix": False,
            "max_items": 20,
        },
    },
]


# Listen up, this function SYNCS the registry to the database! Call it at startup, after DB
# migrations. It's IDEMPOTENT - safe to run multiple times. For each widget in WIDGET_REGISTRY,
# it checks if it exists in DB. If yes, UPDATES it (name, template, config might have changed
# in code). If no, INSERTS it. This means: 1) Code is source of truth for widget definitions,
# 2) DB schema changes (new widgets, updated configs) auto-apply on restart. GOTCHA: If you
# DELETE a widget from WIDGET_REGISTRY, it stays in DB! You'd need manual cleanup or a migration.
# The session.commit() is at the END - all or nothing (transaction). Don't call this during
# requests - it's a startup initialization task!
async def initialize_widget_registry(session: AsyncSession) -> None:
    """Initialize widget registry in database.

    Registers all widgets defined in WIDGET_REGISTRY if they don't exist yet.
    Updates existing widgets with latest configuration.
    """
    logger.info("Initializing widget registry...")

    for widget_def in WIDGET_REGISTRY:
        # Check if widget already exists
        stmt = select(WidgetModel).where(WidgetModel.type == widget_def["type"])
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing widget
            existing.name = widget_def["name"]
            existing.template_path = widget_def["template_path"]
            existing.default_config = widget_def["default_config"]
            logger.debug(f"Updated widget: {widget_def['type']}")
        else:
            # Create new widget
            widget = WidgetModel(
                type=widget_def["type"],
                name=widget_def["name"],
                template_path=widget_def["template_path"],
                default_config=widget_def["default_config"],
            )
            session.add(widget)
            logger.debug(f"Registered new widget: {widget_def['type']}")

    await session.commit()
    logger.info(f"Widget registry initialized with {len(WIDGET_REGISTRY)} widgets")


# Yo, simple widget lookup by type! Returns None if not found (not an error - UI can handle
# missing widgets gracefully). The scalar_one_or_none() ensures we get exactly ONE widget or
# None - if somehow there are duplicates (shouldn't happen - type is unique!), it raises. Use
# this when rendering the widget picker or validating widget_type from user input. No caching
# here - if widgets change frequently, add a cache layer!
async def get_widget_by_type(session: AsyncSession, widget_type: str) -> Widget | None:
    """Get a widget from registry by type."""
    stmt = select(WidgetModel).where(WidgetModel.type == widget_type)
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()

    if not model:
        return None

    return Widget(
        id=model.id,
        type=model.type,
        name=model.name,
        template_path=model.template_path,
        default_config=model.default_config,
    )


# Hey future me, this lists ALL registered widgets, sorted alphabetically by name. Use this
# for the widget picker UI ("Available Widgets" dropdown). The order_by(WidgetModel.name) makes
# it user-friendly - widgets appear in a predictable order, not random DB insertion order. The
# scalars().all() unpacks the result rows. This is a small table (5-20 widgets typically), so
# no pagination needed. If you ever have 100+ widgets, add limit/offset!
async def get_all_widgets(session: AsyncSession) -> list[Widget]:
    """Get all widgets from registry."""
    stmt = select(WidgetModel).order_by(WidgetModel.name)
    result = await session.execute(stmt)
    models = result.scalars().all()

    return [
        Widget(
            id=model.id,
            type=model.type,
            name=model.name,
            template_path=model.template_path,
            default_config=model.default_config,
        )
        for model in models
    ]
