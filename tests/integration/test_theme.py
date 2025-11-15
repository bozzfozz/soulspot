"""Tests for Harmony theme integration."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from soulspot.config import Settings
from soulspot.main import create_app


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        app_env="development",
        debug=True,
        database={"url": "sqlite+aiosqlite:///:memory:"},
        observability={
            "enable_dependency_health_checks": False,
        },
    )


@pytest.fixture
def client(test_settings):
    """Create test client."""
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        yield test_client


class TestThemeFiles:
    """Test that theme files exist and are valid."""

    def test_theme_css_exists(self):
        """Test that theme.css file exists."""
        theme_css = Path("src/soulspot/static/css/theme.css")
        assert theme_css.exists(), "theme.css should exist"
        assert theme_css.stat().st_size > 0, "theme.css should not be empty"

    def test_colors_json_exists(self):
        """Test that colors.json token file exists."""
        colors_json = Path("design/tokens/colors.json")
        assert colors_json.exists(), "colors.json should exist"

        # Validate JSON structure
        with open(colors_json) as f:
            data = json.load(f)
            assert "colors" in data
            assert "brand" in data["colors"]
            assert "semantic" in data["colors"]
            assert "neutral" in data["colors"]

    def test_typography_json_exists(self):
        """Test that typography.json token file exists."""
        typography_json = Path("design/tokens/typography.json")
        assert typography_json.exists(), "typography.json should exist"

        # Validate JSON structure
        with open(typography_json) as f:
            data = json.load(f)
            assert "typography" in data
            assert "fontFamily" in data["typography"]
            assert "fontSize" in data["typography"]

    def test_tailwind_theme_exists(self):
        """Test that tailwind.theme.js exists."""
        tailwind_theme = Path("design/tailwind.theme.js")
        assert tailwind_theme.exists(), "tailwind.theme.js should exist"
        assert tailwind_theme.stat().st_size > 0, (
            "tailwind.theme.js should not be empty"
        )

    def test_theme_include_exists(self):
        """Test that theme include template exists."""
        theme_include = Path("src/soulspot/templates/includes/_theme.html")
        assert theme_include.exists(), "_theme.html should exist"

        # Check for key content
        content = theme_include.read_text()
        assert "/static/css/theme.css" in content
        assert "harmony" in content.lower()

    def test_theme_sample_exists(self):
        """Test that theme sample template exists."""
        theme_sample = Path("src/soulspot/templates/theme-sample.html")
        assert theme_sample.exists(), "theme-sample.html should exist"

        # Check for key elements
        content = theme_sample.read_text()
        assert "harmony" in content.lower()
        assert "harmony-btn" in content
        assert "harmony-card" in content
        assert "harmony-badge" in content

    def test_design_guidelines_exist(self):
        """Test that design guidelines documentation exists."""
        guidelines = Path("docs/design-guidelines.md")
        assert guidelines.exists(), "design-guidelines.md should exist"

        # Check for key sections
        content = guidelines.read_text()
        assert "Color Palette" in content
        assert "Typography" in content
        assert "Accessibility" in content
        assert "WCAG" in content


class TestThemeRoute:
    """Test theme sample page route."""

    def test_theme_sample_route_accessible(self, client):
        """Test that theme sample page is accessible."""
        response = client.get("/theme-sample")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_theme_sample_contains_harmony_elements(self, client):
        """Test that theme sample page contains Harmony elements."""
        response = client.get("/theme-sample")
        content = response.text

        # Check for key Harmony components
        assert "harmony-btn" in content
        assert "harmony-card" in content
        assert "harmony-badge" in content
        assert "harmony-alert" in content
        assert "color-primary" in content

    def test_theme_sample_includes_theme_css(self, client):
        """Test that theme sample includes theme.css."""
        response = client.get("/theme-sample")
        content = response.text
        assert "/static/css/theme.css" in content


class TestThemeStaticFiles:
    """Test that theme static files are served correctly."""

    def test_theme_css_served(self, client):
        """Test that theme.css is served via static files."""
        response = client.get("/static/css/theme.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

        # Check for key CSS variables
        content = response.text
        assert "--color-primary" in content
        assert "--font-family" in content
        assert "harmony-btn" in content


class TestDesignTokens:
    """Test design token values."""

    def test_primary_color_value(self):
        """Test that primary color is correctly set."""
        with open("design/tokens/colors.json") as f:
            data = json.load(f)
            primary = data["colors"]["brand"]["primary"]["base"]
            assert primary == "#fe4155"

    def test_font_family_includes_inter(self):
        """Test that font family includes Inter."""
        with open("design/tokens/typography.json") as f:
            data = json.load(f)
            fonts = data["typography"]["fontFamily"]["sans"]
            assert "Inter" in fonts

    def test_spacing_scale_defined(self):
        """Test that spacing scale is defined."""
        with open("design/tokens/typography.json") as f:
            data = json.load(f)
            spacing = data["spacing"]
            assert "xs" in spacing
            assert "sm" in spacing
            assert "md" in spacing
            assert "lg" in spacing
            assert "xl" in spacing

    def test_semantic_colors_defined(self):
        """Test that all semantic colors are defined."""
        with open("design/tokens/colors.json") as f:
            data = json.load(f)
            semantic = data["colors"]["semantic"]
            assert "success" in semantic
            assert "warning" in semantic
            assert "danger" in semantic
            assert "info" in semantic
