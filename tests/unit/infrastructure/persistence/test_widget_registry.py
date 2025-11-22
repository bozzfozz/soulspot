"""Unit tests for widget registry."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import Widget
from soulspot.infrastructure.persistence.models import WidgetModel
from soulspot.infrastructure.persistence.widget_registry import (
    WIDGET_REGISTRY,
    get_all_widgets,
    get_widget_by_type,
    initialize_widget_registry,
)


class TestWidgetRegistry:
    """Test suite for widget registry functions."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def mock_widget_model(self) -> WidgetModel:
        """Create a mock WidgetModel."""
        model = MagicMock(spec=WidgetModel)
        model.id = 1
        model.type = "active_jobs"
        model.name = "Active Jobs"
        model.template_path = "partials/widgets/active_jobs.html"
        model.default_config = {"refresh_interval": 5, "max_items": 10}
        return model

    async def test_widget_registry_constant(self):
        """Test that WIDGET_REGISTRY is properly defined."""
        assert isinstance(WIDGET_REGISTRY, list)
        assert len(WIDGET_REGISTRY) == 5

        # Check all widgets have required keys
        for widget in WIDGET_REGISTRY:
            assert "type" in widget
            assert "name" in widget
            assert "template_path" in widget
            assert "default_config" in widget

    async def test_widget_registry_types(self):
        """Test that all expected widget types are present."""
        widget_types = {w["type"] for w in WIDGET_REGISTRY}
        expected_types = {
            "active_jobs",
            "spotify_search",
            "missing_tracks",
            "quick_actions",
            "metadata_manager",
        }
        assert widget_types == expected_types

    async def test_initialize_widget_registry_creates_new_widgets(
        self, mock_session: AsyncMock
    ):
        """Test initializing widget registry creates new widgets."""
        # Mock execute to return None (no existing widgets)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        await initialize_widget_registry(mock_session)

        # Verify session.add was called for each widget
        assert mock_session.add.call_count == len(WIDGET_REGISTRY)
        assert mock_session.commit.call_count == 1

    async def test_initialize_widget_registry_updates_existing_widgets(
        self, mock_session: AsyncMock
    ):
        """Test initializing widget registry updates existing widgets."""
        # Create mock existing widgets for each type
        mock_widgets = {}
        for widget_def in WIDGET_REGISTRY:
            mock_existing = MagicMock(spec=WidgetModel)
            mock_existing.type = widget_def["type"]
            mock_existing.name = "Old Name"
            mock_existing.template_path = "old/path.html"
            mock_existing.default_config = {}
            mock_widgets[widget_def["type"]] = mock_existing

        # Mock execute to return the appropriate existing widget based on query
        def mock_execute_side_effect(stmt):
            # Extract the widget type from the WHERE clause
            # This is a simplified mock - in real code we'd parse the statement
            mock_result = AsyncMock()
            # Return the first widget as existing (for testing purposes)
            mock_result.scalar_one_or_none = MagicMock(
                return_value=mock_widgets["active_jobs"]
            )
            return mock_result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        await initialize_widget_registry(mock_session)

        # Verify at least one widget was updated (the mock returns the same widget for all queries)
        # In real scenario with proper mocking, we'd check each widget individually
        assert mock_session.add.call_count == 0
        assert mock_session.commit.call_count == 1

    async def test_initialize_widget_registry_mixed_scenario(
        self, mock_session: AsyncMock
    ):
        """Test initializing widget registry with some existing and some new widgets."""
        # Mock first widget exists, others don't
        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = AsyncMock()
            if call_count == 1:
                # First widget exists
                mock_existing = MagicMock(spec=WidgetModel)
                mock_existing.type = "active_jobs"
                mock_result.scalar_one_or_none = MagicMock(return_value=mock_existing)
            else:
                # Other widgets don't exist
                mock_result.scalar_one_or_none = MagicMock(return_value=None)
            return mock_result

        mock_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        await initialize_widget_registry(mock_session)

        # Verify new widgets were added (all except first one)
        assert mock_session.add.call_count == len(WIDGET_REGISTRY) - 1
        assert mock_session.commit.call_count == 1

    async def test_get_widget_by_type_found(
        self, mock_session: AsyncMock, mock_widget_model: WidgetModel
    ):
        """Test getting a widget by type when it exists."""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_widget_model)
        mock_session.execute = AsyncMock(return_value=mock_result)

        widget = await get_widget_by_type(mock_session, "active_jobs")

        assert widget is not None
        assert isinstance(widget, Widget)
        assert widget.id == 1
        assert widget.type == "active_jobs"
        assert widget.name == "Active Jobs"
        assert widget.template_path == "partials/widgets/active_jobs.html"
        assert widget.default_config == {"refresh_interval": 5, "max_items": 10}

    async def test_get_widget_by_type_not_found(self, mock_session: AsyncMock):
        """Test getting a widget by type when it doesn't exist."""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        widget = await get_widget_by_type(mock_session, "nonexistent")

        assert widget is None

    async def test_get_all_widgets_empty(self, mock_session: AsyncMock):
        """Test getting all widgets when registry is empty."""
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        widgets = await get_all_widgets(mock_session)

        assert widgets == []

    async def test_get_all_widgets_multiple(
        self, mock_session: AsyncMock, mock_widget_model: WidgetModel
    ):
        """Test getting all widgets with multiple entries."""
        # Create multiple mock widgets
        mock_widgets = []
        for i, widget_def in enumerate(WIDGET_REGISTRY[:3]):
            model = MagicMock(spec=WidgetModel)
            model.id = i + 1
            model.type = widget_def["type"]
            model.name = widget_def["name"]
            model.template_path = widget_def["template_path"]
            model.default_config = widget_def["default_config"]
            mock_widgets.append(model)

        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=mock_widgets))
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        widgets = await get_all_widgets(mock_session)

        assert len(widgets) == 3
        assert all(isinstance(w, Widget) for w in widgets)
        assert widgets[0].type == "active_jobs"
        assert widgets[1].type == "spotify_search"
        assert widgets[2].type == "missing_tracks"

    async def test_initialize_widget_registry_logs_correctly(
        self, mock_session: AsyncMock
    ):
        """Test that initialization logs appropriate messages."""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "soulspot.infrastructure.persistence.widget_registry.logger"
        ) as mock_logger:
            await initialize_widget_registry(mock_session)

            # Check that info was logged
            assert mock_logger.info.call_count == 2
            assert "Initializing widget registry" in str(
                mock_logger.info.call_args_list
            )
            assert "Widget registry initialized" in str(mock_logger.info.call_args_list)

            # Check that debug was logged for each widget
            assert mock_logger.debug.call_count == len(WIDGET_REGISTRY)


