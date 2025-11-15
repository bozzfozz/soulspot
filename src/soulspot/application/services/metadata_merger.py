"""Metadata merger service for combining metadata from multiple sources."""

import logging
import re
from typing import Any

from soulspot.domain.entities import Album, Artist, MetadataSource, Track

logger = logging.getLogger(__name__)


class MetadataMerger:
    """Service for merging metadata from multiple sources with authority hierarchy.

    Authority Hierarchy: Manual > MusicBrainz > Spotify > Last.fm
    """

    # Authority hierarchy - lower number = higher priority
    AUTHORITY_HIERARCHY = {
        MetadataSource.MANUAL: 0,
        MetadataSource.MUSICBRAINZ: 1,
        MetadataSource.SPOTIFY: 2,
        MetadataSource.LASTFM: 3,
    }

    @staticmethod
    def _get_source_priority(source: MetadataSource) -> int:
        """Get priority value for a metadata source."""
        return MetadataMerger.AUTHORITY_HIERARCHY.get(source, 999)

    @staticmethod
    def _select_best_value(
        current_value: Any,
        current_source: MetadataSource | None,
        new_value: Any,
        new_source: MetadataSource,
    ) -> tuple[Any, MetadataSource]:
        """
        Select the best value based on authority hierarchy.

        Args:
            current_value: Existing value
            current_source: Source of existing value
            new_value: New value to consider
            new_source: Source of new value

        Returns:
            Tuple of (best_value, source)
        """
        # If new value is empty/None, keep current
        if new_value is None or (isinstance(new_value, str) and not new_value.strip()):
            return current_value, current_source or new_source

        # If no current value, use new value
        if current_value is None or (
            isinstance(current_value, str) and not current_value.strip()
        ):
            return new_value, new_source

        # If no source info, use new value (assume it's better than unknown)
        if current_source is None:
            return new_value, new_source

        # Compare priorities
        current_priority = MetadataMerger._get_source_priority(current_source)
        new_priority = MetadataMerger._get_source_priority(new_source)

        if new_priority < current_priority:
            return new_value, new_source

        return current_value, current_source

    @staticmethod
    def _merge_lists(
        current_list: list[str],
        new_list: list[str],
        max_items: int = 10,
    ) -> list[str]:
        """
        Merge two lists, removing duplicates and limiting size.

        Args:
            current_list: Existing list
            new_list: New list to merge
            max_items: Maximum number of items to keep

        Returns:
            Merged list
        """
        # Combine and deduplicate while preserving order
        seen = set()
        merged = []

        for item in current_list + new_list:
            normalized = item.lower().strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                merged.append(item.strip())

        return merged[:max_items]

    @staticmethod
    def normalize_artist_name(name: str) -> str:
        """
        Normalize artist names by standardizing featuring/featuring formats.

        Args:
            name: Artist name to normalize

        Returns:
            Normalized artist name
        """
        if not name:
            return name

        # Replace various featuring formats with standard "feat."
        patterns = [
            (r"\s+ft\.?\s+", " feat. "),
            (r"\s+featuring\s+", " feat. "),
            (r"\s+feat\s+", " feat. "),
            (r"\s+ft\s+", " feat. "),
            (r"\s+Ft\.?\s+", " feat. "),
            (r"\s+Featuring\s+", " feat. "),
            (r"\s+Feat\.?\s+", " feat. "),
        ]

        normalized = name
        for pattern, replacement in patterns:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        return normalized.strip()

    def merge_track_metadata(
        self,
        track: Track,
        spotify_data: dict[str, Any] | None = None,
        musicbrainz_data: dict[str, Any] | None = None,
        lastfm_data: dict[str, Any] | None = None,
        manual_overrides: dict[str, Any] | None = None,
    ) -> Track:
        """
        Merge track metadata from multiple sources.

        Args:
            track: Track entity to update
            spotify_data: Spotify track data
            musicbrainz_data: MusicBrainz recording data
            lastfm_data: Last.fm track data
            manual_overrides: Manual metadata overrides

        Returns:
            Updated track entity
        """
        # Extract metadata from each source
        sources_data: dict[MetadataSource, dict[str, Any]] = {}

        if spotify_data:
            sources_data[MetadataSource.SPOTIFY] = {
                "duration_ms": spotify_data.get("duration_ms"),
                "isrc": (
                    spotify_data.get("external_ids", {}).get("isrc")
                    if "external_ids" in spotify_data
                    else None
                ),
            }

        if musicbrainz_data:
            mb_tags = []
            if "tags" in musicbrainz_data:
                mb_tags = [tag["name"] for tag in musicbrainz_data["tags"][:10]]

            sources_data[MetadataSource.MUSICBRAINZ] = {
                "duration_ms": musicbrainz_data.get("length"),
                "isrc": (
                    musicbrainz_data.get("isrc-list", [None])[0]
                    if "isrc-list" in musicbrainz_data
                    else None
                ),
                "tags": mb_tags,
            }

        if lastfm_data:
            lfm_tags = []
            if "toptags" in lastfm_data and "tag" in lastfm_data["toptags"]:
                lfm_tags = [
                    tag["name"]
                    for tag in lastfm_data["toptags"]["tag"][:10]
                    if isinstance(tag, dict) and "name" in tag
                ]

            sources_data[MetadataSource.LASTFM] = {
                "tags": lfm_tags,
            }

        if manual_overrides:
            sources_data[MetadataSource.MANUAL] = manual_overrides

        # Merge fields based on authority hierarchy
        for source, data in sources_data.items():
            # Duration
            if "duration_ms" in data and data["duration_ms"]:
                current_source = track.metadata_sources.get("duration_ms")
                new_value, best_source = self._select_best_value(
                    track.duration_ms,
                    MetadataSource(current_source) if current_source else None,
                    data["duration_ms"],
                    source,
                )
                if new_value != track.duration_ms:
                    track.duration_ms = new_value
                    track.metadata_sources["duration_ms"] = best_source.value

            # ISRC
            if "isrc" in data and data["isrc"]:
                current_source = track.metadata_sources.get("isrc")
                new_value, best_source = self._select_best_value(
                    track.isrc,
                    MetadataSource(current_source) if current_source else None,
                    data["isrc"],
                    source,
                )
                if new_value != track.isrc:
                    track.isrc = new_value
                    track.metadata_sources["isrc"] = best_source.value

            # Tags (merge from all sources)
            if "tags" in data and data["tags"]:
                track.tags = self._merge_lists(track.tags, data["tags"])

            # Genres (merge from all sources)
            if "genres" in data and data["genres"]:
                track.genres = self._merge_lists(track.genres, data["genres"])

        return track

    def merge_artist_metadata(
        self,
        artist: Artist,
        spotify_data: dict[str, Any] | None = None,
        musicbrainz_data: dict[str, Any] | None = None,
        lastfm_data: dict[str, Any] | None = None,
        manual_overrides: dict[str, Any] | None = None,
    ) -> Artist:
        """
        Merge artist metadata from multiple sources.

        Args:
            artist: Artist entity to update
            spotify_data: Spotify artist data
            musicbrainz_data: MusicBrainz artist data
            lastfm_data: Last.fm artist data
            manual_overrides: Manual metadata overrides

        Returns:
            Updated artist entity
        """
        # Normalize artist name
        artist.name = self.normalize_artist_name(artist.name)

        # Extract metadata from each source
        sources_data: dict[MetadataSource, dict[str, Any]] = {}

        if spotify_data:
            sources_data[MetadataSource.SPOTIFY] = {
                "genres": spotify_data.get("genres", []),
            }

        if musicbrainz_data:
            mb_tags = []
            mb_genres = []
            if "tags" in musicbrainz_data:
                mb_tags = [tag["name"] for tag in musicbrainz_data["tags"][:10]]
            if "genres" in musicbrainz_data:
                mb_genres = [genre["name"] for genre in musicbrainz_data["genres"][:10]]

            sources_data[MetadataSource.MUSICBRAINZ] = {
                "tags": mb_tags,
                "genres": mb_genres,
            }

        if lastfm_data:
            lfm_tags = []
            if "tags" in lastfm_data and "tag" in lastfm_data["tags"]:
                lfm_tags = [
                    tag["name"]
                    for tag in lastfm_data["tags"]["tag"][:10]
                    if isinstance(tag, dict) and "name" in tag
                ]

            sources_data[MetadataSource.LASTFM] = {
                "tags": lfm_tags,
            }

        if manual_overrides:
            sources_data[MetadataSource.MANUAL] = manual_overrides

        # Merge fields
        for _source, data in sources_data.items():
            # Tags (merge from all sources)
            if "tags" in data and data["tags"]:
                artist.tags = self._merge_lists(artist.tags, data["tags"])

            # Genres (merge from all sources)
            if "genres" in data and data["genres"]:
                artist.genres = self._merge_lists(artist.genres, data["genres"])

        return artist

    def merge_album_metadata(
        self,
        album: Album,
        spotify_data: dict[str, Any] | None = None,
        musicbrainz_data: dict[str, Any] | None = None,
        lastfm_data: dict[str, Any] | None = None,
        manual_overrides: dict[str, Any] | None = None,
    ) -> Album:
        """
        Merge album metadata from multiple sources.

        Args:
            album: Album entity to update
            spotify_data: Spotify album data
            musicbrainz_data: MusicBrainz release data
            lastfm_data: Last.fm album data
            manual_overrides: Manual metadata overrides

        Returns:
            Updated album entity
        """
        # Extract metadata from each source
        sources_data: dict[MetadataSource, dict[str, Any]] = {}

        if spotify_data:
            sources_data[MetadataSource.SPOTIFY] = {
                "genres": spotify_data.get("genres", []),
            }

        if musicbrainz_data:
            mb_tags = []
            if "tags" in musicbrainz_data:
                mb_tags = [tag["name"] for tag in musicbrainz_data["tags"][:10]]

            release_year = None
            if "date" in musicbrainz_data:
                date_str = musicbrainz_data["date"]
                if date_str and len(date_str) >= 4:
                    # Extract year from date string
                    year_str = date_str[:4]
                    if year_str.isdigit():
                        release_year = int(year_str)

            sources_data[MetadataSource.MUSICBRAINZ] = {
                "tags": mb_tags,
                "release_year": release_year,
            }

        if lastfm_data:
            lfm_tags = []
            if "tags" in lastfm_data and "tag" in lastfm_data["tags"]:
                lfm_tags = [
                    tag["name"]
                    for tag in lastfm_data["tags"]["tag"][:10]
                    if isinstance(tag, dict) and "name" in tag
                ]

            sources_data[MetadataSource.LASTFM] = {
                "tags": lfm_tags,
            }

        if manual_overrides:
            sources_data[MetadataSource.MANUAL] = manual_overrides

        # Merge fields
        for source, data in sources_data.items():
            # Release year
            if "release_year" in data and data["release_year"]:
                current_source = album.metadata_sources.get("release_year")
                new_value, best_source = self._select_best_value(
                    album.release_year,
                    MetadataSource(current_source) if current_source else None,
                    data["release_year"],
                    source,
                )
                if new_value != album.release_year:
                    album.release_year = new_value
                    album.metadata_sources["release_year"] = best_source.value

            # Tags (merge from all sources)
            if "tags" in data and data["tags"]:
                album.tags = self._merge_lists(album.tags, data["tags"])

            # Genres (merge from all sources)
            if "genres" in data and data["genres"]:
                album.genres = self._merge_lists(album.genres, data["genres"])

        return album
