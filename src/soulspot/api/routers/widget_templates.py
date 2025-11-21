"""Widget template API endpoints for custom widget management."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from soulspot.application.services.widget_template_registry import (
    get_widget_template_registry,
)

router = APIRouter(prefix="/widgets/templates", tags=["widget-templates"])


class WidgetTemplateResponse(BaseModel):
    """Response model for widget template."""

    id: str
    type: str
    name: str
    description: str
    version: str
    author: str
    template_path: str
    icon: str
    category: str
    supports_config: bool
    config_schema: dict[str, Any]
    default_config: dict[str, Any]
    default_span_cols: int
    min_span_cols: int
    max_span_cols: int
    data_endpoint: str
    supports_sse: bool
    sse_events: list[str]
    poll_interval: int
    requires_auth: bool
    permissions: list[str]
    tags: list[str]
    is_enabled: bool
    is_system: bool


class WidgetTemplateSearchRequest(BaseModel):
    """Request model for widget template search."""

    query: str = ""
    category: str | None = None
    tags: list[str] | None = None


# Hey future me, this lists all available widget templates! enabled_only filter is useful for hiding
# disabled/experimental widgets. get_all returns list from registry which is in-memory dict - fast!
# The big list comprehension unpacks WidgetTemplate into WidgetTemplateResponse Pydantic model which
# provides API schema validation. Accessing t.config.field directly for each field is verbose - could
# use **dict unpacking if field names matched. Icon, category, tags come from config object. is_enabled
# and is_system are top-level template props. This is just a read operation, no mutations, but uses POST
# for search endpoint (inconsistent). No pagination - could return 100s of templates and blow up response!
@router.get("", response_model=list[WidgetTemplateResponse])
async def list_widget_templates(
    enabled_only: bool = False,
) -> list[WidgetTemplateResponse]:
    """List all available widget templates.

    Args:
        enabled_only: If True, only return enabled templates

    Returns:
        List of widget templates
    """
    registry = get_widget_template_registry()
    templates = registry.get_all(enabled_only=enabled_only)

    return [
        WidgetTemplateResponse(
            id=t.id,
            type=t.type,
            name=t.config.name,
            description=t.config.description,
            version=t.config.version,
            author=t.config.author,
            template_path=t.config.template_path,
            icon=t.config.icon,
            category=t.config.category,
            supports_config=t.config.supports_config,
            config_schema=t.config.config_schema,
            default_config=t.config.default_config,
            default_span_cols=t.config.default_span_cols,
            min_span_cols=t.config.min_span_cols,
            max_span_cols=t.config.max_span_cols,
            data_endpoint=t.config.data_endpoint,
            supports_sse=t.config.supports_sse,
            sse_events=t.config.sse_events,
            poll_interval=t.config.poll_interval,
            requires_auth=t.config.requires_auth,
            permissions=t.config.permissions,
            tags=t.config.tags,
            is_enabled=t.is_enabled,
            is_system=t.is_system,
        )
        for t in templates
    ]


# Hey, this gets ONE widget template by ID! registry.get() returns None if not found, then we 404.
# The same verbose unpacking as list endpoint - t.config.field for each property. Could refactor to
# helper function or use Pydantic's from_orm if WidgetTemplate was an ORM model. This is read-only
# operation - templates can't be modified via API (yet). Templates are defined in code or config files.
@router.get("/{template_id}", response_model=WidgetTemplateResponse)
async def get_widget_template(template_id: str) -> WidgetTemplateResponse:
    """Get a specific widget template by ID.

    Args:
        template_id: Template ID

    Returns:
        Widget template

    Raises:
        HTTPException: If template not found
    """
    registry = get_widget_template_registry()
    template = registry.get(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Widget template not found: {template_id}",
        )

    return WidgetTemplateResponse(
        id=template.id,
        type=template.type,
        name=template.config.name,
        description=template.config.description,
        version=template.config.version,
        author=template.config.author,
        template_path=template.config.template_path,
        icon=template.config.icon,
        category=template.config.category,
        supports_config=template.config.supports_config,
        config_schema=template.config.config_schema,
        default_config=template.config.default_config,
        default_span_cols=template.config.default_span_cols,
        min_span_cols=template.config.min_span_cols,
        max_span_cols=template.config.max_span_cols,
        data_endpoint=template.config.data_endpoint,
        supports_sse=template.config.supports_sse,
        sse_events=template.config.sse_events,
        poll_interval=template.config.poll_interval,
        requires_auth=template.config.requires_auth,
        permissions=template.config.permissions,
        tags=template.config.tags,
        is_enabled=template.is_enabled,
        is_system=template.is_system,
    )


# Yo, filter templates by category (e.g., "stats", "media", "system")! get_by_category does simple
# list filtering in Python - registry is in-memory dict so this is fast. Same verbose unpacking as
# other endpoints. Returns empty list if category has no templates (not 404). Category names are
# case-sensitive! "Stats" != "stats". Should normalize or document valid category values.
@router.get("/category/{category}", response_model=list[WidgetTemplateResponse])
async def get_templates_by_category(category: str) -> list[WidgetTemplateResponse]:
    """Get widget templates by category.

    Args:
        category: Category name

    Returns:
        List of matching templates
    """
    registry = get_widget_template_registry()
    templates = registry.get_by_category(category)

    return [
        WidgetTemplateResponse(
            id=t.id,
            type=t.type,
            name=t.config.name,
            description=t.config.description,
            version=t.config.version,
            author=t.config.author,
            template_path=t.config.template_path,
            icon=t.config.icon,
            category=t.config.category,
            supports_config=t.config.supports_config,
            config_schema=t.config.config_schema,
            default_config=t.config.default_config,
            default_span_cols=t.config.default_span_cols,
            min_span_cols=t.config.min_span_cols,
            max_span_cols=t.config.max_span_cols,
            data_endpoint=t.config.data_endpoint,
            supports_sse=t.config.supports_sse,
            sse_events=t.config.sse_events,
            poll_interval=t.config.poll_interval,
            requires_auth=t.config.requires_auth,
            permissions=t.config.permissions,
            tags=t.config.tags,
            is_enabled=t.is_enabled,
            is_system=t.is_system,
        )
        for t in templates
    ]


@router.post("/search", response_model=list[WidgetTemplateResponse])
async def search_widget_templates(
    request: WidgetTemplateSearchRequest,
) -> list[WidgetTemplateResponse]:
    """Search for widget templates.

    Args:
        request: Search parameters

    Returns:
        List of matching templates
    """
    registry = get_widget_template_registry()
    templates = registry.search(
        query=request.query,
        category=request.category,
        tags=request.tags,
    )

    return [
        WidgetTemplateResponse(
            id=t.id,
            type=t.type,
            name=t.config.name,
            description=t.config.description,
            version=t.config.version,
            author=t.config.author,
            template_path=t.config.template_path,
            icon=t.config.icon,
            category=t.config.category,
            supports_config=t.config.supports_config,
            config_schema=t.config.config_schema,
            default_config=t.config.default_config,
            default_span_cols=t.config.default_span_cols,
            min_span_cols=t.config.min_span_cols,
            max_span_cols=t.config.max_span_cols,
            data_endpoint=t.config.data_endpoint,
            supports_sse=t.config.supports_sse,
            sse_events=t.config.sse_events,
            poll_interval=t.config.poll_interval,
            requires_auth=t.config.requires_auth,
            permissions=t.config.permissions,
            tags=t.config.tags,
            is_enabled=t.is_enabled,
            is_system=t.is_system,
        )
        for t in templates
    ]


# Listen, this scans filesystem for new custom widget templates! discover_templates() looks in
# configured directories (e.g., "src/soulspot/templates/widgets/custom/") for template files that
# match naming convention. Parses YAML frontmatter to load widget config. Returns count of NEW
# templates found (doesn't count already-loaded ones). This is idempotent - safe to call multiple
# times. Use this after adding new widget template files to hot-reload them without restarting server!
@router.post("/discover")
async def discover_widget_templates() -> dict[str, Any]:
    """Discover and load custom widget templates.

    Returns:
        Discovery result with count of templates found
    """
    registry = get_widget_template_registry()
    count = registry.discover_templates()

    return {
        "message": f"Discovered {count} widget templates",
        "count": count,
    }


# Hey, this returns unique list of all categories from enabled templates! Uses set comprehension to
# dedupe, then sorted() for alphabetical order. enabled_only=True filters out disabled/experimental
# templates. Returns just strings (category names) not full category objects. Frontend uses this to
# populate category filter dropdown. Categories are freeform strings - no enum validation.
@router.get("/categories/list")
async def list_categories() -> dict[str, list[str]]:
    """List all available widget categories.

    Returns:
        Dictionary with list of categories
    """
    registry = get_widget_template_registry()
    templates = registry.get_all(enabled_only=True)

    categories = sorted({t.config.category for t in templates})

    return {"categories": categories}


# Yo, same as categories but for tags! A widget can have multiple tags (list) vs single category.
# update() merges all tags from all templates into one big set. sorted() for alphabetical order.
# Tags are used for search/filtering. Common tags: "audio", "realtime", "analytics", "experimental".
# No validation - tags are freeform strings defined in widget template config. Returns unique sorted list.
@router.get("/tags/list")
async def list_tags() -> dict[str, list[str]]:
    """List all available widget tags.

    Returns:
        Dictionary with list of tags
    """
    registry = get_widget_template_registry()
    templates = registry.get_all(enabled_only=True)

    # Collect all tags
    all_tags = set()
    for template in templates:
        all_tags.update(template.config.tags)

    return {"tags": sorted(all_tags)}
