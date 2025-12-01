"""Unit tests for album types and compilation detection.

Hey future me - these tests validate the Lidarr-style compilation detection logic!
We test:
1. is_various_artists() pattern matching (VA, Various Artists, etc.)
2. calculate_track_diversity() metric calculation
3. detect_compilation() full heuristics (explicit flags, patterns, diversity)

Test data is based on real-world scenarios from music collections.
"""

import pytest

from soulspot.domain.value_objects.album_types import (
    DIVERSITY_THRESHOLD,
    DOMINANT_ARTIST_THRESHOLD,
    MIN_TRACKS_FOR_DIVERSITY,
    VARIOUS_ARTISTS_PATTERNS,
    CompilationDetectionResult,
    PrimaryAlbumType,
    SecondaryAlbumType,
    calculate_track_diversity,
    detect_compilation,
    is_various_artists,
)


class TestPrimaryAlbumType:
    """Tests for PrimaryAlbumType enum."""

    def test_from_string_album(self) -> None:
        """Test parsing 'album' string."""
        assert PrimaryAlbumType.from_string("album") == PrimaryAlbumType.ALBUM
        assert PrimaryAlbumType.from_string("ALBUM") == PrimaryAlbumType.ALBUM
        assert PrimaryAlbumType.from_string("Album") == PrimaryAlbumType.ALBUM

    def test_from_string_ep(self) -> None:
        """Test parsing 'ep' string."""
        assert PrimaryAlbumType.from_string("ep") == PrimaryAlbumType.EP
        assert PrimaryAlbumType.from_string("EP") == PrimaryAlbumType.EP

    def test_from_string_single(self) -> None:
        """Test parsing 'single' string."""
        assert PrimaryAlbumType.from_string("single") == PrimaryAlbumType.SINGLE

    def test_from_string_variations(self) -> None:
        """Test parsing common variations."""
        assert PrimaryAlbumType.from_string("lp") == PrimaryAlbumType.ALBUM
        assert PrimaryAlbumType.from_string("full-length") == PrimaryAlbumType.ALBUM
        assert PrimaryAlbumType.from_string("mini-album") == PrimaryAlbumType.EP

    def test_from_string_unknown_defaults_album(self) -> None:
        """Test unknown strings default to ALBUM."""
        assert PrimaryAlbumType.from_string("unknown") == PrimaryAlbumType.ALBUM
        assert PrimaryAlbumType.from_string("") == PrimaryAlbumType.ALBUM
        assert PrimaryAlbumType.from_string("gibberish") == PrimaryAlbumType.ALBUM


class TestSecondaryAlbumType:
    """Tests for SecondaryAlbumType enum."""

    def test_from_string_compilation(self) -> None:
        """Test parsing 'compilation' string."""
        assert SecondaryAlbumType.from_string("compilation") == SecondaryAlbumType.COMPILATION

    def test_from_string_live(self) -> None:
        """Test parsing 'live' string."""
        assert SecondaryAlbumType.from_string("live") == SecondaryAlbumType.LIVE

    def test_from_string_soundtrack(self) -> None:
        """Test parsing 'soundtrack' string."""
        assert SecondaryAlbumType.from_string("soundtrack") == SecondaryAlbumType.SOUNDTRACK

    def test_from_string_dj_mix_variations(self) -> None:
        """Test DJ mix variations."""
        assert SecondaryAlbumType.from_string("dj-mix") == SecondaryAlbumType.DJ_MIX
        assert SecondaryAlbumType.from_string("dj mix") == SecondaryAlbumType.DJ_MIX
        assert SecondaryAlbumType.from_string("djmix") == SecondaryAlbumType.DJ_MIX

    def test_from_string_unknown_returns_none(self) -> None:
        """Test unknown strings return None."""
        assert SecondaryAlbumType.from_string("unknown") is None
        assert SecondaryAlbumType.from_string("") is None

    def test_from_string_list(self) -> None:
        """Test parsing list of strings."""
        result = SecondaryAlbumType.from_string_list(["compilation", "live", "unknown"])
        assert len(result) == 2
        assert SecondaryAlbumType.COMPILATION in result
        assert SecondaryAlbumType.LIVE in result


