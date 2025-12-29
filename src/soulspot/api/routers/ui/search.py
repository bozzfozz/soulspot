"""Search UI routes.

Hey future me - this module contains all search-related UI routes:
- Advanced search page (/search)
- Quick search partial for header (/search/quick)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from soulspot.api.dependencies import get_db_session
from soulspot.api.routers.ui._shared import templates
from soulspot.infrastructure.persistence.models import (
    ArtistModel,
    PlaylistModel,
    TrackModel,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
async def search(request: Request) -> Any:
    """Advanced search page."""
    return templates.TemplateResponse(request, "search.html")


# Hey future me - this is the HTMX quick-search endpoint for the header search bar! It returns a
# dropdown partial with local library results (tracks, artists, playlists). NOT Spotify search -
# that would be slow and require auth. The q param comes from input field via hx-get. We search
# library only if query is at least 2 chars to avoid noise. Results limited to 5 per type for
# quick display. The partial renders into #search-results dropdown in base.html header.
@router.get("/search/quick", response_class=HTMLResponse)
async def quick_search(
    request: Request,
    q: str = "",
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Quick search partial for header search bar.

    Searches local library (tracks, artists, playlists) and returns
    HTML partial for HTMX dropdown. Minimum query length is 2 characters.

    Args:
        request: FastAPI request
        q: Search query string
        session: Database session

    Returns:
        HTML partial with search results dropdown
    """
    results: list[dict[str, Any]] = []
    query = q.strip()

    if len(query) >= 2:
        search_term = f"%{query}%"

        # Search tracks (title or artist name)
        stmt = (
            select(TrackModel)
            .join(TrackModel.artist)
            .options(joinedload(TrackModel.artist))
            .where(
                or_(
                    TrackModel.title.ilike(search_term),
                    ArtistModel.name.ilike(search_term),
                )
            )
            .limit(5)
        )
        result = await session.execute(stmt)
        tracks = result.scalars().all()

        for track in tracks:
            results.append(
                {
                    "type": "track",
                    "name": track.title,
                    "subtitle": track.artist.name if track.artist else "Unknown Artist",
                    "url": f"/library/tracks/{track.id}",
                }
            )

        # Search playlists by name
        stmt = (
            select(PlaylistModel).where(PlaylistModel.name.ilike(search_term)).limit(5)
        )
        result = await session.execute(stmt)
        playlists = result.scalars().all()

        for playlist in playlists:
            results.append(
                {
                    "type": "playlist",
                    "name": playlist.name,
                    "subtitle": "Playlist",
                    "url": f"/playlists/{playlist.id}",
                }
            )

        # Sort: exact matches first, then by type (playlist > track)
        type_order = {"playlist": 0, "artist": 1, "album": 2, "track": 3}
        results.sort(
            key=lambda x: (
                0 if x["name"].lower() == query.lower() else 1,
                type_order.get(x["type"], 99),
            )
        )

    return templates.TemplateResponse(
        request,
        "partials/quick_search_results.html",
        context={"query": query, "results": results},
    )
