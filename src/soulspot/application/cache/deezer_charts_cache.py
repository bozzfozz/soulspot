"""In-memory cache for Deezer Charts data.

Hey future me - dieser Cache ist analog zu NewReleasesCache!
Charts werden NUR im Speicher gehalten, NICHT in der Datenbank!

Das Problem: Charts sind Browse-Content, keine persönliche Library.
Wenn Charts in die soulspot_* Tabellen geschrieben werden, vermischt
sich Browse-Content mit User's Library. Das ist falsch!

Lösung: Charts in-memory cachen. Sie werden:
1. Periodisch vom DeezerSyncWorker aktualisiert
2. Von der Charts-API direkt aus dem Cache gelesen
3. NIEMALS in die Library-Tabellen geschrieben!

Cache-Strategie:
- In-Memory (kein Redis/DB)
- TTL: 60 Minuten (charts update throughout day)
- Bei Cache-Miss: Live-Fetch von Deezer API
- Invalidation: Bei Manual-Refresh oder TTL-Ablauf
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from soulspot.application.services.charts_service import ChartsResult


@dataclass
class DeezerChartsCache:
    """In-memory cache for Deezer charts data.
    
    Hey future me - das ist der Cache für Charts!
    Enthält Tracks, Albums, Artists + Metadata wann gecacht wurde.
    
    WICHTIG: Charts werden NICHT in die DB geschrieben!
    Nur dieser Cache enthält Chart-Daten.
    """
    
    tracks_result: ChartsResult | None = None
    """Cached chart tracks result."""
    
    albums_result: ChartsResult | None = None
    """Cached chart albums result."""
    
    artists_result: ChartsResult | None = None
    """Cached chart artists result."""
    
    cached_at: datetime | None = None
    """When the cache was last updated."""
    
    ttl_minutes: int = 60
    """Time-to-live in minutes before cache is considered stale."""
    
    is_valid: bool = False
    """Whether cache contains valid data."""
    
    sync_errors: list[str] = field(default_factory=list)
    """Errors from the last sync attempt."""
    
    def is_fresh(self) -> bool:
        """Check if cache is still fresh (not expired).
        
        Returns:
            True if cache is valid and not expired
        """
        if not self.is_valid or not self.cached_at:
            return False
        
        age = datetime.now(UTC) - self.cached_at
        return age < timedelta(minutes=self.ttl_minutes)
    
    def get_age_seconds(self) -> int | None:
        """Get cache age in seconds.
        
        Returns:
            Seconds since cache was updated, or None if not cached
        """
        if not self.cached_at:
            return None
        
        age = datetime.now(UTC) - self.cached_at
        return int(age.total_seconds())
    
    def update_tracks(self, result: ChartsResult) -> None:
        """Update cache with new chart tracks result.
        
        Args:
            result: Fresh chart tracks from ChartsService
        """
        self.tracks_result = result
        self._mark_updated(result.errors)
    
    def update_albums(self, result: ChartsResult) -> None:
        """Update cache with new chart albums result.
        
        Args:
            result: Fresh chart albums from ChartsService
        """
        self.albums_result = result
        self._mark_updated(result.errors)
    
    def update_artists(self, result: ChartsResult) -> None:
        """Update cache with new chart artists result.
        
        Args:
            result: Fresh chart artists from ChartsService
        """
        self.artists_result = result
        self._mark_updated(result.errors)
    
    def update_all(
        self,
        tracks: ChartsResult | None = None,
        albums: ChartsResult | None = None,
        artists: ChartsResult | None = None,
    ) -> None:
        """Update cache with all chart results at once.
        
        Args:
            tracks: Chart tracks result
            albums: Chart albums result
            artists: Chart artists result
        """
        errors: list[str] = []
        
        if tracks:
            self.tracks_result = tracks
            errors.extend(tracks.errors.values() if tracks.errors else [])
        
        if albums:
            self.albums_result = albums
            errors.extend(albums.errors.values() if albums.errors else [])
        
        if artists:
            self.artists_result = artists
            errors.extend(artists.errors.values() if artists.errors else [])
        
        self.cached_at = datetime.now(UTC)
        self.is_valid = True
        self.sync_errors = errors
    
    def _mark_updated(self, errors: dict[str, str] | None = None) -> None:
        """Mark cache as updated with current timestamp."""
        self.cached_at = datetime.now(UTC)
        self.is_valid = True
        if errors:
            self.sync_errors = list(errors.values())
    
    def invalidate(self) -> None:
        """Mark cache as invalid (forces refresh on next access)."""
        self.is_valid = False
    
    def get_stats(self) -> dict[str, int | bool | None]:
        """Get cache statistics for monitoring/debugging.
        
        Returns:
            Dictionary with cache stats
        """
        return {
            "is_valid": self.is_valid,
            "is_fresh": self.is_fresh(),
            "age_seconds": self.get_age_seconds(),
            "track_count": len(self.tracks_result.tracks) if self.tracks_result else 0,
            "album_count": len(self.albums_result.albums) if self.albums_result else 0,
            "artist_count": len(self.artists_result.artists) if self.artists_result else 0,
            "error_count": len(self.sync_errors),
        }