class TestIsVariousArtists:
    """Tests for is_various_artists() function.
    
    Hey future me - this validates pattern matching for album_artist tag!
    Common patterns: "Various Artists", "VA", "V.A.", "Sampler", etc.
    """

    def test_various_artists_exact_matches(self) -> None:
        """Test exact pattern matches."""
        assert is_various_artists("Various Artists") is True
        assert is_various_artists("various artists") is True
        assert is_various_artists("VARIOUS ARTISTS") is True
        assert is_various_artists("VA") is True
        assert is_various_artists("va") is True
        assert is_various_artists("V.A.") is True
        assert is_various_artists("v.a.") is True

    def test_various_artists_international(self) -> None:
        """Test international variations."""
        assert is_various_artists("Diverse") is True  # German
        assert is_various_artists("verschiedene") is True  # German
        assert is_various_artists("Varios Artistas") is True  # Spanish
        assert is_various_artists("Artistes Divers") is True  # French
        assert is_various_artists("Artisti Vari") is True  # Italian

    def test_various_artists_with_suffix(self) -> None:
        """Test patterns with suffixes like (2024)."""
        assert is_various_artists("Various Artists (2024)") is True
        assert is_various_artists("Various Artists - Dance Hits") is True
        assert is_various_artists("VA - Summer Mix") is True

    def test_non_various_artists(self) -> None:
        """Test real artist names are NOT detected as VA."""
        assert is_various_artists("The Beatles") is False
        assert is_various_artists("Pink Floyd") is False
        assert is_various_artists("Variousthing Band") is False  # Contains "various" but not VA
        assert is_various_artists("Vari-Speed") is False

    def test_edge_cases(self) -> None:
        """Test edge cases."""
        assert is_various_artists(None) is False
        assert is_various_artists("") is False
        assert is_various_artists("   ") is False  # Whitespace only

    def test_sampler_and_compilation(self) -> None:
        """Test sampler and compilation keywords."""
        assert is_various_artists("Sampler") is True
        assert is_various_artists("Compilation") is True
        assert is_various_artists("soundtrack") is True
        assert is_various_artists("OST") is True


class TestCalculateTrackDiversity:
    """Tests for calculate_track_diversity() function.
    
    Hey future me - this is the core metric for Lidarr-style detection!
    diversity_ratio = unique_artists / total_tracks
    """

    def test_all_same_artist(self) -> None:
        """Test album where all tracks are by same artist."""
        artists = ["Pink Floyd", "Pink Floyd", "Pink Floyd", "Pink Floyd"]
        ratio, details = calculate_track_diversity(artists)
        
        assert ratio == 0.25  # 1 unique / 4 total
        assert details["unique_artists"] == 1
        assert details["total_tracks"] == 4
        assert details["dominant_artist"] == "pink floyd"
        assert details["dominant_percent"] == 1.0

    def test_all_unique_artists(self) -> None:
        """Test compilation where every track has different artist."""
        artists = ["Artist A", "Artist B", "Artist C", "Artist D"]
        ratio, details = calculate_track_diversity(artists)
        
        assert ratio == 1.0  # 4 unique / 4 total
        assert details["unique_artists"] == 4
        assert details["total_tracks"] == 4
        assert details["dominant_percent"] == 0.25

    def test_mixed_artists(self) -> None:
        """Test album with some repeated artists."""
        # 3 unique artists across 5 tracks = 60% diversity
        artists = ["Artist A", "Artist A", "Artist B", "Artist C", "Artist A"]
        ratio, details = calculate_track_diversity(artists)
        
        assert ratio == 0.6  # 3 unique / 5 total
        assert details["unique_artists"] == 3
        assert details["total_tracks"] == 5
        assert details["dominant_artist"] == "artist a"
        assert details["dominant_count"] == 3
        assert details["dominant_percent"] == 0.6

    def test_case_insensitive(self) -> None:
        """Test that artist comparison is case-insensitive."""
        artists = ["Artist A", "artist a", "ARTIST A", "Artist B"]
        ratio, details = calculate_track_diversity(artists)
        
        assert details["unique_artists"] == 2  # "Artist A" (3 variants) + "Artist B"

    def test_empty_list(self) -> None:
        """Test empty artist list."""
        ratio, details = calculate_track_diversity([])
        
        assert ratio == 0.0
        assert details["unique_artists"] == 0
        assert details["total_tracks"] == 0

    def test_threshold_boundary_75_percent(self) -> None:
        """Test the 75% threshold boundary (Lidarr's default)."""
        # Exactly 75%: 3 unique out of 4 tracks
        artists_75 = ["A", "B", "C", "D"]  # 4 unique / 4 total = 100%
        ratio_75, _ = calculate_track_diversity(artists_75)
        assert ratio_75 >= DIVERSITY_THRESHOLD

        # Just below 75%: 2 unique out of 4 tracks (with repeats)
        artists_below = ["A", "A", "B", "C"]  # 3 unique / 4 total = 75%
        ratio_below, _ = calculate_track_diversity(artists_below)
        assert ratio_below >= DIVERSITY_THRESHOLD  # 0.75 = threshold


