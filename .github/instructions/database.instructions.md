---
applyTo: "alembic/**/*.py,src/soulspot/infrastructure/persistence/**/*.py"
---

# Database & Migration Instructions

## SQLAlchemy Models
Models live in `src/soulspot/infrastructure/persistence/models.py`. Use SQLAlchemy 2.0 syntax:

```python
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from soulspot.infrastructure.persistence.models import Base

class Track(Base):
    __tablename__ = "tracks"
    
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    artist_id: Mapped[str] = mapped_column(ForeignKey("artists.id"))
    
    artist: Mapped["Artist"] = relationship(back_populates="tracks")
```

## Async Database Access
**Always** use async sessions. Never use synchronous SQLAlchemy:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_tracks_by_artist(session: AsyncSession, artist_id: str) -> list[Track]:
    result = await session.execute(
        select(Track).where(Track.artist_id == artist_id)
    )
    return list(result.scalars().all())
```

## Alembic Migrations

### Creating Migrations
```bash
alembic revision --autogenerate -m "Add column_name to table_name"
```

### Migration File Structure
```python
"""Add column_name to table_name

Revision ID: abc123
Revises: def456
Create Date: 2024-01-01 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "abc123"
down_revision = "def456"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("table_name", sa.Column("column_name", sa.String(255)))

def downgrade() -> None:
    op.drop_column("table_name", "column_name")
```

### Running Migrations
```bash
# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current revision
alembic current
```

## Repository Pattern
Repositories are in `src/soulspot/infrastructure/persistence/repositories.py`:

```python
class TrackRepository:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
    
    async def get_by_id(self, track_id: str) -> Track | None:
        async with self._session_factory() as session:
            return await session.get(Track, track_id)
```

## Transaction Management
Let the service layer manage transactions. Repositories should not commit:

```python
# In service layer
async with session.begin():
    await track_repo.add(track)
    await audit_repo.log_action("track_added", track.id)
    # Commits automatically on exit
```

## Database URL
Get from settings, never hardcode:
```python
from soulspot.config import get_settings
settings = get_settings()
db_url = settings.database.url  # async URL with aiosqlite
```

## Alembic env.py
The `env.py` converts async URL to sync for migrations. Don't modify this pattern unless necessary.
