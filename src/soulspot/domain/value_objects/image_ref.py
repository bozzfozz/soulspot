"""ImageRef value object for consistent image handling across domain.

Hey future me - ImageRef ist die Standard-Struktur für alle Bilder im System!
Jede Entity (Artist, Album, Track, Playlist) nutzt ImageRef für Bild-Referenzen.

Warum Value Object statt einfacher str?
1. Konsistenz: artist.image.url, album.cover.url - gleiche Struktur überall
2. Erweiterbar: Später einfach width, height, format hinzufügen
3. Typsicherheit: Mypy prüft ImageRef-Attribute
4. Semantik: Klar dass es ein Bild ist, nicht irgendein String

Namenskonvention für Entity-Felder:
- artist.image → Künstlerfoto/Profilbild
- album.cover → Album-Cover Art
- track.cover → Single/Track-Cover
- playlist.cover → Playlist-Cover
- user.avatar → User-Profilbild
"""

from dataclasses import dataclass


@dataclass
class ImageRef:
    """Reference to an image (remote URL and/or local cached path).

    Value object for consistent image handling across all domain entities.

    Attributes:
        url: Remote CDN URL (Spotify, Deezer, etc.) - None if not available
        path: Local cached file path - None if not cached locally

    Usage:
        artist.image.url   → Remote CDN URL
        artist.image.path  → Local cached file
        album.cover.url    → Album cover URL
        album.cover.path   → Local album cover

    Both fields are optional - an entity might have:
    - Only URL (not yet cached locally)
    - Only path (local file, no remote)
    - Both (cached from remote)
    - Neither (no image available)
    """
    url: str | None = None   # Remote CDN URL (Spotify, Deezer, etc.)
    path: str | None = None  # Local cached file path

    @property
    def has_image(self) -> bool:
        """Check if any image reference exists (URL or local path)."""
        return bool(self.url or self.path)

    @property
    def display_url(self) -> str | None:
        """Get the best URL for display (prefer local cache, fallback to remote).

        Hey future me - Template verwendet diese Property!
        Zuerst lokale Datei (schneller, offline-fähig), dann CDN.
        Lokale Dateien werden über /api/artwork/ Endpoint serviert.
        """
        # If we have a local path, construct a local URL
        if self.path:
            return f"/api/artwork/{self.path}"
        return self.url

    @classmethod
    def from_url(cls, url: str | None) -> "ImageRef":
        """Create ImageRef from URL only (no local path yet)."""
        return cls(url=url, path=None)

    @classmethod
    def from_path(cls, path: str | None) -> "ImageRef":
        """Create ImageRef from local path only (no remote URL)."""
        return cls(url=None, path=path)

    @classmethod
    def empty(cls) -> "ImageRef":
        """Create empty ImageRef (no image)."""
        return cls(url=None, path=None)

    def with_url(self, url: str | None) -> "ImageRef":
        """Create new ImageRef with updated URL (immutable pattern)."""
        return ImageRef(url=url, path=self.path)

    def with_path(self, path: str | None) -> "ImageRef":
        """Create new ImageRef with updated path (immutable pattern)."""
        return ImageRef(url=self.url, path=path)

    def __bool__(self) -> bool:
        """Enable truthiness check: if image_ref: ..."""
        return self.has_image
