# Advanced Search & Matching API Documentation

## Overview

The Advanced Search & Matching API provides intelligent track matching with fuzzy search, quality filters, exclusion keywords, and smart scoring algorithms to find the best quality matches for music downloads.

## Features

- **Fuzzy Matching**: Typo-tolerant search with configurable threshold
- **Quality Filters**: Min bitrate and audio format filtering
- **Exclusion Keywords**: Blacklist unwanted versions (live, remix, etc.)
- **Smart Scoring**: Intelligent ranking based on multiple factors
- **Alternative Sources**: Automatic fallback to alternative matches

## Service Architecture

### AdvancedSearchService

Core service providing advanced search capabilities.

#### Key Methods

##### `search_with_filters(query, results, filters)`

Complete search pipeline with all filters and ranking.

**Parameters:**
- `query` (str): Search query string
- `results` (list[dict]): Raw search results from slskd
- `filters` (SearchFilters | None): Search filters configuration

**Returns:**
- `list[SearchResult]`: Filtered and ranked search results

**Example:**
```python
from soulspot.application.services.advanced_search import (
    AdvancedSearchService,
    SearchFilters,
)

service = AdvancedSearchService()

# Configure filters
filters = SearchFilters(
    min_bitrate=256,           # Minimum 256 kbps
    formats=["flac", "mp3"],   # Only FLAC and MP3
    exclusion_keywords=["live", "remix"],
    fuzzy_threshold=80,        # 80% match threshold
)

# Raw search results from slskd
raw_results = [
    {
        "username": "user1",
        "filename": "/music/Artist - Song.flac",
        "size": 25000000,
        "bitrate": 1000,
    },
    # ... more results
]

# Apply advanced search
ranked_results = service.search_with_filters(
    query="Artist Song",
    results=raw_results,
    filters=filters,
)

# Best match
if ranked_results:
    best = ranked_results[0]
    print(f"Best match: {best.filename}")
    print(f"Match score: {best.match_score:.2f}")
    print(f"Quality score: {best.quality_score:.2f}")
```

##### `select_best_match(query, results, filters)`

Select the single best match from search results.

**Parameters:**
- `query` (str): Search query string
- `results` (list[dict]): Raw search results from slskd
- `filters` (SearchFilters | None): Search filters configuration

**Returns:**
- `SearchResult | None`: Best matching result or None

**Example:**
```python
best_match = service.select_best_match(
    query="Artist Song",
    results=raw_results,
    filters=filters,
)

if best_match:
    print(f"Download: {best_match.filename} from {best_match.username}")
```

## Data Models

### SearchFilters

Configuration for search filtering and matching.

**Fields:**
- `min_bitrate` (int | None): Minimum bitrate in kbps (e.g., 320)
- `formats` (list[str] | None): Allowed formats (e.g., ["flac", "mp3"])
- `exclusion_keywords` (list[str] | None): Keywords to exclude (e.g., ["live", "remix"])
- `fuzzy_threshold` (int): Minimum fuzzy match score (0-100, default: 80)

**Example:**
```python
from soulspot.application.services.advanced_search import SearchFilters

# Strict quality filters
strict_filters = SearchFilters(
    min_bitrate=320,
    formats=["flac"],
    exclusion_keywords=["live", "remix", "cover"],
    fuzzy_threshold=90,
)

# Relaxed filters
relaxed_filters = SearchFilters(
    min_bitrate=192,
    formats=["flac", "mp3", "m4a"],
    exclusion_keywords=["live"],
    fuzzy_threshold=70,
)
```

### SearchResult

Enhanced search result with scoring information.

**Fields:**
- `username` (str): User sharing the file
- `filename` (str): Full file path
- `size` (int): File size in bytes
- `bitrate` (int): Audio bitrate in kbps
- `length` (int | None): Track length in seconds
- `quality` (int | None): Quality indicator
- `match_score` (float): Combined match score (0-100)
- `fuzzy_score` (float): Fuzzy matching score (0-100)
- `quality_score` (float): Quality score (0-100)

## Integration with SearchAndDownloadTrackUseCase

The advanced search service is integrated into the existing search and download use case.

### Enhanced Request Parameters

```python
from soulspot.application.use_cases.search_and_download import (
    SearchAndDownloadTrackRequest,
)
from soulspot.domain.value_objects import TrackId

request = SearchAndDownloadTrackRequest(
    track_id=TrackId.from_string("..."),
    search_query="Artist Song Name",
    
    # Standard options
    max_results=10,
    timeout_seconds=30,
    quality_preference="best",
    
    # Advanced search options
    use_advanced_search=True,      # Enable advanced features
    min_bitrate=320,               # Minimum bitrate
    formats=["flac", "mp3"],       # Allowed formats
    exclusion_keywords=["live"],   # Custom exclusions
    fuzzy_threshold=80,            # Fuzzy match threshold
)

# Execute search and download
response = await use_case.execute(request)
```

### Backward Compatibility

The advanced search is optional and backward compatible:

```python
# Legacy mode (use_advanced_search=False)
legacy_request = SearchAndDownloadTrackRequest(
    track_id=track_id,
    quality_preference="best",
    use_advanced_search=False,  # Use legacy selection logic
)

# Advanced mode (default)
advanced_request = SearchAndDownloadTrackRequest(
    track_id=track_id,
    use_advanced_search=True,   # Default, can be omitted
    min_bitrate=256,
)
```

## Scoring Algorithm

### Smart Score Calculation

The smart score combines multiple factors with weighted importance:

**Formula:**
```
smart_score = (0.5 × fuzzy_score) + (0.4 × quality_score) + (0.1 × filename_score)
```

**Components:**

