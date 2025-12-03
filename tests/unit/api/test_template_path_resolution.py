# AI-Model: Copilot
"""Unit tests for template path resolution in UI router.

This test validates that the template directory is correctly resolved relative to
the ui.py file location, ensuring it works both in development (source tree) and
production (installed package) environments.
"""

from pathlib import Path

import pytest


class TestTemplatePathResolution:
    """Test template path is correctly resolved."""

    def test_templates_directory_exists(self):
        """Verify templates directory path exists."""
        from soulspot.api.routers.ui import _TEMPLATES_DIR

        assert _TEMPLATES_DIR.exists(), (
            f"Templates directory not found: {_TEMPLATES_DIR}"
        )

    def test_templates_directory_is_absolute(self):
        """Verify templates directory path is absolute."""
        from soulspot.api.routers.ui import _TEMPLATES_DIR

        assert _TEMPLATES_DIR.is_absolute(), (
            "Templates directory path should be absolute"
        )

    def test_templates_directory_contains_index_html(self):
        """Verify templates directory contains index.html."""
        from soulspot.api.routers.ui import _TEMPLATES_DIR

        index_html = _TEMPLATES_DIR / "index.html"
        assert index_html.exists(), f"index.html not found at {index_html}"

    def test_jinja2_templates_instance_configured(self):
        """Verify Jinja2Templates instance is properly configured."""
        from soulspot.api.routers.ui import templates

        # Check that the templates object has been initialized
        assert templates is not None
        assert hasattr(templates, "env")

    def test_jinja2_can_load_index_template(self):
        """Verify Jinja2 can actually load the index.html template."""
        from soulspot.api.routers.ui import templates

        # This would raise TemplateNotFound if path is wrong
        template = templates.env.get_template("index.html")
        assert template is not None
        assert template.name == "index.html"

    def test_template_search_path_is_correct(self):
        """Verify Jinja2 loader search path is correctly set."""
        from soulspot.api.routers.ui import _TEMPLATES_DIR, templates

        search_paths = templates.env.loader.searchpath
        assert len(search_paths) > 0, "No search paths configured"
        assert str(_TEMPLATES_DIR) in search_paths, (
            f"Template directory {_TEMPLATES_DIR} not in search paths: {search_paths}"
        )

    def test_templates_directory_relative_to_module(self):
        """Verify templates directory is correctly computed relative to ui.py."""
        from soulspot.api.routers import ui

        # Get the ui.py file location
        ui_file = Path(ui.__file__)

        # Template dir should be: ui.py -> routers/ -> api/ -> soulspot/ -> templates/
        expected_templates_dir = ui_file.parent.parent.parent / "templates"

        from soulspot.api.routers.ui import _TEMPLATES_DIR

        assert expected_templates_dir == _TEMPLATES_DIR, (
            f"Template directory mismatch: {_TEMPLATES_DIR} != {expected_templates_dir}"
        )

    def test_multiple_templates_accessible(self):
        """Verify multiple common templates can be loaded."""
        from soulspot.api.routers.ui import templates

        template_names = [
            "index.html",
            "playlists.html",
            "downloads.html",
            "base.html",
        ]

        for name in template_names:
            try:
                template = templates.env.get_template(name)
                assert template is not None, f"Failed to load {name}"
                assert template.name == name
            except Exception as e:
                pytest.fail(f"Failed to load template {name}: {e}")
