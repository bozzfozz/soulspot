"""UI routes for dashboard widget system."""

from pathlib import Path
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

# Hey future me - compute templates directory relative to THIS file so it works both in
# development (source tree) and production (installed package / Docker container). The old hardcoded
# "src/soulspot/templates" breaks when working directory changes or in containers!
# Path(__file__).parent goes up to api/routers/, then .parent.parent goes to soulspot/,
# then / "templates" gets us to soulspot/templates/. This works anywhere the code runs!
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(prefix="/ui", tags=["dashboard-ui"])


# Hey future me, this renders the main dashboard HTML! page_slug defaults to "default" which is
# the initial page everyone sees. If page doesn't exist, we auto-create it on the fly - nice UX
# but could cause race conditions if multiple users hit it simultaneously. No caching here so every
# request does DB lookups. edit_mode toggle controls whether widget drag-drop is enabled. Templates
# are Jinja2 - make sure dashboard.html exists or this blows up. Page entity uses id=0 for new pages
# which is kinda weird - usually you'd let the DB auto-increment. The commit is inline which means
# if template rendering fails, you still created the page (dangling data).
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


# Yo this loads the widget canvas! page_id can be "default" string OR an int - flexible but type
# unsafe. We manually check and convert which is error-prone. Returns raw HTML string for errors
# instead of proper HTTPException - HTMX expects HTML responses though so this makes sense. We
# get instances then look up widget metadata for each - inefficient, should JOIN in single query.
# widgets_with_meta builds dict manually instead of using Pydantic - more flexible but less type
# safety. The template needs to handle empty widgets list gracefully. edit_mode passed to template
# determines if widgets show edit controls (move/resize/delete buttons).
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