1. **Fuzzy Score (50%)**: How well the filename matches the query
   - Uses token-set ratio algorithm from rapidfuzz
   - Handles typos, word order variations, and missing words
   - Configurable threshold (default 80%)

2. **Quality Score (40%)**: Audio quality assessment
   - Format scoring: FLAC (40 pts) > High-quality lossy (30 pts) > MP3 (20 pts)
   - Bitrate scoring: Normalized to 0-40 range (320kbps = 40 pts)
   - File size scoring: Larger files indicate better quality (0-20 pts)

3. **Filename Score (10%)**: Filename quality
   - Bonus for well-formatted names (Artist - Title.ext)
   - Penalty for very long filenames
   - Penalty for excessive special characters
   - Penalty for multiple spaces/underscores

### Quality Score Details

**Format Bonuses:**
- FLAC: 40 points (lossless)
- M4A/OPUS: 30 points (high-quality lossy)
- MP3: 20 points (standard lossy)
- OGG: 15 points
- Other: 10 points

**Bitrate Scoring:**
- FLAC: 40 points if ≥800 kbps, 20 points otherwise
- Lossy: Normalized to 320kbps (linear scale, max 40 points)

**File Size Scoring:**
- Compared to expected size for format and duration
- Larger than expected = higher quality
- Maximum 20 points

## Default Exclusion Keywords

When no custom exclusion keywords are provided, these defaults are used:

- `live` - Live performances
- `remix` - Remixed versions
- `cover` - Cover versions
- `karaoke` - Karaoke versions
- `instrumental` - Instrumental versions
- `acoustic` - Acoustic versions
- `demo` - Demo recordings
- `rehearsal` - Rehearsal recordings

These can be overridden by providing custom exclusion keywords.

## Use Cases

### Use Case 1: High-Quality FLAC Search

```python
filters = SearchFilters(
    min_bitrate=800,           # High bitrate for FLAC
    formats=["flac"],          # Only FLAC
    exclusion_keywords=["live", "remix"],
    fuzzy_threshold=85,        # Strict matching
)

best = service.select_best_match("Artist - Album - Track", results, filters)
```

### Use Case 2: Typo-Tolerant Search

```python
# Query with typo: "Bohemain Rapsody" instead of "Bohemian Rhapsody"
filters = SearchFilters(
    fuzzy_threshold=70,  # Lower threshold for fuzzy matching
)

matches = service.search_with_filters("Bohemain Rapsody", results, filters)
# Still finds "Bohemian Rhapsody" with ~85% match
```

### Use Case 3: Quality Fallback

```python
# Try high quality first
high_quality_filters = SearchFilters(
    min_bitrate=320,
    formats=["flac"],
)

best = service.select_best_match(query, results, high_quality_filters)

if not best:
    # Fallback to lower quality
    fallback_filters = SearchFilters(
        min_bitrate=192,
        formats=["flac", "mp3"],
    )
    best = service.select_best_match(query, results, fallback_filters)
```

### Use Case 4: Custom Exclusions

```python
# Exclude specific versions
filters = SearchFilters(
    exclusion_keywords=["radio edit", "clean version", "explicit"],
    fuzzy_threshold=80,
)

results = service.search_with_filters(query, raw_results, filters)
```

### Use Case 5: Multi-Format Priority

```python
# Prefer FLAC, fallback to high-quality MP3
filters = SearchFilters(
    formats=["flac", "mp3"],
    min_bitrate=256,
)

# Smart scoring will prioritize FLAC (higher format bonus)
ranked = service.search_with_filters(query, results, filters)
```

## Performance Considerations

### Fuzzy Matching Performance

- Token-set ratio algorithm is efficient for typical music filenames
- Threshold of 80+ provides good balance of accuracy and performance
- Lower thresholds (60-70) increase false positives but improve recall

### Recommendations

1. **Default Threshold**: 80% works well for most use cases
2. **Strict Matching**: 90%+ for exact matches only
3. **Relaxed Matching**: 70% for finding alternatives with typos
4. **Minimum Quality**: 256 kbps or higher recommended for good quality

## Testing

Comprehensive test coverage with 22 tests for AdvancedSearchService:

- Fuzzy matching with exact matches and typos
- Quality filters (bitrate, format, combined)
- Exclusion filters (default, custom, case-insensitive)
- Quality scoring (FLAC, MP3, low bitrate)
- Smart scoring algorithm
- Complete search pipeline
- Alternative source scenarios

Run tests:
```bash
pytest tests/unit/application/services/test_advanced_search.py -v
```

## Error Handling

The service is designed to be robust:

- Returns empty list if no matches pass filters
- Returns None if no best match found
- Handles missing fields gracefully (defaults to 0)
- Case-insensitive exclusion matching
- Validates input parameters

## Future Enhancements

Potential improvements for future versions:

1. **Machine Learning Scoring**: Train model on user preferences
2. **User Reputation**: Factor in user upload quality history
3. **Download Success Rate**: Prioritize reliable sources
4. **Semantic Matching**: Understand artist name variations
5. **Configurable Weights**: Allow customization of score components
6. **Caching**: Cache fuzzy match results for performance

## Related Documentation

- [Backend Development Roadmap](backend-development-roadmap.md)
- [Advanced Search Guide](guide/advanced-search-guide.md) (User Guide)
- [Architecture Documentation](architecture.md)

## Support

For issues or questions:
1. Check test examples in `tests/unit/application/services/test_advanced_search.py`
2. Review integration tests in `tests/unit/application/use_cases/test_search_and_download.py`
3. Report issues on GitHub

---

**Version:** 1.0  
**Last Updated:** 2025-11-16  
**Status:** Complete