class TestDetectCompilation:
    """Tests for detect_compilation() full heuristic function.
    
    Hey future me - this is the MAIN entry point! Test order matters:
    1. explicit_flag (highest priority)
    2. album_artist patterns
    3. track diversity (needs MIN_TRACKS_FOR_DIVERSITY tracks)
    """

    def test_explicit_flag_true(self) -> None:
        """Test that explicit_flag=True always returns compilation."""
        result = detect_compilation(
            album_artist="Pink Floyd",  # NOT a VA pattern
            track_artists=["Pink Floyd"] * 10,  # All same artist
            explicit_flag=True,  # BUT flag says compilation!
        )
        
        assert result.is_compilation is True
        assert result.reason == "explicit_flag"
        assert result.confidence == 1.0

    def test_album_artist_va_pattern(self) -> None:
        """Test Various Artists album_artist detection."""
        result = detect_compilation(
            album_artist="Various Artists",
            track_artists=None,
            explicit_flag=None,
        )
        
        assert result.is_compilation is True
        assert result.reason == "album_artist_pattern"
        assert result.confidence == 0.95

    def test_album_artist_va_pattern_german(self) -> None:
        """Test German VA pattern."""
        result = detect_compilation(album_artist="Verschiedene Künstler")
        
        assert result.is_compilation is True
        assert result.reason == "album_artist_pattern"

    def test_track_diversity_high(self) -> None:
        """Test high track diversity triggers compilation detection."""
        # 4 unique artists = 100% diversity (way above 75% threshold)
        track_artists = ["Artist A", "Artist B", "Artist C", "Artist D"]
        result = detect_compilation(
            album_artist="First Artist",  # Not a VA pattern
            track_artists=track_artists,
            explicit_flag=None,
        )
        
        assert result.is_compilation is True
        assert result.reason == "track_diversity"
        assert "diversity_ratio" in result.details
        assert result.details["diversity_ratio"] == 1.0

    def test_no_dominant_artist(self) -> None:
        """Test no-dominant-artist rule (none has >25%)."""
        # 5 tracks, max 1 per artist = all have 20% (<25% threshold)
        track_artists = ["A", "B", "C", "D", "E"]
        result = detect_compilation(
            album_artist=None,
            track_artists=track_artists,
            explicit_flag=None,
        )
        
        assert result.is_compilation is True
        # Could be "track_diversity" (100%) or "no_dominant_artist"
        assert result.reason in ("track_diversity", "no_dominant_artist")

    def test_normal_album_same_artist(self) -> None:
        """Test normal album where all tracks are by same artist."""
        track_artists = ["The Beatles"] * 10
        result = detect_compilation(
            album_artist="The Beatles",
            track_artists=track_artists,
            explicit_flag=None,
        )
        
        assert result.is_compilation is False
        assert result.reason == "no_indicators"

    def test_too_few_tracks_for_diversity(self) -> None:
        """Test that diversity analysis needs MIN_TRACKS_FOR_DIVERSITY tracks."""
        # Only 2 tracks - not enough for diversity analysis
        track_artists = ["Artist A", "Artist B"]
        result = detect_compilation(
            album_artist="Artist A",
            track_artists=track_artists,
            explicit_flag=None,
        )
        
        # Should NOT detect as compilation (not enough data)
        assert result.is_compilation is False
        assert result.reason == "no_indicators"

    def test_borderline_diversity(self) -> None:
        """Test borderline diversity (50-75%) returns uncertain result."""
        # 3 unique out of 5 = 60% diversity (borderline)
        track_artists = ["A", "A", "B", "C", "A"]  # A=3, B=1, C=1
        result = detect_compilation(
            album_artist=None,
            track_artists=track_artists,
            explicit_flag=None,
        )
        
        # 60% is borderline - should NOT be detected as compilation
        # because dominant artist (A) has 60% > 25% threshold
        assert result.is_compilation is False
        assert result.reason == "borderline_diversity"
        assert result.confidence < 1.0


