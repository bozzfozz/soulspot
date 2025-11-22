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

    # Hey helper method - returns priority number for source (lower = higher authority)
    # MANUAL has priority 0 (highest), MUSICBRAINZ 1, SPOTIFY 2, LASTFM 3
    # Unknown sources get 999 (lowest priority) - safe fallback
    @staticmethod
    def _get_source_priority(source: MetadataSource) -> int:
        """Get priority value for a metadata source."""
        return MetadataMerger.AUTHORITY_HIERARCHY.get(source, 999)

    # Hey future me - detects when sources disagree on field value!
    # WHY normalize values? "Rock" vs "rock" isn't a real conflict, just formatting
    # WHY check empty values? None/"" values don't count as conflicts
    # Returns dict of {source: value} for all conflicting values EXCEPT the winner
    # Empty dict means no conflict (all sources agree or only one has data)
    @staticmethod
    def _detect_conflicts(
        _field_name: str,  # Hey - kept for documentation, not used in logic
        values_by_source: dict[MetadataSource, Any],
        winning_source: MetadataSource,
    ) -> dict[MetadataSource, Any]:
        """
        Detect conflicts between metadata sources for a specific field.

        Args:
            _field_name: Name of the field being checked (for documentation)
            values_by_source: Map of source to value for this field
            winning_source: The source that won based on authority hierarchy

        Returns:
            Dict of conflicting sources and their values (excludes winner)
        """
        conflicts: dict[MetadataSource, Any] = {}

        # Get winning value
        winning_value = values_by_source.get(winning_source)
        if winning_value is None or (
            isinstance(winning_value, str) and not winning_value.strip()
        ):
            return conflicts  # No conflicts if winning value is empty

        # Check each source for conflicts
        for source, value in values_by_source.items():
            if source == winning_source:
                continue  # Skip the winner

            # Skip empty values
            if value is None or (isinstance(value, str) and not value.strip()):
                continue

            # Normalize for comparison (case-insensitive for strings)
            normalized_winning = (
                str(winning_value).strip().lower() if winning_value else ""
            )
            normalized_value = str(value).strip().lower() if value else ""

            # If values differ, it's a conflict
            if normalized_winning != normalized_value:
                conflicts[source] = value

        return conflicts

    # Yo value selection - picks best value based on source authority
    # WHY check empty strings? API might return "" instead of None for missing data
    # WHY prefer new if current is None? Need to populate empty fields
    # Returns tuple (value, source) so you know WHERE the final value came from
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

    # Listen, list merger - combines two lists while removing duplicates
    # WHY normalize to lowercase? "Rock" and "rock" are the same genre
    # WHY preserve original case? Keep first occurrence's case ("Rock" not "rock")
    # max_items limit prevents tag bloat (imagine merging 50 tags from all sources!)
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

    # Listen, normalizes artist names to standardize "feat" formatting! All those regex patterns catch
    # variations like "ft.", "feat", "featuring", "Ft.", etc and replace with standard " feat. " (note
    # the spaces). Uses re.IGNORECASE so "FEATURING" also matches. Multiple patterns needed because
    # people write it so many different ways! The .strip() at end removes leading/trailing whitespace.
    # Regex substitution happens in order so later patterns won't undo earlier ones. This is idempotent -
    # running twice gives same result. Useful for deduplication (different artist strings that are really
    # the same artist). Doesn't handle unicode variants or typos. Consider adding more patterns like
    # "f/" or "w/" (common abbreviations). Returns original string if empty/None which is safe.
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

    # Hey future me, this merges metadata from multiple sources with authority rules! Manual overrides
    # are highest priority (user knows best), then MusicBrainz (official DB), Spotify (streaming service),
    # Last.fm (community). For each source, extracts relevant fields and calls _select_best_value which
    # compares authority levels. Duration and ISRC use strict authority - only better source overwrites.
    # Tags and genres MERGE from all sources (combine lists) instead of replacing. The metadata_sources dict
    # tracks which field came from which source - useful for debugging and conflict resolution. Nested dict
    # access like spotify_data.get("external_ids", {}).get("isrc") prevents KeyError if structure missing.
    # List slicing [:10] limits tags to prevent bloat. This modifies Track entity in place and returns it.
    # NOW also returns conflicts dict showing where sources disagreed!
    def merge_track_metadata(
        self,
        track: Track,
        spotify_data: dict[str, Any] | None = None,
        musicbrainz_data: dict[str, Any] | None = None,
        lastfm_data: dict[str, Any] | None = None,
        manual_overrides: dict[str, Any] | None = None,
    ) -> tuple[Track, dict[str, dict[MetadataSource, Any]]]:
        """
        Merge track metadata from multiple sources.

        Args:
            track: Track entity to update
            spotify_data: Spotify track data
            musicbrainz_data: MusicBrainz recording data
            lastfm_data: Last.fm track data
            manual_overrides: Manual metadata overrides

        Returns:
            Tuple of (updated track entity, conflicts dict)
            Conflicts dict maps field_name -> {source: conflicting_value}
        """
        # Track detected conflicts
        detected_conflicts: dict[str, dict[MetadataSource, Any]] = {}

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

        # Hey - collect ALL values for each field to detect conflicts!
        # Build a map of field_name -> {source: value} for comparison
        field_values: dict[str, dict[MetadataSource, Any]] = {}

        for source, data in sources_data.items():
            if "duration_ms" in data and data["duration_ms"]:
                if "duration_ms" not in field_values:
                    field_values["duration_ms"] = {}
                field_values["duration_ms"][source] = data["duration_ms"]

            if "isrc" in data and data["isrc"]:
                if "isrc" not in field_values:
                    field_values["isrc"] = {}
                field_values["isrc"][source] = data["isrc"]

        # Merge fields based on authority hierarchy and detect conflicts
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

        # Detect conflicts after merging
        for field_name, values_by_source in field_values.items():
            if len(values_by_source) <= 1:
                continue  # No conflict if only one source has data

            # Determine winning source (what's in track.metadata_sources)
            winning_source_str = track.metadata_sources.get(field_name)
            if not winning_source_str:
                continue  # Skip if no winning source tracked

            winning_source = MetadataSource(winning_source_str)
            conflicts = self._detect_conflicts(
                field_name, values_by_source, winning_source
            )

            if conflicts:
                detected_conflicts[field_name] = conflicts

        return track, detected_conflicts

    # Hey artist metadata merger - updates Artist entity with data from multiple sources
    # WHY normalize name first? Standardize "ft." format before merging
    # Tags and genres MERGE from all sources (accumulate), not replace
    # Returns modified artist entity for fluent API style
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

    # Yo album metadata merger - similar to track/artist but also handles release_year
    # WHY parse date string? MusicBrainz returns "YYYY-MM-DD", we only want year
    # WHY [:4] slice? First 4 chars are always the year ("2023-05-15" -> "2023")
    # isdigit() check prevents crash on malformed dates like "XXXX-01-01"
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
