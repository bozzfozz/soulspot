"""Widget template API endpoints for custom widget management."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from soulspot.application.services.widget_template_registry import (
    get_widget_template_registry,
)

router = APIRouter(prefix="/api/widgets/templates", tags=["widget-templates"])


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
