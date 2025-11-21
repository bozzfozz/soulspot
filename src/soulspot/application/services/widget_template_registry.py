"""Widget template registry service for discovering and managing widget templates."""

import logging
from functools import lru_cache
from pathlib import Path

from soulspot.domain.entities.widget_template import (
    WidgetTemplate,
    WidgetTemplateConfig,
)

logger = logging.getLogger(__name__)


class WidgetTemplateRegistry:
    """Registry for widget templates."""

    def __init__(self, template_dir: Path | None = None):
        """Initialize widget template registry.

        Args:
            template_dir: Directory containing widget template files
        """
        self.templates: dict[str, WidgetTemplate] = {}
        self.template_dir = template_dir or Path(
            "src/soulspot/templates/widget_templates"
        )

        # Initialize with built-in system widgets
        self._register_system_widgets()

    # Hey this registers built-in system widgets! Hard-coded widget definitions for Active Jobs, Spotify
    # Search, Missing Tracks, Quick Actions, and Metadata Manager. Each has WidgetTemplateConfig with
    # name, description, template path, icon, category, config schema, etc. The data_endpoint tells widget
    # where to fetch content. supports_sse=True means widget subscribes to real-time updates via SSE.
    # poll_interval determines refresh frequency (0 = no polling, 5 = every 5 seconds). is_system=True
    # prevents deletion of these core widgets. default_config provides sensible defaults. config_schema
    # defines what's configurable (select, number, array, etc). This runs in __init__ so widgets are
    # available immediately. Logs count at end for debugging. Consider loading from JSON files instead
    # of hard-coding? Makes customization easier without code changes.
    def _register_system_widgets(self) -> None:
        """Register built-in system widgets."""
        # Active Jobs Widget
        self.register(
            WidgetTemplate(
                id="active_jobs",
                type="active_jobs",
                config=WidgetTemplateConfig(
                    name="Active Jobs",
                    description="Shows active download jobs with real-time updates",
                    version="1.0.0",
                    author="SoulSpot Team",
                    template_path="partials/widgets/active_jobs.html",
                    icon="download",
                    category="monitoring",
                    supports_config=False,
                    default_span_cols=6,
                    min_span_cols=4,
                    max_span_cols=12,
                    data_endpoint="/api/ui/widgets/active-jobs/content",
                    supports_sse=True,
                    sse_events=["downloads_update"],
                    poll_interval=5,
                    requires_auth=False,
                    tags=["downloads", "monitoring", "real-time"],
                ),
                is_system=True,
            )
        )

        # Spotify Search Widget
        self.register(
            WidgetTemplate(
                id="spotify_search",
                type="spotify_search",
                config=WidgetTemplateConfig(
                    name="Spotify Search",
                    description="Search for tracks on Spotify and quickly download them",
                    version="1.0.0",
                    author="SoulSpot Team",
                    template_path="partials/widgets/spotify_search.html",
                    icon="search",
                    category="search",
                    supports_config=True,
                    config_schema={
                        "default_search_type": {
                            "type": "select",
                            "options": ["track", "album", "artist"],
                            "default": "track",
                        },
                        "default_limit": {
                            "type": "number",
                            "min": 5,
                            "max": 50,
                            "default": 10,
                        },
                    },
                    default_config={
                        "default_search_type": "track",
                        "default_limit": 10,
                    },
                    default_span_cols=6,
                    min_span_cols=6,
                    max_span_cols=12,
                    data_endpoint="/api/ui/widgets/spotify-search/content",
                    supports_sse=False,
                    poll_interval=0,
                    requires_auth=True,
                    tags=["spotify", "search", "music"],
                ),
                is_system=True,
            )
        )

        # Missing Tracks Widget
        self.register(
            WidgetTemplate(
                id="missing_tracks",
                type="missing_tracks",
                config=WidgetTemplateConfig(
                    name="Missing Tracks",
                    description="Shows tracks from playlists that are not yet downloaded",
                    version="1.0.0",
                    author="SoulSpot Team",
                    template_path="partials/widgets/missing_tracks.html",
                    icon="exclamation-circle",
                    category="monitoring",
                    supports_config=True,
                    config_schema={
                        "max_playlists": {
                            "type": "number",
                            "min": 1,
                            "max": 20,
                            "default": 10,
                        },
                    },
                    default_config={"max_playlists": 10},
                    default_span_cols=6,
                    min_span_cols=6,
                    max_span_cols=12,
                    data_endpoint="/api/ui/widgets/missing-tracks/content",
                    supports_sse=False,
                    poll_interval=30,
                    requires_auth=False,
                    tags=["playlists", "monitoring", "tracks"],
                ),
                is_system=True,
            )
        )

        # Quick Actions Widget
        self.register(
            WidgetTemplate(
                id="quick_actions",
                type="quick_actions",
                config=WidgetTemplateConfig(
                    name="Quick Actions",
                    description="Configurable quick action buttons for common tasks",
                    version="1.0.0",
                    author="SoulSpot Team",
                    template_path="partials/widgets/quick_actions.html",
                    icon="lightning-bolt",
                    category="utility",
                    supports_config=True,
                    config_schema={
                        "actions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "endpoint": {"type": "string"},
                                    "method": {
                                        "type": "string",
                                        "enum": ["GET", "POST"],
                                    },
                                    "icon": {"type": "string"},
                                },
                            },
                        },
                    },
                    default_config={
                        "actions": [
                            {
                                "label": "Sync All Playlists",
                                "endpoint": "/api/playlists/sync-all",
                                "method": "POST",
                                "icon": "refresh",
                            },
                        ],
                    },
                    default_span_cols=4,
                    min_span_cols=4,
                    max_span_cols=8,
                    data_endpoint="/api/ui/widgets/quick-actions/content",
                    supports_sse=False,
                    poll_interval=0,
                    requires_auth=False,
                    tags=["utility", "actions"],
                ),
                is_system=True,
            )
        )

        # Metadata Manager Widget
        self.register(
            WidgetTemplate(
                id="metadata_manager",
                type="metadata_manager",
                config=WidgetTemplateConfig(
                    name="Metadata Manager",
                    description="Detect and fix metadata issues in your library",
                    version="1.0.0",
                    author="SoulSpot Team",
                    template_path="partials/widgets/metadata_manager.html",
                    icon="tag",
                    category="management",
                    supports_config=True,
                    config_schema={
                        "default_filter": {
                            "type": "select",
                            "options": ["all", "missing", "incorrect"],
                            "default": "all",
                        },
                        "max_issues": {
                            "type": "number",
                            "min": 10,
                            "max": 100,
                            "default": 20,
                        },
                    },
                    default_config={
                        "default_filter": "all",
                        "max_issues": 20,
                    },
                    default_span_cols=6,
                    min_span_cols=6,
                    max_span_cols=12,
                    data_endpoint="/api/ui/widgets/metadata-manager/content",
                    supports_sse=False,
                    poll_interval=60,
                    requires_auth=False,
                    tags=["metadata", "management", "library"],
                ),
                is_system=True,
            )
        )

        logger.info(f"Registered {len(self.templates)} system widgets")

    # Listen, widget registry methods - CRUD for widget templates
    # WHY log warning on overwrite? Dev probably made mistake, help debug
    # is_system check prevents deleting built-in widgets (safety)
    def register(self, template: WidgetTemplate) -> None:
        """Register a widget template.

        Args:
            template: Widget template to register
        """
        if template.id in self.templates:
            logger.warning(f"Overwriting existing template: {template.id}")

        self.templates[template.id] = template
        logger.debug(
            f"Registered widget template: {template.id} ({template.config.name})"
        )

    def unregister(self, template_id: str) -> bool:
        """Unregister a widget template.

        Args:
            template_id: ID of template to unregister

        Returns:
            True if unregistered, False if not found
        """
        if template_id in self.templates:
            # Don't allow unregistering system widgets
            if self.templates[template_id].is_system:
                logger.warning(f"Cannot unregister system widget: {template_id}")
                return False

            del self.templates[template_id]
            logger.info(f"Unregistered widget template: {template_id}")
            return True
        return False

    def get(self, template_id: str) -> WidgetTemplate | None:
        """Get a widget template by ID.

        Args:
            template_id: Template ID

        Returns:
            Widget template or None if not found
        """
        return self.templates.get(template_id)

    def get_all(self, enabled_only: bool = False) -> list[WidgetTemplate]:
        """Get all registered templates.

        Args:
            enabled_only: If True, only return enabled templates

        Returns:
            List of widget templates
        """
        templates = list(self.templates.values())

        if enabled_only:
            templates = [t for t in templates if t.is_enabled]

        return templates

    def get_by_category(self, category: str) -> list[WidgetTemplate]:
        """Get templates by category.

        Args:
            category: Category name

        Returns:
            List of matching templates
        """
        return [
            t
            for t in self.templates.values()
            if t.config.category == category and t.is_enabled
        ]

    # Listen, searches for widget templates! Filters by enabled status first (no point showing disabled).
    # Then applies query search on name and description (case-insensitive via .lower()). Category filter
    # is exact match (case-sensitive!). Tags filter uses "any match" logic - template included if it has
    # ANY of the requested tags. Could also do "all match" (template must have ALL tags) - consider making
    # this configurable? The if conditions cascade - each narrows results further. Returns empty list if
    # no matches. No pagination - could return all templates if search is broad! Consider limiting results.
    # Query matching on both name and description is good UX - cast wide net. The query_lower optimization
    # avoids repeated .lower() calls in comprehension. Clean, simple search implementation.
    def search(
        self,
        query: str = "",
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> list[WidgetTemplate]:
        """Search for templates.

        Args:
            query: Search query (matches name and description)
            category: Filter by category
            tags: Filter by tags (any match)

        Returns:
            List of matching templates
        """
        results = list(self.templates.values())

        # Filter by enabled status
        results = [t for t in results if t.is_enabled]

        # Filter by query
        if query:
            query_lower = query.lower()
            results = [
                t
                for t in results
                if query_lower in t.config.name.lower()
                or query_lower in t.config.description.lower()
            ]

        # Filter by category
        if category:
            results = [t for t in results if t.config.category == category]

        # Filter by tags
        if tags:
            results = [t for t in results if any(tag in t.config.tags for tag in tags)]

        return results

    # Hey, template file discovery - loads custom widgets from JSON files
    # WHY template_dir? Allows users to add custom widgets without code changes
    # glob("*.json") finds all JSON files in directory
    # Per-file exception handling - one bad template doesn't break loading others
    def discover_templates(self) -> int:
        """Discover and load custom templates from template directory.

        Returns:
            Number of templates discovered
        """
        if not self.template_dir.exists():
            logger.warning(f"Template directory not found: {self.template_dir}")
            return 0

        count = 0
        for template_file in self.template_dir.glob("*.json"):
            try:
                template = WidgetTemplate.from_file(template_file)
                self.register(template)
                count += 1
            except Exception as e:
                logger.error(f"Error loading template {template_file}: {e}")

        logger.info(f"Discovered {count} custom widget templates")
        return count


# Listen, global registry singleton - cached with lru_cache decorator
# WHY lru_cache? Ensures only ONE registry instance across app (singleton pattern)
# The decorator makes this thread-safe and prevents re-instantiation
# Automatically discovers custom templates on first call
@lru_cache
def get_widget_template_registry() -> WidgetTemplateRegistry:
    """Get the global widget template registry (thread-safe).

    Returns:
        WidgetTemplateRegistry instance
    """
    registry = WidgetTemplateRegistry()
    # Try to discover custom templates
    registry.discover_templates()
    return registry
