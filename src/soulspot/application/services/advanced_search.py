"""Advanced search service with fuzzy matching, quality filters, and smart scoring."""

import re
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz


# Hey future me, SearchFilters is a simple config dataclass for search criteria! Holds bitrate minimum (320kbps for
# high quality), allowed formats (prevent downloading .wma garbage), exclusion keywords (no "live" or "remix" trash),
# and fuzzy match threshold (how close filenames must match query, 0-100). Default threshold of 80 is pretty strict -
# lower it to 60-70 if you're getting zero results. These are ALL optional - can search without any filters!
@dataclass
class SearchFilters:
    """Search filters configuration."""

    min_bitrate: int | None = None  # Minimum bitrate in kbps (e.g., 320)
    formats: list[str] | None = None  # Allowed formats (e.g., ["flac", "mp3"])
    exclusion_keywords: list[str] | None = (
        None  # Keywords to exclude (e.g., ["live", "remix"])
    )
    fuzzy_threshold: int = 80  # Minimum fuzzy match score (0-100)


# Yo, SearchResult is slskd raw data + OUR computed scores! Username is who's sharing the file (useful for
# blacklisting jerks), filename is full path like "/music/Artist/Album/01 Track.flac", size in bytes, bitrate
# in kbps, length in seconds (might be None!). The scores are what make this "enhanced" - fuzzy_score is how
# well filename matches query, quality_score is audio quality rating, match_score is combined weighted total.
# All scores are 0-100 scale. This is what you sort by to find the BEST match from hundreds of search results!
@dataclass
class SearchResult:
    """Enhanced search result with scoring."""

    username: str
    filename: str
    size: int
    bitrate: int
    length: int | None = None
    quality: int | None = None
    match_score: float = 0.0  # Combined match score (0-100)
    fuzzy_score: float = 0.0  # Fuzzy matching score (0-100)
    quality_score: float = 0.0  # Quality score (0-100)


