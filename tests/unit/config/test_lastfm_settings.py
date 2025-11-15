"""Test for Last.fm configuration check."""


from soulspot.config.settings import LastfmSettings


def test_lastfm_is_configured_with_both_credentials():
    """Test is_configured returns True when both credentials are provided."""
    settings = LastfmSettings(api_key="test_key", api_secret="test_secret")
    assert settings.is_configured() is True


def test_lastfm_is_configured_without_key():
    """Test is_configured returns False when API key is missing."""
    settings = LastfmSettings(api_key="", api_secret="test_secret")
    assert settings.is_configured() is False


def test_lastfm_is_configured_without_secret():
    """Test is_configured returns False when API secret is missing."""
    settings = LastfmSettings(api_key="test_key", api_secret="")
    assert settings.is_configured() is False


def test_lastfm_is_configured_with_empty_values():
    """Test is_configured returns False when both are empty."""
    settings = LastfmSettings(api_key="", api_secret="")
    assert settings.is_configured() is False


def test_lastfm_is_configured_with_whitespace():
    """Test is_configured returns False when credentials are only whitespace."""
    settings = LastfmSettings(api_key="   ", api_secret="   ")
    assert settings.is_configured() is False
