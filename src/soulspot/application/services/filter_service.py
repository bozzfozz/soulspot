"""Filter service for whitelist/blacklist filtering."""

import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import FilterRule, FilterTarget, FilterType
from soulspot.domain.value_objects import FilterRuleId
from soulspot.infrastructure.persistence.repositories import FilterRuleRepository

logger = logging.getLogger(__name__)


class FilterService:
    """Service for managing and applying filter rules."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize filter service.

        Args:
            session: Database session
        """
        self.repository = FilterRuleRepository(session)

    # Hey future me, creates whitelist/blacklist filter rules! pattern is string to match (or regex if
    # is_regex=True). FilterRule is a domain entity (good separation of concerns). Uses repository.add()
    # to persist to DB. The priority param determines evaluation order (higher = first) which matters when
    # you have conflicting rules. enabled=True by default means rule is active immediately. No validation
    # on pattern - could create invalid regex and crash when applied! Should validate regex patterns here.
    # Description is optional but highly recommended - you'll forget what the rule does in 6 months! Logs
    # creation which is good for auditing. Returns the created rule for immediate use. FilterRuleId.generate()
    # creates new UUID - good for distributed systems (no auto-increment ID conflicts).
    async def create_filter(
        self,
        name: str,
        filter_type: FilterType,
        target: FilterTarget,
        pattern: str,
        is_regex: bool = False,
        priority: int = 0,
        description: str | None = None,
    ) -> FilterRule:
        """Create a new filter rule.

        Args:
            name: Filter name
            filter_type: Type (whitelist/blacklist)
            target: Target (keyword/user/format/bitrate)
            pattern: Pattern to match
            is_regex: Whether pattern is regex
            priority: Rule priority (higher evaluated first)
            description: Optional description

        Returns:
            Created filter rule
        """
        filter_rule = FilterRule(
            id=FilterRuleId.generate(),
            name=name,
            filter_type=filter_type,
            target=target,
            pattern=pattern,
            is_regex=is_regex,
            enabled=True,
            priority=priority,
            description=description,
        )
        await self.repository.add(filter_rule)
        logger.info(f"Created filter rule: {name} ({filter_type.value})")
        return filter_rule

    # Hey simple getter - fetches filter by ID from repository
    # type: ignore comment because repository might return None but type system gets confused
    async def get_filter(self, filter_id: FilterRuleId) -> FilterRule | None:
        """Get filter rule by ID."""
        return await self.repository.get_by_id(filter_id)  # type: ignore[no-any-return]

    # Yo list all filters with pagination - offset/limit for large filter lists
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[FilterRule]:
        """List all filter rules."""
        return await self.repository.list_all(limit, offset)

    # Listen, filters by type - get only whitelist OR only blacklist rules
    async def list_by_type(self, filter_type: FilterType) -> list[FilterRule]:
        """List filter rules by type."""
        return await self.repository.list_by_type(filter_type.value)

    # Hey only enabled filters - disabled ones exist in DB but don't apply to search results
    # Useful for temporarily disabling a filter without deleting it
    async def list_enabled(self) -> list[FilterRule]:
        """List all enabled filter rules."""
        return await self.repository.list_enabled()

    # Yo enable/disable toggle - calls domain entity method then persists
    # WHY call entity.enable()? Encapsulates business logic (could add validation, timestamps, etc)
    async def enable_filter(self, filter_id: FilterRuleId) -> None:
        """Enable a filter rule."""
        filter_rule = await self.repository.get_by_id(filter_id)
        if filter_rule:
            filter_rule.enable()
            await self.repository.update(filter_rule)
            logger.info(f"Enabled filter rule: {filter_rule.name}")

    # Listen, disable filter - keeps it in DB but stops applying it
    async def disable_filter(self, filter_id: FilterRuleId) -> None:
        """Disable a filter rule."""
        filter_rule = await self.repository.get_by_id(filter_id)
        if filter_rule:
            filter_rule.disable()
            await self.repository.update(filter_rule)
            logger.info(f"Disabled filter rule: {filter_rule.name}")

    # Hey pattern update - change the match pattern or regex flag
    # Useful for tweaking filters without deleting and recreating
    async def update_filter_pattern(
        self, filter_id: FilterRuleId, pattern: str, is_regex: bool = False
    ) -> None:
        """Update filter pattern."""
        filter_rule = await self.repository.get_by_id(filter_id)
        if filter_rule:
            filter_rule.update_pattern(pattern, is_regex)
            await self.repository.update(filter_rule)
            logger.info(f"Updated pattern for filter rule: {filter_rule.name}")

    # Yo permanent deletion - use with caution!
    async def delete_filter(self, filter_id: FilterRuleId) -> None:
        """Delete a filter rule."""
        await self.repository.delete(filter_id)
        logger.info(f"Deleted filter rule: {filter_id}")

    async def apply_filters(
        self, search_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Apply all enabled filters to search results.

        Args:
            search_results: List of search results from slskd
                Expected format: [{"filename": "...", "username": "...", ...}, ...]

        Returns:
            Filtered list of search results
        """
        filters = await self.list_enabled()
        if not filters:
            return search_results

        # Sort by priority (higher first)
        filters.sort(key=lambda f: f.priority, reverse=True)

        # Separate whitelist and blacklist filters
        whitelist_filters = [
            f for f in filters if f.filter_type == FilterType.WHITELIST
        ]
        blacklist_filters = [
            f for f in filters if f.filter_type == FilterType.BLACKLIST
        ]

        filtered_results = []

        for result in search_results:
            # Apply blacklist filters first
            if self._is_blacklisted(result, blacklist_filters):
                logger.debug(
                    f"Filtered out by blacklist: {result.get('filename', 'unknown')}"
                )
                continue

            # Apply whitelist filters (if any exist, result must match at least one)
            if whitelist_filters and not self._is_whitelisted(
                result, whitelist_filters
            ):
                logger.debug(
                    f"Filtered out by whitelist: {result.get('filename', 'unknown')}"
                )
                continue

            filtered_results.append(result)

        logger.info(
            f"Filtered {len(search_results)} results down to {len(filtered_results)}"
        )
        return filtered_results

    # Listen, blacklist check - returns True if result matches ANY blacklist filter
    # WHY any match? One bad keyword is enough to filter out (e.g., "live" excludes all live versions)
    def _is_blacklisted(
        self, result: dict[str, Any], blacklist_filters: list[FilterRule]
    ) -> bool:
        """Check if result matches any blacklist filter."""
        for filter_rule in blacklist_filters:
            if self._matches_filter(result, filter_rule):
                return True
        return False

    # Hey whitelist check - returns True if matches ANY whitelist filter
    # If you have whitelists, result MUST match at least one to pass
    def _is_whitelisted(
        self, result: dict[str, Any], whitelist_filters: list[FilterRule]
    ) -> bool:
        """Check if result matches any whitelist filter."""
        for filter_rule in whitelist_filters:
            if self._matches_filter(result, filter_rule):
                return True
        return False

    def _matches_filter(self, result: dict[str, Any], filter_rule: FilterRule) -> bool:
        """Check if result matches a specific filter rule."""
        try:
            if filter_rule.target == FilterTarget.KEYWORD:
                # Check filename for keyword
                filename = result.get("filename", "")
                return self._pattern_matches(filter_rule, filename)

            elif filter_rule.target == FilterTarget.USER:
                # Check username
                username = result.get("username", "")
                return self._pattern_matches(filter_rule, username)

            elif filter_rule.target == FilterTarget.FORMAT:
                # Check file format/extension
                filename = result.get("filename", "")
                extension = filename.split(".")[-1].lower() if "." in filename else ""
                return self._pattern_matches(filter_rule, extension)

            elif filter_rule.target == FilterTarget.BITRATE:
                # Check if bitrate is above minimum
                bitrate = result.get("bitrate", 0)
                try:
                    min_bitrate = int(filter_rule.pattern)
                    return bitrate >= min_bitrate  # type: ignore[no-any-return]
                except ValueError:
                    logger.warning(f"Invalid bitrate pattern: {filter_rule.pattern}")
                    return False

        except Exception as e:
            logger.error(f"Error matching filter {filter_rule.name}: {e}")
            return False

        return False

    # Yo pattern matching - case-insensitive substring search OR regex
    # WHY case-insensitive? "FLAC" and "flac" should both match
    # GOTCHA: Invalid regex patterns are caught and logged, returns False (safe default)
    def _pattern_matches(self, filter_rule: FilterRule, text: str) -> bool:
        """Check if text matches filter pattern."""
        if filter_rule.is_regex:
            try:
                return bool(re.search(filter_rule.pattern, text, re.IGNORECASE))
            except re.error as e:
                logger.error(f"Invalid regex pattern in filter {filter_rule.name}: {e}")
                return False
        else:
            # Case-insensitive substring match
            return filter_rule.pattern.lower() in text.lower()

    # Listen, default keywords - hard-coded list of common exclusions
    # WHY these? Live recordings, remixes, karaoke usually lower quality than studio originals
    # Return list not set so order is preserved (could be used for UI display order)
    async def get_default_exclusion_keywords(self) -> list[str]:
        """Get default exclusion keywords for new installations.

        Returns:
            List of common exclusion keywords
        """
        return [
            "live",
            "remix",
            "cover",
            "karaoke",
            "instrumental",
            "acapella",
            "radio edit",
            "demo",
            "bootleg",
            "tribute",
        ]

    # Hey, create default filters from keyword list - onboarding helper for new users
    # WHY priority 100-i? Earlier keywords (like "live") get higher priority than later ones
    # WHY per-filter try/except? Don't want one bad keyword to stop creating others
    # Returns created filters so caller knows what was actually created vs failed
    async def create_default_filters(self) -> list[FilterRule]:
        """Create default blacklist filters for common unwanted content.

        Returns:
            List of created filter rules
        """
        keywords = await self.get_default_exclusion_keywords()
        filters = []

        for i, keyword in enumerate(keywords):
            try:
                filter_rule = await self.create_filter(
                    name=f"Exclude {keyword.title()}",
                    filter_type=FilterType.BLACKLIST,
                    target=FilterTarget.KEYWORD,
                    pattern=keyword,
                    is_regex=False,
                    priority=100 - i,  # Earlier keywords have higher priority
                    description=f"Automatically exclude tracks with '{keyword}' in filename",
                )
                filters.append(filter_rule)
            except Exception as e:
                logger.error(f"Failed to create default filter for '{keyword}': {e}")

        logger.info(f"Created {len(filters)} default exclusion filters")
        return filters
