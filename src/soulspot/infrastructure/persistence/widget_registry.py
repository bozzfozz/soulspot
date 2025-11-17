"""Widget registry initialization and management."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Widget
from soulspot.infrastructure.persistence.models import WidgetModel

logger = logging.getLogger(__name__)

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
