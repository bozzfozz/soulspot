# Artwork Implementation

**Category:** Library Management  
**Status:** ✅ Implemented  
**Last Updated:** 2025-11-28  
**Related Docs:** [UI Patterns](../09-ui/ui-patterns.md) | [Data Models](./data-models.md)

---

## Overview

Library UI displays artist and album artwork directly from Spotify CDN URLs. No local storage for library artwork needed — minimizes storage and avoids duplicates.

---

## Artwork Sources

| Entity | DB Field | Source | Format |
|--------|----------|--------|--------|
| **Artist** | `image_url` | Spotify CDN | ~320x320 JPEG |
| **Album** | `artwork_url` | Spotify CDN | ~300-640px JPEG |
| **Track** | – | Inherits from Album | – |

### Spotify CDN URLs

```
https://i.scdn.co/image/{image_id}
```

- URLs are stable and cacheable
- Various sizes available (64, 300, 640px)
- No authentication needed

---

## Fallback Chain

```
1. Spotify CDN URL (artwork_url / image_url)
        ↓ (not available)
2. Placeholder (Icon or letter avatar)
        ↓ (LATER: Optional)
3. cover.jpg from album folder
        ↓ (LATER: Optional)
4. MusicBrainz / CoverArtArchive
```

**Currently Implemented:** Level 1 + 2

---

## Database Schema

### ArtistModel

```python
class ArtistModel(Base):
    __tablename__ = "artists"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ...
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

---

### AlbumModel

```python
class AlbumModel(Base):
    __tablename__ = "albums"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # ...
    artwork_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

---

## API Routes

### GET /ui/library/artists

```python
@router.get("/library/artists")
async def library_artists(request: Request) -> Any:
    """Library artists browser page."""
    # SQL query with aggregation
    stmt = (
        select(ArtistModel, track_count, album_count)
        .outerjoin(...)
    )
    
    # Template data with image_url
    artists = [
        {
            "name": artist.name,
            "track_count": track_count or 0,
            "album_count": album_count or 0,
            "image_url": artist.image_url,  # Spotify CDN URL
        }
        for artist, track_count, album_count in rows
    ]
```

---

### GET /ui/library/albums

```python
@router.get("/library/albums")
async def library_albums(request: Request) -> Any:
    """Library albums browser page."""
    # SQL query with track count
    stmt = (
        select(AlbumModel, track_count)
        .outerjoin(...)
        .options(joinedload(AlbumModel.artist))
    )
    
    # Template data with artwork_url
    albums = [
        {
            "title": album.title,
            "artist": album.artist.name if album.artist else "Unknown",
            "track_count": track_count or 0,
            "year": album.release_year,
            "artwork_url": album.artwork_url,  # Spotify CDN URL
        }
        for album, track_count in rows
    ]
```

---

## Template Patterns

### Album Card with Artwork

```jinja2
<div class="album-cover">
    {% if album.artwork_url %}
    <img src="{{ album.artwork_url }}" alt="{{ album.title }}" loading="lazy">
    {% else %}
    <i class="bi bi-disc"></i>
    {% endif %}
</div>
```

---

### Artist Avatar with Image

```jinja2
<div class="artist-avatar">
    {% if artist.image_url %}
    <img src="{{ artist.image_url }}" alt="{{ artist.name }}" loading="lazy">
    {% else %}
    <div class="letter-avatar">{{ artist.name[0] }}</div>
    {% endif %}
</div>
```

---

## Performance Optimization

### Lazy Loading

```html
<img src="{{ artwork_url }}" loading="lazy">
```

- Browser loads images when visible
- Improves initial page load

---

### CDN Caching

```http
Cache-Control: public, max-age=31536000
```

- Spotify CDN images cached for 1 year
- Reduces bandwidth and latency

---

## Related Documentation

- **[UI Patterns](../09-ui/ui-patterns.md)** - UI component patterns
- **[Data Models](./data-models.md)** - Entity data models

---

**Last Validated:** 2025-11-28  
**Implementation Status:** ✅ Production-ready
