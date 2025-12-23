"""Artist name normalization for matching and deduplication.

Hey future me - this module handles the tricky business of matching artist names!
"DJ Paul Elstak" should match "Paul Elstak", "The Beatles" should match "Beatles".

The key insight is that music files often have different naming conventions:
- Local files: "DJ Paul Elstak" (full DJ prefix)
- Spotify: "Paul Elstak" (no DJ prefix)
- Discogs: "Paul Elstak, DJ" (suffix style)

This module provides normalization functions to strip common prefixes/suffixes
so fuzzy matching can find the correct artist even with naming differences.

Used by:
- LibraryDiscoveryWorker (matching local → Deezer/Spotify)
- LibraryMergeService (duplicate artist detection)
- MetadataMerger (external tag comparison)
- EnrichmentService (candidate scoring)

Examples:
    >>> from soulspot.domain.value_objects.artist_normalization import normalize_artist_name
    >>> normalize_artist_name("DJ Paul Elstak")
    'paul elstak'
    >>> normalize_artist_name("The Prodigy")
    'prodigy'
    >>> normalize_artist_name("Dr. Dre")
    'dre'
"""

# =============================================================================
# ARTIST PREFIXES
# Hey future me - these are common prefixes that should be stripped for matching!
# Order matters: more specific patterns first (e.g., "dj. " before "dj ").
# All patterns are lowercase with trailing space included.
# =============================================================================

ARTIST_PREFIXES: tuple[str, ...] = (
    # DJ variants (most common in electronic music)
    "dj ",
    "dj. ",
    # Articles (common in band names)
    "the ",
    # MC/rapper prefixes
    "mc ",
    "mc. ",
    # Doctor/titles
    "dr ",
    "dr. ",
    # Lil/Big (hip-hop naming conventions)
    "lil ",
    "lil' ",
    "big ",
    # Age/status modifiers
    "young ",
    "old ",
    # Royalty titles
    "king ",
    "queen ",
    "sir ",
    "lady ",
    # Formal titles
    "miss ",
    "mister ",
    "mr ",
    "mr. ",
    "mrs ",
    "mrs. ",
    "ms ",
    "ms. ",
)

# =============================================================================
# ARTIST SUFFIXES
# Hey future me - these are common suffixes that should be stripped for matching!
# Less common than prefixes, but still useful for edge cases.
# =============================================================================

ARTIST_SUFFIXES: tuple[str, ...] = (
    # DJ/MC at end (rare but exists)
    " dj",
    " mc",
    # Group type indicators
    " band",
    " group",
    " orchestra",
    " ensemble",
    " trio",
    " quartet",
    " quintet",
    # Project/collective
    " project",
    " collective",
)


def normalize_artist_name(name: str) -> str:
    """Normalize artist name for better matching.

    Hey future me - this is crucial for matching "DJ Paul Elstak" to "Paul Elstak"!
    Strips common prefixes (DJ, The, MC, Dr, Lil) and suffixes (Band, Orchestra).
    Also normalizes whitespace and case.

    This function is intentionally simple and fast - it runs on every artist
    comparison during enrichment, so performance matters.

    Args:
        name: Original artist name

    Returns:
        Normalized name for comparison (lowercase, stripped prefixes/suffixes)

    Examples:
        >>> normalize_artist_name("DJ Paul Elstak")
        'paul elstak'
        >>> normalize_artist_name("The Prodigy")
        'prodigy'
        >>> normalize_artist_name("Dr. Dre")
        'dre'
        >>> normalize_artist_name("Lil Wayne")
        'wayne'
        >>> normalize_artist_name("Paul Elstak")
        'paul elstak'
        >>> normalize_artist_name("The Beatles Band")
        'beatles'
    """
    if not name:
        return ""

    # Lowercase and strip whitespace
    normalized = name.lower().strip()

    # Strip prefixes (check each, strip first match only)
    # Hey future me - we only strip ONE prefix to avoid over-normalization
    # "The DJ Shadow" -> "dj shadow" (strip "the"), NOT "shadow" (strip both)
    for prefix in ARTIST_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break  # Only strip one prefix

    # Strip suffixes (check each, strip first match only)
    for suffix in ARTIST_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
            break  # Only strip one suffix

    return normalized


def normalize_for_fuzzy_match(name: str) -> str:
    """More aggressive normalization for fuzzy matching.

    Hey future me - use this when you need EXTRA normalization for fuzzy matching!
    Unlike normalize_artist_name(), this also:
    - Removes ALL punctuation
    - Collapses multiple spaces
    - Removes common words like "and", "&"

    This is useful for cases like:
    - "AC/DC" vs "ACDC" vs "AC DC"
    - "Guns N' Roses" vs "Guns and Roses" vs "Guns & Roses"

    Args:
        name: Original artist name

    Returns:
        Aggressively normalized name

    Examples:
        >>> normalize_for_fuzzy_match("AC/DC")
        'acdc'
        >>> normalize_for_fuzzy_match("Guns N' Roses")
        'guns roses'
    """
    import re

    if not name:
        return ""

    # First apply standard normalization
    normalized = normalize_artist_name(name)

    # Remove punctuation (keep alphanumeric and spaces)
    normalized = re.sub(r"[^\w\s]", "", normalized)

    # Remove common conjunctions
    normalized = re.sub(r"\b(and|n|the|a|an)\b", "", normalized, flags=re.IGNORECASE)

    # Collapse multiple spaces
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def extract_sort_name(name: str) -> str:
    """Extract sort name from artist name (move articles to end).

    Hey future me - this is for creating sort-friendly names!
    "The Beatles" -> "Beatles, The"
    "A Tribe Called Quest" -> "Tribe Called Quest, A"

    Useful for:
    - Library sorting
    - Alphabetical artist lists
    - Music player displays

    Args:
        name: Original artist name

    Returns:
        Sort-friendly name with articles moved to end

    Examples:
        >>> extract_sort_name("The Beatles")
        'Beatles, The'
        >>> extract_sort_name("A Tribe Called Quest")
        'Tribe Called Quest, A'
        >>> extract_sort_name("Pink Floyd")
        'Pink Floyd'
    """
    if not name:
        return ""

    # Articles to move to end
    articles = ("the ", "a ", "an ")

    name_lower = name.lower()
    for article in articles:
        if name_lower.startswith(article):
            # Move article to end with comma
            rest = name[len(article) :]
            article_proper = name[: len(article) - 1]  # Remove trailing space
            return f"{rest}, {article_proper}"

    return name


# Export all public functions
__all__ = [
    "ARTIST_PREFIXES",
    "ARTIST_SUFFIXES",
    "normalize_artist_name",
    "normalize_for_fuzzy_match",
    "extract_sort_name",
]
