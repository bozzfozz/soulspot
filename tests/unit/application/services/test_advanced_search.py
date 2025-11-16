"""Tests for AdvancedSearchService."""

import pytest

from soulspot.application.services.advanced_search import (
    AdvancedSearchService,
    SearchFilters,
    SearchResult,
)


@pytest.fixture
def search_service():
    """Create search service instance."""
    return AdvancedSearchService()


@pytest.fixture
def sample_results():
    """Sample search results for testing."""
    return [
        {
            "username": "user1",
            "filename": "/music/Artist - Song Name.mp3",
            "size": 7_200_000,
            "bitrate": 320,
            "length": 180,
        },
        {
            "username": "user2",
            "filename": "/music/Artist - Song Name (Live).mp3",
            "size": 6_500_000,
            "bitrate": 256,
            "length": 180,
        },
        {
            "username": "user3",
            "filename": "/music/Artist - Song Name.flac",
            "size": 25_000_000,
            "bitrate": 1000,
            "length": 180,
        },
        {
            "username": "user4",
            "filename": "/music/Artist - Song Name [Remix].mp3",
            "size": 5_000_000,
            "bitrate": 192,
            "length": 180,
        },
        {
            "username": "user5",
            "filename": "/music/Different Artist - Other Song.mp3",
            "size": 4_000_000,
            "bitrate": 160,
            "length": 150,
        },
    ]


class TestFuzzyMatching:
    """Tests for fuzzy matching functionality."""

    def test_apply_fuzzy_matching_exact_match(self, search_service, sample_results):
        """Test fuzzy matching with exact query match."""
        query = "Artist Song Name"
        results = search_service.apply_fuzzy_matching(query, sample_results, threshold=80)

        # Should match most results except the very different one
        assert len(results) >= 3
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(r.fuzzy_score >= 80 for r in results)

    def test_apply_fuzzy_matching_with_typo(self, search_service):
        """Test fuzzy matching handles typos."""
        results = [
            {
                "username": "user1",
                "filename": "/music/Bohemian Rhapsody.mp3",
                "size": 7_000_000,
                "bitrate": 320,
            }
        ]

        # Query with typo
        query = "Bohemain Rapsody"
        matched = search_service.apply_fuzzy_matching(query, results, threshold=70)

        assert len(matched) > 0
        assert matched[0].fuzzy_score >= 70

    def test_apply_fuzzy_matching_threshold(self, search_service, sample_results):
        """Test fuzzy matching threshold filtering."""
        query = "Artist Song Name"

        # High threshold
        results_high = search_service.apply_fuzzy_matching(
            query, sample_results, threshold=95
        )

        # Low threshold
        results_low = search_service.apply_fuzzy_matching(
            query, sample_results, threshold=50
        )

        # Low threshold should return more results
        assert len(results_low) >= len(results_high)

    def test_extract_base_filename(self, search_service):
        """Test filename extraction."""
        assert (
            search_service._extract_base_filename("/path/to/song.mp3")
            == "song"
        )
        assert (
            search_service._extract_base_filename("C:\\Music\\Artist - Title.flac")
            == "Artist - Title"
        )
        assert (
            search_service._extract_base_filename("song")
            == "song"
        )


class TestQualityFilters:
    """Tests for quality filtering functionality."""

    def test_apply_quality_filters_min_bitrate(self, search_service):
        """Test minimum bitrate filtering."""
        results = [
            SearchResult(
                username="user1",
                filename="song1.mp3",
                size=7_000_000,
                bitrate=320,
            ),
            SearchResult(
                username="user2",
                filename="song2.mp3",
                size=5_000_000,
                bitrate=192,
            ),
            SearchResult(
                username="user3",
                filename="song3.mp3",
                size=4_000_000,
                bitrate=128,
            ),
        ]

        filters = SearchFilters(min_bitrate=256)
        filtered = search_service.apply_quality_filters(results, filters)

        assert len(filtered) == 1
        assert filtered[0].bitrate >= 256

    def test_apply_quality_filters_formats(self, search_service):
        """Test format filtering."""
        results = [
            SearchResult(
                username="user1",
                filename="song.flac",
                size=25_000_000,
                bitrate=1000,
            ),
            SearchResult(
                username="user2",
                filename="song.mp3",
                size=7_000_000,
                bitrate=320,
            ),
            SearchResult(
                username="user3",
                filename="song.m4a",
                size=6_000_000,
                bitrate=256,
            ),
        ]

        # Only allow FLAC
        filters = SearchFilters(formats=["flac"])
        filtered = search_service.apply_quality_filters(results, filters)
        assert len(filtered) == 1
        assert filtered[0].filename.endswith(".flac")

        # Allow FLAC and MP3
        filters = SearchFilters(formats=["flac", "mp3"])
        filtered = search_service.apply_quality_filters(results, filters)
        assert len(filtered) == 2

    def test_apply_quality_filters_combined(self, search_service):
        """Test combined quality filters."""
        results = [
            SearchResult(
                username="user1",
                filename="song.flac",
                size=25_000_000,
                bitrate=1000,
            ),
            SearchResult(
                username="user2",
                filename="song_320.mp3",
                size=7_000_000,
                bitrate=320,
            ),
            SearchResult(
                username="user3",
                filename="song_192.mp3",
                size=5_000_000,
                bitrate=192,
            ),
        ]

        # MP3 only, min 256 kbps
        filters = SearchFilters(formats=["mp3"], min_bitrate=256)
        filtered = search_service.apply_quality_filters(results, filters)

        assert len(filtered) == 1
        assert filtered[0].filename.endswith(".mp3")
        assert filtered[0].bitrate >= 256