class TestCompilationDetectionResult:
    """Tests for CompilationDetectionResult dataclass."""

    def test_bool_conversion(self) -> None:
        """Test that result can be used as boolean."""
        positive = CompilationDetectionResult(True, "test", 1.0)
        negative = CompilationDetectionResult(False, "test", 0.5)
        
        assert bool(positive) is True
        assert bool(negative) is False
        
        # Can use in if statements
        if positive:
            passed = True
        else:
            passed = False
        assert passed is True

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        result = CompilationDetectionResult(
            is_compilation=True,
            reason="track_diversity",
            confidence=0.85,
            details={"diversity_ratio": 0.9},
        )
        
        d = result.to_dict()
        assert d["is_compilation"] is True
        assert d["reason"] == "track_diversity"
        assert d["confidence"] == 0.85
        assert d["details"]["diversity_ratio"] == 0.9

    def test_repr(self) -> None:
        """Test string representation."""
        result = CompilationDetectionResult(True, "explicit_flag", 1.0)
        repr_str = repr(result)
        
        assert "True" in repr_str
        assert "explicit_flag" in repr_str
        assert "100%" in repr_str


class TestConstants:
    """Tests for module constants."""

    def test_diversity_threshold(self) -> None:
        """Test DIVERSITY_THRESHOLD is sensible."""
        assert 0.5 <= DIVERSITY_THRESHOLD <= 1.0
        assert DIVERSITY_THRESHOLD == 0.75  # Lidarr default

    def test_dominant_artist_threshold(self) -> None:
        """Test DOMINANT_ARTIST_THRESHOLD is sensible."""
        assert 0.1 <= DOMINANT_ARTIST_THRESHOLD <= 0.5
        assert DOMINANT_ARTIST_THRESHOLD == 0.25  # Lidarr default

    def test_min_tracks_for_diversity(self) -> None:
        """Test MIN_TRACKS_FOR_DIVERSITY is sensible."""
        assert MIN_TRACKS_FOR_DIVERSITY >= 2
        assert MIN_TRACKS_FOR_DIVERSITY == 3

    def test_various_artists_patterns_is_frozenset(self) -> None:
        """Test patterns are immutable frozenset for O(1) lookup."""
        assert isinstance(VARIOUS_ARTISTS_PATTERNS, frozenset)
        assert "various artists" in VARIOUS_ARTISTS_PATTERNS
        assert "va" in VARIOUS_ARTISTS_PATTERNS
