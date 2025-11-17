"""UI routes for dashboard widget system."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.domain.entities import Page, WidgetInstance
from soulspot.infrastructure.persistence.repositories import (
    PageRepository,
    WidgetInstanceRepository,
    WidgetRepository,
)

templates = Jinja2Templates(directory="src/soulspot/templates")

router = APIRouter(prefix="/ui", tags=["dashboard-ui"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    page_slug: str = "default",
    edit_mode: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Render dashboard page."""
    page_repo = PageRepository(session)

    # Get page by slug or default
    if page_slug == "default":
        page = await page_repo.get_default()
    else:
        page = await page_repo.get_by_slug(page_slug)

    if not page:
        # Create default page if it doesn't exist
        page = Page(
            id=0,
            name="My Dashboard",
            slug="default",
            is_default=True,
        )
        await page_repo.add(page)
        await session.commit()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "page": page,
            "edit_mode": edit_mode,
        },
    )


@router.get("/pages/{page_id}/canvas", response_class=HTMLResponse)
async def get_canvas(
    request: Request,
    page_id: int | str,
    edit_mode: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Get widget canvas HTML for a page."""
    page_repo = PageRepository(session)
    instance_repo = WidgetInstanceRepository(session)
    widget_repo = WidgetRepository(session)

    # Get page
    if page_id == "default":
        page = await page_repo.get_default()
    else:
        page = await page_repo.get_by_id(int(page_id))

    if not page:
        return HTMLResponse(
            '<div class="text-center py-8 text-red-500">Page not found</div>'
        )

    # Get widget instances for page
    instances = await instance_repo.get_by_page(page.id)

    # Get widget metadata for each instance
    widgets_with_meta = []
    for instance in instances:
        widget = await widget_repo.get_by_type(instance.widget_type)
        if widget:
            widgets_with_meta.append(
                {
                    "instance": instance,
                    "widget": widget,
                }
            )

    return templates.TemplateResponse(
        "partials/widget_canvas.html",
        {
            "request": request,
            "page": page,
            "widgets": widgets_with_meta,
            "edit_mode": edit_mode,
        },
    )


@router.post("/dashboard/toggle-edit-mode", response_class=HTMLResponse)
async def toggle_edit_mode(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Toggle edit mode for dashboard."""
    # Get current edit mode from form data or query param
    form_data = await request.form()
    current_edit_mode = form_data.get("edit_mode", "false") == "true"
    new_edit_mode = not current_edit_mode

    # Return updated dashboard container
    return HTMLResponse(
        f'<div id="dashboard-container" class="{"edit-mode-active" if new_edit_mode else ""}" '
        f'hx-get="/api/ui/pages/default/canvas?edit_mode={str(new_edit_mode).lower()}" '
        f'hx-trigger="load" hx-swap="innerHTML"></div>'
    )


@router.get("/widgets/catalog", response_class=HTMLResponse)
async def widget_catalog(
    request: Request,
    page_id: int = None,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Get widget catalog modal."""
    widget_repo = WidgetRepository(session)
    widgets = await widget_repo.get_all()

    return templates.TemplateResponse(
        "partials/widget_catalog_modal.html",
        {
            "request": request,
            "widgets": widgets,
            "page_id": page_id or 1,
        },
    )


@router.post("/widgets/instances", response_class=HTMLResponse)
async def add_widget_instance(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Add a widget instance to a page."""
    form_data = await request.form()
    page_id = int(form_data.get("page_id", 1))
    widget_type = form_data.get("widget_type", "")

    instance_repo = WidgetInstanceRepository(session)
    widget_repo = WidgetRepository(session)

    # Get widget metadata
    widget = await widget_repo.get_by_type(widget_type)
    if not widget:
        return HTMLResponse(
            '<div class="text-red-500">Widget not found</div>', status_code=404
        )

    # Find next available position
    existing_instances = await instance_repo.get_by_page(page_id)
    next_row = 0
    if existing_instances:
        next_row = max(inst.position_row for inst in existing_instances) + 1

    # Create widget instance
    instance = WidgetInstance(
        id=0,
        page_id=page_id,
        widget_type=widget_type,
        position_row=next_row,
        position_col=0,
        span_cols=6,  # Default half-width
        config=widget.default_config,
    )

    await instance_repo.add(instance)
    await session.commit()

    # Return updated canvas
    return HTMLResponse(
        f'<div hx-get="/api/ui/pages/{page_id}/canvas?edit_mode=true" '
        f'hx-trigger="load" hx-swap="outerHTML"></div>'
    )


@router.delete("/widgets/instances/{instance_id}", response_class=HTMLResponse)
async def delete_widget_instance(
    instance_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Delete a widget instance."""
    instance_repo = WidgetInstanceRepository(session)

    instance = await instance_repo.get_by_id(instance_id)
    if not instance:
        return HTMLResponse("", status_code=404)

    await instance_repo.delete(instance_id)
    await session.commit()

    # Return empty (widget will be removed from DOM)
    return HTMLResponse("")


@router.post(
    "/widgets/instances/{instance_id}/move-{direction}", response_class=HTMLResponse
)
async def move_widget(
    instance_id: int,
    direction: str,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Move widget in specified direction."""
    instance_repo = WidgetInstanceRepository(session)

    instance = await instance_repo.get_by_id(instance_id)
    if not instance:
        return HTMLResponse("", status_code=404)

    # Apply movement
    if direction == "up":
        instance.move_up()
    elif direction == "down":
        instance.move_down()
    elif direction == "left":
        instance.move_left()
    elif direction == "right":
        instance.move_right()
    else:
        return HTMLResponse("Invalid direction", status_code=400)

    await instance_repo.update(instance)
    await session.commit()

    # Return updated canvas
    page_id = instance.page_id
    return HTMLResponse(
        f'<div hx-get="/api/ui/pages/{page_id}/canvas?edit_mode=true" '
        f'hx-trigger="load" hx-target="#widget-canvas" hx-swap="innerHTML"></div>'
    )


@router.post("/widgets/instances/{instance_id}/resize", response_class=HTMLResponse)
async def resize_widget(
    instance_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Toggle widget size."""
    instance_repo = WidgetInstanceRepository(session)

    instance = await instance_repo.get_by_id(instance_id)
    if not instance:
        return HTMLResponse("", status_code=404)

    # Toggle size (4 -> 6 -> 12 -> 4)
    instance.toggle_size()

    await instance_repo.update(instance)
    await session.commit()

    # Return updated canvas
    page_id = instance.page_id
    return HTMLResponse(
        f'<div hx-get="/api/ui/pages/{page_id}/canvas?edit_mode=true" '
        f'hx-trigger="load" hx-target="#widget-canvas" hx-swap="innerHTML"></div>'
    )


@router.get("/widgets/instances/{instance_id}/config", response_class=HTMLResponse)
async def get_widget_config(
    request: Request,
    instance_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Get widget configuration modal."""
    instance_repo = WidgetInstanceRepository(session)
    widget_repo = WidgetRepository(session)

    instance = await instance_repo.get_by_id(instance_id)
    if not instance:
        return HTMLResponse("Widget not found", status_code=404)

    widget = await widget_repo.get_by_type(instance.widget_type)

    return templates.TemplateResponse(
        "partials/widget_config_modal.html",
        {
            "request": request,
            "instance": instance,
            "widget": widget,
        },
    )


@router.post("/widgets/instances/{instance_id}/config", response_class=HTMLResponse)
async def save_widget_config(
    instance_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Save widget configuration."""
    instance_repo = WidgetInstanceRepository(session)

    instance = await instance_repo.get_by_id(instance_id)
    if not instance:
        return HTMLResponse("Widget not found", status_code=404)

    form_data = await request.form()
    # Update config from form data
    config = dict(form_data)
    instance.update_config(config)

    await instance_repo.update(instance)
    await session.commit()

    return HTMLResponse('<div class="text-green-600">Configuration saved!</div>')


@router.get("/pages/list", response_class=HTMLResponse)
async def list_pages(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Get list of pages for sidebar."""
    page_repo = PageRepository(session)
    pages = await page_repo.get_all()

    return templates.TemplateResponse(
        "partials/page_list.html",
        {
            "request": request,
            "pages": pages,
        },
    )


@router.get("/pages/new", response_class=HTMLResponse)
async def new_page_modal(request: Request) -> Any:
    """Get new page creation modal."""
    return templates.TemplateResponse(
        "partials/new_page_modal.html",
        {"request": request},
    )


@router.post("/pages", response_class=HTMLResponse)
async def create_page(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Create a new page."""
    form_data = await request.form()
    name = form_data.get("name", "")
    slug = form_data.get("slug", "")

    if not name or not slug:
        return HTMLResponse("Name and slug are required", status_code=400)

    page_repo = PageRepository(session)

    # Check if slug already exists
    existing = await page_repo.get_by_slug(slug)
    if existing:
        return HTMLResponse("Page with this slug already exists", status_code=400)

    page = Page(
        id=0,
        name=name,
        slug=slug,
        is_default=False,
    )

    await page_repo.add(page)
    await session.commit()

    # Redirect to new page
    return HTMLResponse(
        f'<script>window.location.href="/api/ui/dashboard?page_slug={slug}";</script>'
    )


@router.delete("/pages/{page_id}", response_class=HTMLResponse)
async def delete_page(
    page_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Delete a page."""
    page_repo = PageRepository(session)

    page = await page_repo.get_by_id(page_id)
    if not page:
        return HTMLResponse("", status_code=404)

    # Don't allow deleting default page
    if page.is_default:
        return HTMLResponse("Cannot delete default page", status_code=400)

    await page_repo.delete(page_id)
    await session.commit()

    # Redirect to default page
    return HTMLResponse('<script>window.location.href="/api/ui/dashboard";</script>')
