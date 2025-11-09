"""Tests for settings management."""

import pytest

from soulspot.config import Settings, get_settings
from soulspot.config.settings import Profile


class TestSettings:
    """Test Settings configuration."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.app_name == "SoulSpot Bridge"
        assert settings.app_env == "development"
        assert settings.profile == Profile.SIMPLE
        assert settings.debug is True
        assert settings.log_level == "INFO"

    def test_database_defaults(self):
        """Test database default settings."""
        settings = Settings()
        assert settings.database.url == "sqlite+aiosqlite:///./soulspot.db"
        assert settings.database.echo is False
        assert settings.database.pool_size == 5

    def test_api_defaults(self):
        """Test API default settings."""
        settings = Settings()
        assert settings.api.host == "0.0.0.0"
        assert settings.api.port == 8000
        assert settings.api.workers == 1
        assert "http://localhost:8000" in settings.api.cors_origins

    def test_storage_defaults(self):
        """Test storage default settings."""
        settings = Settings()
        assert settings.storage.download_path.is_absolute()
        assert settings.storage.music_path.is_absolute()
        assert settings.storage.artwork_path.is_absolute()
        assert settings.storage.temp_path.is_absolute()

    def test_simple_profile(self):
        """Test simple profile detection."""
        settings = Settings(profile=Profile.SIMPLE)
        assert settings.is_simple_profile() is True
        assert settings.is_standard_profile() is False

    def test_standard_profile(self):
        """Test standard profile detection."""
        settings = Settings(profile=Profile.STANDARD)
        assert settings.is_simple_profile() is False
        assert settings.is_standard_profile() is True

    def test_environment_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("APP_NAME", "Test App")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("LOG_LEVEL", "ERROR")

        # Clear cache before testing
        get_settings.cache_clear()

        settings = Settings()
        assert settings.app_name == "Test App"
        assert settings.debug is False
        assert settings.log_level == "ERROR"

    def test_nested_environment_override(self, monkeypatch):
        """Test nested settings override via environment."""
        monkeypatch.setenv("DATABASE__URL", "postgresql://localhost/test")
        monkeypatch.setenv("API__PORT", "9000")

        settings = Settings()
        assert settings.database.url == "postgresql://localhost/test"
        assert settings.api.port == 9000

    def test_cors_origins_from_string(self):
        """Test CORS origins parsing from comma-separated string."""
        settings = Settings(
            api={"cors_origins": "http://a.com,http://b.com,http://c.com"}
        )
        assert len(settings.api.cors_origins) == 3
        assert "http://a.com" in settings.api.cors_origins
        assert "http://b.com" in settings.api.cors_origins

    def test_secret_key_production_validation(self):
        """Test secret key validation in production."""
        with pytest.raises(
            ValueError, match="Secret key must be changed in production"
        ):
            Settings(
                app_env="production",
                secret_key="change-me-to-a-random-secret-key-in-production",
            )

    def test_secret_key_production_with_valid_key(self):
        """Test secret key validation passes with valid key in production."""
        settings = Settings(
            app_env="production",
            secret_key="a" * 32,  # Valid secret key
        )
        assert settings.secret_key == "a" * 32

    def test_ensure_directories(self, tmp_path):
        """Test directory creation."""
        settings = Settings(
            storage={
                "download_path": tmp_path / "downloads",
                "music_path": tmp_path / "music",
                "artwork_path": tmp_path / "artwork",
                "temp_path": tmp_path / "tmp",
            }
        )

        settings.ensure_directories()

        assert (tmp_path / "downloads").exists()
        assert (tmp_path / "music").exists()
        assert (tmp_path / "artwork").exists()
        assert (tmp_path / "tmp").exists()

    def test_get_settings_caching(self):
        """Test settings singleton caching."""
        # Clear cache before testing
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2  # Same instance

    def test_api_port_validation(self):
        """Test API port validation."""
        with pytest.raises(ValueError):
            Settings(api={"port": 0})  # Too low

        with pytest.raises(ValueError):
            Settings(api={"port": 70000})  # Too high

        # Valid port should work
        settings = Settings(api={"port": 8080})
        assert settings.api.port == 8080

    def test_slskd_defaults(self):
        """Test slskd default settings."""
        settings = Settings()
        assert settings.slskd.url == "http://localhost:5030"
        assert settings.slskd.username == "admin"
        assert settings.slskd.api_key is None

    def test_spotify_defaults(self):
        """Test Spotify default settings."""
        settings = Settings()
        assert settings.spotify.client_id == ""
        assert (
            settings.spotify.redirect_uri
            == "http://localhost:8000/auth/spotify/callback"
        )

    def test_musicbrainz_defaults(self):
        """Test MusicBrainz default settings."""
        settings = Settings()
        assert settings.musicbrainz.app_name == "SoulSpot-Bridge"
        assert settings.musicbrainz.app_version == "0.1.0"
        assert settings.musicbrainz.contact == ""