class TestExclusionFilters:
    """Tests for exclusion keyword filtering."""

    def test_apply_exclusion_filters_default(self, search_service):
        """Test default exclusion keywords."""
        results = [
            SearchResult(
                username="user1",
                filename="Song.mp3",
                size=7_000_000,
                bitrate=320,
            ),
            SearchResult(
                username="user2",
                filename="Song (Live).mp3",
                size=6_000_000,
                bitrate=320,
            ),
            SearchResult(
                username="user3",
                filename="Song [Remix].mp3",
                size=6_500_000,
                bitrate=320,
            ),
        ]

        filtered = search_service.apply_exclusion_filters(results)

        # Should exclude live and remix
        assert len(filtered) == 1
        assert "live" not in filtered[0].filename.lower()
        assert "remix" not in filtered[0].filename.lower()

    def test_apply_exclusion_filters_custom(self, search_service):
        """Test custom exclusion keywords."""
        results = [
            SearchResult(
                username="user1",
                filename="Song.mp3",
                size=7_000_000,
                bitrate=320,
            ),
            SearchResult(
                username="user2",
                filename="Song (Radio Edit).mp3",
                size=5_000_000,
                bitrate=256,
            ),
            SearchResult(
                username="user3",
                filename="Song (Extended).mp3",
                size=8_000_000,
                bitrate=320,
            ),
        ]

        # Custom exclusion
        filtered = search_service.apply_exclusion_filters(
            results, exclusion_keywords=["radio", "extended"]
        )

        assert len(filtered) == 1
        assert "radio" not in filtered[0].filename.lower()
        assert "extended" not in filtered[0].filename.lower()

    def test_apply_exclusion_filters_case_insensitive(self, search_service):
        """Test exclusion is case-insensitive."""
        results = [
            SearchResult(
                username="user1",
                filename="Song (LIVE).mp3",
                size=7_000_000,
                bitrate=320,
            ),
            SearchResult(
                username="user2",
                filename="Song (Live).mp3",
                size=7_000_000,
                bitrate=320,
            ),
            SearchResult(
                username="user3",
                filename="Song (live).mp3",
                size=7_000_000,
                bitrate=320,
            ),
        ]

        filtered = search_service.apply_exclusion_filters(results)

        # All should be excluded regardless of case
        assert len(filtered) == 0


class TestQualityScoring:
    """Tests for quality score calculation."""

    def test_calculate_quality_score_flac(self, search_service):
        """Test quality scoring for FLAC files."""
        result = SearchResult(
            username="user1",
            filename="song.flac",
            size=25_000_000,
            bitrate=1000,
        )

        score = search_service.calculate_quality_score(result)

        # FLAC should get high score
        assert score >= 80

    def test_calculate_quality_score_mp3_320(self, search_service):
        """Test quality scoring for 320kbps MP3."""
        result = SearchResult(
            username="user1",
            filename="song.mp3",
            size=7_200_000,
            bitrate=320,
        )

        score = search_service.calculate_quality_score(result)

        # 320kbps MP3 should get good score
        assert 60 <= score <= 90

    def test_calculate_quality_score_low_bitrate(self, search_service):
        """Test quality scoring for low bitrate files."""
        result = SearchResult(
            username="user1",
            filename="song.mp3",
            size=3_000_000,
            bitrate=128,
        )

        score = search_service.calculate_quality_score(result)

        # Low bitrate should get lower score
        assert score < 70


class TestSmartScoring:
    """Tests for smart score calculation."""

    def test_calculate_smart_score(self, search_service):
        """Test smart score calculation."""
        result = SearchResult(
            username="user1",
            filename="Artist - Song Name.mp3",
            size=7_200_000,
            bitrate=320,
            fuzzy_score=95.0,
        )

        query = "Artist Song Name"
        score = search_service.calculate_smart_score(result, query)

        # Should get high score with good fuzzy match and quality
        assert score >= 70
        assert result.match_score == score

    def test_calculate_filename_quality(self, search_service):
        """Test filename quality scoring."""
        # Good filename
        good_score = search_service._calculate_filename_quality("Artist - Title.mp3")
        assert good_score >= 90

        # Long filename
        long_filename = "a" * 200 + ".mp3"
        long_score = search_service._calculate_filename_quality(long_filename)
        assert long_score < good_score

        # Filename with special characters
        special_filename = "Artist###Title!!!@@@.mp3"
        special_score = search_service._calculate_filename_quality(special_filename)
        assert special_score < good_score