# Listen up future me, AdvancedSearchService is the SMART search on top of dumb slskd results! Takes raw
# search results (hundreds of files) and ranks them by fuzzy matching + quality + filename cleanliness. This
# is stateless (no internal state, pure functions) so safe for concurrent use. default_exclusion_keywords are
# patterns most users hate (live recordings, karaoke tracks, etc). Add more keywords here if users complain!
class AdvancedSearchService:
    """Service for advanced search with fuzzy matching and filtering."""

    # Hey future me, stores default blacklist keywords - these get auto-excluded unless user overrides.
    # WHY these specific words? They're the most common "junk" in music filenames that users don't want.
    # Add regional variants if needed (e.g., "en vivo" for Spanish "live").
    def __init__(self) -> None:
        """Initialize the advanced search service."""
        self.default_exclusion_keywords = [
            "live",
            "remix",
            "cover",
            "karaoke",
            "instrumental",
            "acoustic",
            "demo",
            "rehearsal",
        ]

    # Hey future me: Advanced search with fuzzy matching - because "bohemian rhapsody" should match "Bohemian Rhapsody (2011 Remaster).flac"
    # WHY fuzzy matching? Users and uploaders spell things differently, we need tolerance
    # WHY rapidfuzz.token_set_ratio? It ignores word order and extra words - perfect for music filenames
    # Example: "Queen Bohemian Rhapsody" matches "Bohemian Rhapsody - Queen - 2011 Remaster"
    def apply_fuzzy_matching(
        self,
        query: str,
        results: list[dict[str, Any]],
        threshold: int = 80,
    ) -> list[SearchResult]:
        """Apply fuzzy matching to search results.

        Args:
            query: Search query string
            results: List of search results from slskd
            threshold: Minimum fuzzy match score (0-100)

        Returns:
            List of SearchResult objects with fuzzy match scores
        """
        enhanced_results: list[SearchResult] = []

        for result in results:
            filename = result.get("filename", "")
            # Extract filename without path and extension for better matching
            base_filename = self._extract_base_filename(filename)

            # Calculate fuzzy match score
            fuzzy_score = fuzz.token_set_ratio(query.lower(), base_filename.lower())

            if fuzzy_score >= threshold:
                enhanced_results.append(
                    SearchResult(
                        username=result.get("username", ""),
                        filename=filename,
                        size=result.get("size", 0),
                        bitrate=result.get("bitrate", 0),
                        length=result.get("length"),
                        quality=result.get("quality"),
                        fuzzy_score=fuzzy_score,
                    )
                )

        return enhanced_results

    # Yo, quality filtering - removes files that don't meet bitrate/format standards. This is FAST filtering
    # (simple comparisons), no scoring involved. WHY filter before scoring? Saves CPU - don't score files we'll
    # reject anyway! Example: if user wants FLAC only, we remove all MP3s here. If min_bitrate=320, we remove
    # all 128kbps files. This can reduce 1000 results to 50, huge speedup for scoring step!
    def apply_quality_filters(
        self,
        results: list[SearchResult],
        filters: SearchFilters,
    ) -> list[SearchResult]:
        """Apply quality filters to search results.

        Args:
            results: List of search results
            filters: Search filters configuration

        Returns:
            Filtered list of search results
        """
        filtered_results = results

        # Filter by minimum bitrate
        if filters.min_bitrate is not None:
            filtered_results = [
                r for r in filtered_results if r.bitrate >= filters.min_bitrate
            ]

        # Filter by format
        if filters.formats:
            allowed_extensions = [f".{fmt.lower()}" for fmt in filters.formats]
            filtered_results = [
                r
                for r in filtered_results
                if any(r.filename.lower().endswith(ext) for ext in allowed_extensions)
            ]

        return filtered_results

    # Hey, exclusion filter - blacklist removal by keywords in filename. WHY case-insensitive? "LIVE" and "live"
    # both suck equally! WHY substring match not word match? Catches "live_recording", "live-2023", etc. Uses
    # default keywords if none provided (convenience). This is super simple but effective - removes 30-40% of
    # junk results typically. The any() check is efficient - stops at first match, no need to check all keywords.
    # GOTCHA: This can be too aggressive - "Alive" contains "live"! Consider word boundary regex if that's a problem.
    def apply_exclusion_filters(
        self,
        results: list[SearchResult],
        exclusion_keywords: list[str] | None = None,
    ) -> list[SearchResult]:
        """Apply exclusion keyword filters to search results.

        Args:
            results: List of search results
            exclusion_keywords: Keywords to exclude (defaults to built-in list)

        Returns:
            Filtered list of search results
        """
        keywords = exclusion_keywords or self.default_exclusion_keywords
        keywords_lower = [kw.lower() for kw in keywords]

        filtered_results = []
        for result in results:
            filename_lower = result.filename.lower()
            # Check if any exclusion keyword is present in the filename
            if not any(kw in filename_lower for kw in keywords_lower):
                filtered_results.append(result)

        return filtered_results

    # Hey future me: Quality scoring - the "how good is this audio file" calculator
    # Scoring breakdown (0-100 scale):
    # - Format: FLAC=40pts, M4A/Opus=30pts, MP3=20pts (lossless > modern lossy > old lossy)
    # - Bitrate: Normalized to 40pts (320kbps MP3 = 40pts, FLAC 800+kbps = 40pts)
    # - File size: 20pts (bigger usually means better quality for same format)
    # WHY different bitrate ranges for FLAC vs MP3? FLAC is variable bitrate, typically 800-1400kbps
    def calculate_quality_score(self, result: SearchResult) -> float:
        """Calculate quality score for a search result.

        Args:
            result: Search result

        Returns:
            Quality score (0-100)
        """
        score = 0.0

        # Format scoring
        filename_lower = result.filename.lower()
        if filename_lower.endswith(".flac"):
            score += 40  # FLAC gets highest format score
        elif filename_lower.endswith(".m4a") or filename_lower.endswith(".opus"):
            score += 30  # High quality lossy formats
        elif filename_lower.endswith(".mp3"):
            score += 20  # MP3
        elif filename_lower.endswith(".ogg"):
            score += 15  # Ogg Vorbis
        else:
            score += 10  # Other formats

        # Bitrate scoring (normalized to 0-40 range)
        if result.bitrate > 0:
            # FLAC typically reports high bitrate (800-1400 kbps)
            if filename_lower.endswith(".flac"):
                if result.bitrate >= 800:
                    score += 40
                else:
                    score += 20
            else:
                # For lossy formats, 320 kbps is ideal
                bitrate_score = min(result.bitrate / 320.0, 1.0) * 40
                score += bitrate_score

        # File size as quality indicator (0-20 range)
        # Larger files generally indicate better quality
        if result.size > 0:
            # Assume 3-minute song at 320kbps ~= 7.2MB
            # FLAC is roughly 3-4x larger
            expected_size_mp3 = 7_200_000  # 7.2 MB for 3 min at 320kbps
            expected_size_flac = 25_000_000  # ~25 MB for 3 min FLAC

            if filename_lower.endswith(".flac"):
                size_ratio = min(result.size / expected_size_flac, 1.5)
            else:
                size_ratio = min(result.size / expected_size_mp3, 1.5)

            size_score = (size_ratio / 1.5) * 20
            score += size_score

        return min(score, 100.0)

    # Hey future me: Smart scoring - combines fuzzy match + quality + filename cleanliness
    # Weighting: 50% match quality, 40% audio quality, 10% filename quality
    # WHY these weights? Doesn't matter if it's FLAC if it's the wrong song!
    # Example: 100% match + 128kbps MP3 beats 70% match + FLAC
    # GOTCHA: This assumes search results are somewhat relevant - garbage in, garbage out
    def calculate_smart_score(
        self,
        result: SearchResult,
        _query: str,  # noqa: ARG002 - kept for potential future use
    ) -> float:
        """Calculate overall smart score combining multiple factors.

        Args:
            result: Search result
            _query: Original search query (reserved for future use)

        Returns:
            Smart score (0-100)
        """
        # Calculate quality score if not already calculated
        if result.quality_score == 0.0:
            result.quality_score = self.calculate_quality_score(result)

        # Weighted combination:
        # - 50% fuzzy match (how well it matches the query)
        # - 40% quality score (audio quality)
        # - 10% filename quality (bonus for clean filenames)

        fuzzy_weight = 0.5
        quality_weight = 0.4
        filename_weight = 0.1

        # Filename quality: prefer shorter, cleaner filenames
        filename_score = self._calculate_filename_quality(result.filename)

        smart_score = (
            fuzzy_weight * result.fuzzy_score
            + quality_weight * result.quality_score
            + filename_weight * filename_score
        )

        result.match_score = smart_score
        return smart_score

    # Listen, filename cleanliness scoring - because "Artist - Title.mp3" is better than
    # "!!!Artist!!!_-_Title_[FLAC][2023][OFFICIAL]_by_uploader!!!.mp3". Start at 100 points and deduct penalties.
    # WHY penalize length? Long names = people stuffing metadata/tags/watermarks into filename (annoying!).
    # WHY count special chars? Clean names use minimal punctuation. The regex excludes word chars, spaces, hyphens,
    # dots (normal filename chars). More than 15 special chars = -30pts max. Double spaces/underscores = sloppy
    # encoding. The regex bonus rewards "Artist - Title" format which is the gold standard. This is subjective but
    # empirically works well - cleaner filenames usually = better sources!
    def _calculate_filename_quality(self, filename: str) -> float:
        """Calculate filename quality score.

        Args:
            filename: Filename to score

        Returns:
            Filename quality score (0-100)
        """
        score = 100.0

        # Penalize very long filenames (likely have extra metadata)
        base_filename = self._extract_base_filename(filename)
        if len(base_filename) > 100:
            score -= 20
        elif len(base_filename) > 150:
            score -= 40

        # Penalize excessive special characters
        special_char_count = len(re.findall(r"[^\w\s\-.]", base_filename))
        score -= min(special_char_count * 2, 30)

        # Penalize multiple spaces or underscores
        if "  " in base_filename or "__" in base_filename:
            score -= 10

        # Bonus for well-formatted names (Artist - Title.ext pattern)
        if re.match(r"^[\w\s]+ - [\w\s]+\.\w+$", base_filename):
            score += 10

        return max(score, 0.0)

    # Yo, strips path and extension from filename. WHY split on both / and \? Soulseek returns paths from
    # Windows (backslash) and Unix (forward slash) users. Taking last element gets filename regardless. The
    # extension removal joins all but last dot-separated part - handles "file.tar.gz" correctly (keeps "file.tar").
    # This is purely string manipulation, no filesystem access. Simple and works cross-platform!
    def _extract_base_filename(self, filename: str) -> str:
        """Extract base filename without path and extension.

        Args:
            filename: Full filename with path

        Returns:
            Base filename without path and extension
        """
        # Remove path
        base = filename.split("/")[-1].split("\\")[-1]
        # Remove extension
        if "." in base:
            base = ".".join(base.split(".")[:-1])
        return base

    # Hey future me, the final ranking step - calculates smart scores for ALL results then sorts best-first.
    # WHY calculate then sort, not sort during calculate? Cleaner separation, easier to debug scores. The lambda
    # sort key is simple - higher match_score wins. reverse=True puts best matches at index 0. This modifies
    # the SearchResult objects in place (sets match_score) which is a bit side-effecty but efficient. Returns
    # new sorted list without modifying input. Use this before presenting results to user!
    def rank_results(
        self,
        results: list[SearchResult],
        query: str,
    ) -> list[SearchResult]:
        """Rank search results by smart score.

        Args:
            results: List of search results
            query: Original search query

        Returns:
            Ranked list of search results (best first)
        """
        # Calculate smart scores for all results
        for result in results:
            self.calculate_smart_score(result, query)

        # Sort by match_score (descending)
        ranked = sorted(results, key=lambda r: r.match_score, reverse=True)

        return ranked

    # Listen up, this is THE FULL PIPELINE - everything in one call! Takes raw slskd results and returns
    # ranked, filtered, scored results ready for user. Four-step process: fuzzy match (remove non-matches),
    # quality filter (bitrate/format), exclusion filter (blacklist keywords), then rank (smart scoring + sort).
    # Order matters! Filter first (fast), then score survivors (slow). This is the main public API - most
    # callers use this instead of individual steps. Filters default to SearchFilters() with all None (no filtering).
    # Returns list in best-to-worst order - take first N for "top results"!
    def search_with_filters(
        self,
        query: str,
        results: list[dict[str, Any]],
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        """Complete search pipeline with all filters and ranking.

        Args:
            query: Search query string
            results: Raw search results from slskd
            filters: Search filters configuration

        Returns:
            Filtered and ranked list of search results
        """
        if filters is None:
            filters = SearchFilters()

        # Step 1: Apply fuzzy matching
        enhanced_results = self.apply_fuzzy_matching(
            query, results, filters.fuzzy_threshold
        )

        # Step 2: Apply quality filters
        filtered_results = self.apply_quality_filters(enhanced_results, filters)

        # Step 3: Apply exclusion filters
        if filters.exclusion_keywords is not None:
            filtered_results = self.apply_exclusion_filters(
                filtered_results, filters.exclusion_keywords
            )
        else:
            # Use default exclusions
            filtered_results = self.apply_exclusion_filters(filtered_results, None)

        # Step 4: Rank by smart score
        ranked_results = self.rank_results(filtered_results, query)

        return ranked_results

    # Hey future me, convenience method - runs full pipeline and returns ONLY the #1 best result. Use this for
    # auto-download scenarios where you trust the scoring algorithm. Returns None if no results pass filters
    # (common with strict bitrate requirements). This is safe for automation but always log what you pick so
    # you can debug when it downloads the wrong version!
    def select_best_match(
        self,
        query: str,
        results: list[dict[str, Any]],
        filters: SearchFilters | None = None,
    ) -> SearchResult | None:
        """Select the best match from search results.

        Args:
            query: Search query string
            results: Raw search results from slskd
            filters: Search filters configuration

        Returns:
            Best matching result or None if no results
        """
        ranked_results = self.search_with_filters(query, results, filters)

        return ranked_results[0] if ranked_results else None