# Listen up, this toggles edit mode for the dashboard! Gets current state from form data which is
# a string "true"/"false" - the == "true" converts to bool. Returns raw HTML with hx-get attribute
# that tells HTMX to reload the canvas. The edit-mode-active CSS class changes styling. This uses
# inline HTML string building which is fragile - typos won't be caught until runtime. Should use
# template. The f-string with nested quotes is hard to read. _session is unused - FastAPI requires
# the dependency even if not used (keeps dep injection chain intact). Pretty clever use of HTMX!
@router.post("/dashboard/toggle-edit-mode", response_class=HTMLResponse)
async def toggle_edit_mode(
    request: Request,
    _session: AsyncSession = Depends(get_db_session),
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


# Yo, this opens the widget catalog modal - shows all available widget types users can add to their dashboard!
# Gets all widgets from DB (WidgetRepository.get_all()) and renders them in a modal template. page_id defaults
# to None but gets coerced to 1 in template ({"page_id": page_id or 1}) - that's a weird fallback. Why not
# require page_id or get it from context? The catalog shows widget name, description, preview, etc. User clicks
# a widget -> calls add_widget_instance. Template is partials/widget_catalog_modal.html - check that for UI!
@router.get("/widgets/catalog", response_class=HTMLResponse)
async def widget_catalog(
    request: Request,
    page_id: int | None = None,
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


# WATCH OUT: This creates a new widget instance from form data! page_id defaults to 1 which might
# not exist - should validate. The type: ignore is needed because FormData.get() returns str | None
# and we're converting to int without checking. Could crash if form is malformed. Finding next_row
# by max() is clever but assumes rows are sequential - if you delete a middle row, gaps stay.
# Default span_cols=6 means half-width which is reasonable. id=0 for new instance is weird again.
# Returns HTML that triggers HTMX to reload the canvas - slick but means widget won't appear until
# reload completes. Consider optimistic updates? Commits immediately which is good for consistency.
@router.post("/widgets/instances", response_class=HTMLResponse)
async def add_widget_instance(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Add a widget instance to a page."""
    form_data = await request.form()
    page_id = int(form_data.get("page_id", 1))  # type: ignore[arg-type]
    widget_type = str(form_data.get("widget_type", ""))

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


# Hey future me, DELETE widget instance! Standard soft-delete pattern - removes widget from page but doesn't
# cascade delete widget metadata (that's in WidgetRepository, reusable across instances). Returns empty HTML
# on success - HTMX sees the empty response and removes the widget element from DOM (the hx-target was probably
# the widget div). 404 returns empty HTML too - UI won't show error, widget just stays. Should probably show
# toast notification! Commits immediately. No undo - instance config is GONE.
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


# Heads up! Cool use of path param with {direction} variable! FastAPI parses "move-up", "move-down"
# etc. The direction string is validated manually with if/elif - could use Enum for type safety.
# Widget movement logic is in the entity (move_up/down/left/right methods) which is good domain
# modeling. No bounds checking though - could move widget off-grid! Returns empty HTML on 404 which
# means widget just disappears from UI - might be confusing. The hx-target="#widget-canvas" tells
# HTMX where to inject the response. Reloads entire canvas for single widget move - inefficient but
# simple. Consider just updating the moved widget's position in DOM instead of full reload.
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


# Listen, resizes widget through size cycle! toggle_size() method probably does 4->6->12->4 columns (third-width
# -> half-width -> full-width -> back to third). It's a toggle not a "set size" endpoint - can't jump directly
# to specific size, have to cycle through! Returns full canvas reload HTML which is inefficient - the whole grid
# re-renders just to change one widget's width. Consider returning just the resized widget's updated element
# instead. Good for mobile responsive layouts where you might want widgets full-width on small screens!
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


# Yo, loads widget config modal! Shows form for editing widget instance settings (refresh rate, data source,
# display options, etc). Gets both instance (for current config values) and widget metadata (for config schema/
# validation rules). The template probably renders a dynamic form based on widget.config_schema defining what
# fields are editable. Returns modal HTML - user edits config -> POST to save_widget_config. Template needs
# instance AND widget because instance has values, widget has field definitions!
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


# Listen, this saves widget config from form submission! Converts entire form_data to dict with
# dict(form_data) which is simple but means ALL form fields become config - no validation! User
# could inject arbitrary config keys. update_config method should sanitize. Returns success message
# as inline HTML - should probably reload the widget to show new config. No error handling for
# invalid config values - will just silently save bad data. Consider validating against widget's
# config_schema before saving. The green-600 Tailwind class hardcoded in response HTML is fragile.
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


# Hey, this returns page list for sidebar navigation! Simple read-only endpoint - gets all pages from DB
# and renders them as navigation links. The template (partials/page_list.html) probably generates <a> tags
# with each page's slug. No pagination - assumes you won't have hundreds of dashboard pages (reasonable!).
# The is_default flag on pages determines which shows "default" badge in UI. No auth check here - any user
# sees all pages. Add ACLs if you need per-user dashboards!
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


# Yo, shows "create new page" modal! Dead simple - just renders empty form template. No DB access needed
# since we're not pre-populating anything. User fills name and slug -> POST to create_page. The modal
# template probably has input validation (slug must be URL-safe, name required, etc). This is a GET for
# modal HTML, actual creation is the POST endpoint. Standard HTMX modal pattern!
@router.get("/pages/new", response_class=HTMLResponse)
async def new_page_modal(request: Request) -> Any:
    """Get new page creation modal."""
    return templates.TemplateResponse(
        "partials/new_page_modal.html",
        {"request": request},
    )


# IMPORTANT: Creates new dashboard pages! Gets name and slug from form - both are required (checks
# with if not) but doesn't trim whitespace so "  " would pass. Should use .strip() first. Slug
# uniqueness check is good but there's a race condition - two simultaneous requests could both pass
# the check then both insert. Need unique constraint in DB. Page id=0 again - really should let DB
# handle ID generation. Returns JavaScript redirect in HTML which works but feels hacky - should use
# HTTP redirect header instead. Commits before checking if redirect HTML is valid which could leave
# orphan pages. is_default=False is correct - don't want auto-created pages becoming default!
@router.post("/pages", response_class=HTMLResponse)
async def create_page(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Create a new page."""
    form_data = await request.form()
    name = str(form_data.get("name", ""))
    slug = str(form_data.get("slug", ""))

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


# Yo, deletes dashboard pages! The is_default check prevents deleting the default page which is
# smart - would break the app if default page disappeared. But what about widget instances on the
# page? They'll be orphaned unless there's CASCADE delete in the DB. Should probably delete or move
# widgets to another page first. Returns JavaScript redirect on success - same hacky pattern as
# create_page. Empty HTML response for 404 means the UI won't show any feedback. Consider showing
# toast notification. No confirmation prompt - user could accidentally nuke their custom dashboard!
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