class TestRanking:
    """Tests for result ranking."""

    def test_rank_results(self, search_service):
        """Test result ranking by smart score."""
        results = [
            SearchResult(
                username="user1",
                filename="Artist - Song (Low Quality).mp3",
                size=3_000_000,
                bitrate=128,
                fuzzy_score=90.0,
            ),
            SearchResult(
                username="user2",
                filename="Artist - Song.flac",
                size=25_000_000,
                bitrate=1000,
                fuzzy_score=95.0,
            ),
            SearchResult(
                username="user3",
                filename="Artist - Song.mp3",
                size=7_200_000,
                bitrate=320,
                fuzzy_score=95.0,
            ),
        ]

        query = "Artist Song"
        ranked = search_service.rank_results(results, query)

        # FLAC with good match should be first
        assert ranked[0].filename.endswith(".flac")

        # All results should have match scores
        assert all(r.match_score > 0 for r in ranked)

        # Results should be in descending order
        for i in range(len(ranked) - 1):
            assert ranked[i].match_score >= ranked[i + 1].match_score


class TestCompleteSearch:
    """Tests for complete search pipeline."""

    def test_search_with_filters_complete(self, search_service, sample_results):
        """Test complete search pipeline."""
        query = "Artist Song Name"
        filters = SearchFilters(
            min_bitrate=256,
            formats=["flac", "mp3"],
            exclusion_keywords=["live", "remix"],
            fuzzy_threshold=80,
        )

        results = search_service.search_with_filters(query, sample_results, filters)

        # Should filter out low bitrate, wrong format, and excluded keywords
        assert len(results) > 0
        for result in results:
            assert result.bitrate >= 256
            assert result.filename.endswith((".flac", ".mp3"))
            assert "live" not in result.filename.lower()
            assert "remix" not in result.filename.lower()
            assert result.fuzzy_score >= 80

        # Results should be ranked
        for i in range(len(results) - 1):
            assert results[i].match_score >= results[i + 1].match_score

    def test_select_best_match(self, search_service, sample_results):
        """Test selecting best match from results."""
        query = "Artist Song Name"
        filters = SearchFilters(min_bitrate=256)

        best = search_service.select_best_match(query, sample_results, filters)

        assert best is not None
        assert best.bitrate >= 256
        # Should prefer FLAC with good match
        assert best.filename.endswith(".flac")

    def test_select_best_match_no_results(self, search_service):
        """Test selecting best match with no results."""
        query = "Artist Song Name"
        filters = SearchFilters(min_bitrate=10000)  # Impossible bitrate

        best = search_service.select_best_match(query, [], filters)

        assert best is None

    def test_search_with_filters_default(self, search_service, sample_results):
        """Test search with default filters."""
        query = "Artist Song Name"

        # Should use default exclusions (live, remix, etc.)
        results = search_service.search_with_filters(query, sample_results)

        # Should exclude live and remix versions by default
        for result in results:
            assert "live" not in result.filename.lower()
            assert "remix" not in result.filename.lower()


class TestAlternativeSourceScenarios:
    """Tests for alternative source handling scenarios."""

    def test_fuzzy_matching_enables_alternative_sources(self, search_service):
        """Test that fuzzy matching helps find alternative sources."""
        # Simulate a scenario where exact match fails but fuzzy finds alternatives
        results = [
            {
                "username": "user1",
                "filename": "/music/Beatles - Let It Be.mp3",
                "size": 7_000_000,
                "bitrate": 320,
            },
            {
                "username": "user2",
                "filename": "/music/The Beatles - Let It Be.mp3",
                "size": 7_200_000,
                "bitrate": 320,
            },
        ]

        # Query without "The"
        query = "Beatles Let It Be"
        matched = search_service.apply_fuzzy_matching(query, results, threshold=75)

        # Both should match due to fuzzy matching
        assert len(matched) == 2

    def test_quality_fallback_scenario(self, search_service):
        """Test quality fallback when preferred quality not available."""
        results = [
            SearchResult(
                username="user1",
                filename="song.mp3",
                size=5_000_000,
                bitrate=192,
                fuzzy_score=95.0,
            ),
            SearchResult(
                username="user2",
                filename="song.mp3",
                size=7_200_000,
                bitrate=320,
                fuzzy_score=90.0,
            ),
        ]

        # Prefer high bitrate, but lower bitrate has better fuzzy match
        query = "song"
        ranked = search_service.rank_results(results, query)

        # Should balance quality and match score
        assert len(ranked) == 2
        # Higher quality should win overall
        assert ranked[0].bitrate == 320