class TestWidgetRegistryDefaultConfigs:
    """Test suite for widget default configurations."""

    def test_active_jobs_default_config(self):
        """Test active_jobs widget default configuration."""
        widget = next(w for w in WIDGET_REGISTRY if w["type"] == "active_jobs")
        assert widget["default_config"]["refresh_interval"] == 5
        assert widget["default_config"]["max_items"] == 10

    def test_spotify_search_default_config(self):
        """Test spotify_search widget default configuration."""
        widget = next(w for w in WIDGET_REGISTRY if w["type"] == "spotify_search")
        assert widget["default_config"]["search_type"] == "tracks"
        assert widget["default_config"]["max_results"] == 10

    def test_missing_tracks_default_config(self):
        """Test missing_tracks widget default configuration."""
        widget = next(w for w in WIDGET_REGISTRY if w["type"] == "missing_tracks")
        assert widget["default_config"]["auto_detect"] is True
        assert widget["default_config"]["show_found"] is False

    def test_quick_actions_default_config(self):
        """Test quick_actions widget default configuration."""
        widget = next(w for w in WIDGET_REGISTRY if w["type"] == "quick_actions")
        assert widget["default_config"]["actions"] == ["import", "scan", "fix"]
        assert widget["default_config"]["layout"] == "grid"

    def test_metadata_manager_default_config(self):
        """Test metadata_manager widget default configuration."""
        widget = next(w for w in WIDGET_REGISTRY if w["type"] == "metadata_manager")
        assert widget["default_config"]["scope"] == "all"
        assert widget["default_config"]["auto_fix"] is False
        assert widget["default_config"]["max_items"] == 20


class TestWidgetRegistryTemplatePaths:
    """Test suite for widget template paths."""

    def test_all_widgets_have_valid_template_paths(self):
        """Test that all widgets have valid template paths."""
        for widget in WIDGET_REGISTRY:
            assert widget["template_path"].startswith("partials/widgets/")
            assert widget["template_path"].endswith(".html")

    def test_widget_template_paths_unique(self):
        """Test that all widget template paths are unique."""
        paths = [w["template_path"] for w in WIDGET_REGISTRY]
        assert len(paths) == len(set(paths))
