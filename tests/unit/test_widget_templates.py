"""Tests for widget template system."""

from soulspot.application.services.widget_template_registry import (
    WidgetTemplateRegistry,
)
from soulspot.domain.entities.widget_template import (
    WidgetTemplate,
    WidgetTemplateConfig,
)


def test_widget_template_config_validation():
    """Test widget template configuration validation."""
    # Valid configuration
    config = WidgetTemplateConfig(
        name="Test Widget",
        description="A test widget",
        template_path="partials/test_widget.html",
    )
    errors = config.validate()
    assert len(errors) == 0

    # Invalid configuration - missing name
    config = WidgetTemplateConfig(
        name="",
        description="A test widget",
        template_path="partials/test_widget.html",
    )
    errors = config.validate()
    assert "Widget name is required" in errors

    # Invalid configuration - missing description
    config = WidgetTemplateConfig(
        name="Test Widget",
        description="",
        template_path="partials/test_widget.html",
    )
    errors = config.validate()
    assert "Widget description is required" in errors

    # Invalid configuration - missing template path
    config = WidgetTemplateConfig(
        name="Test Widget",
        description="A test widget",
        template_path="",
    )
    errors = config.validate()
    assert "Template path is required" in errors

    # Invalid configuration - bad span_cols
    config = WidgetTemplateConfig(
        name="Test Widget",
        description="A test widget",
        template_path="partials/test_widget.html",
        default_span_cols=15,
    )
    errors = config.validate()
    assert "Default span_cols must be between 1 and 12" in errors


def test_widget_template_creation():
    """Test widget template creation."""
    config = WidgetTemplateConfig(
        name="Test Widget",
        description="A test widget",
        template_path="partials/test_widget.html",
        icon="test-icon",
        category="testing",
    )

    template = WidgetTemplate(
        id="test_widget",
        type="test_widget",
        config=config,
        is_enabled=True,
        is_system=False,
    )

    assert template.id == "test_widget"
    assert template.type == "test_widget"
    assert template.config.name == "Test Widget"
    assert template.is_enabled is True
    assert template.is_system is False


def test_widget_template_to_dict():
    """Test widget template serialization."""
    config = WidgetTemplateConfig(
        name="Test Widget",
        description="A test widget",
        template_path="partials/test_widget.html",
    )

    template = WidgetTemplate(
        id="test_widget",
        type="test_widget",
        config=config,
    )

    data = template.to_dict()

    assert data["id"] == "test_widget"
    assert data["type"] == "test_widget"
    assert data["config"]["name"] == "Test Widget"
    assert data["config"]["description"] == "A test widget"
    assert data["is_enabled"] is True


def test_widget_template_registry():
    """Test widget template registry."""
    registry = WidgetTemplateRegistry()

    # Should have system widgets registered
    assert len(registry.get_all()) > 0

    # Test get by ID
    active_jobs = registry.get("active_jobs")
    assert active_jobs is not None
    assert active_jobs.config.name == "Active Jobs"
    assert active_jobs.is_system is True

    # Test get all
    templates = registry.get_all()
    assert len(templates) == 5  # 5 system widgets

    # Test get by category
    monitoring_widgets = registry.get_by_category("monitoring")
    assert len(monitoring_widgets) >= 2  # active_jobs and missing_tracks


def test_widget_template_registry_search():
    """Test widget template search."""
    registry = WidgetTemplateRegistry()

    # Search by query
    results = registry.search(query="search")
    assert len(results) >= 1
    assert any(t.config.name == "Spotify Search" for t in results)

    # Search by category
    results = registry.search(category="monitoring")
    assert len(results) >= 2

    # Search by tags
    results = registry.search(tags=["downloads"])
    assert len(results) >= 1
    assert any(t.id == "active_jobs" for t in results)


def test_widget_template_registry_custom_widget():
    """Test registering custom widget."""
    registry = WidgetTemplateRegistry()

    # Register custom widget
    config = WidgetTemplateConfig(
        name="Custom Widget",
        description="A custom test widget",
        template_path="partials/custom_widget.html",
        category="custom",
    )

    template = WidgetTemplate(
        id="custom_widget",
        type="custom_widget",
        config=config,
        is_system=False,
    )

    registry.register(template)

    # Verify registration
    custom = registry.get("custom_widget")
    assert custom is not None
    assert custom.config.name == "Custom Widget"
    assert custom.is_system is False

    # Unregister custom widget (should succeed)
    result = registry.unregister("custom_widget")
    assert result is True

    # Try to unregister system widget (should fail)
    result = registry.unregister("active_jobs")
    assert result is False


def test_widget_template_config_schema():
    """Test widget template with config schema."""
    config = WidgetTemplateConfig(
        name="Configurable Widget",
        description="A widget with configuration",
        template_path="partials/configurable.html",
        supports_config=True,
        config_schema={
            "title": {"type": "string", "default": "Default Title"},
            "count": {"type": "number", "min": 1, "max": 100, "default": 10},
        },
        default_config={
            "title": "My Widget",
            "count": 20,
        },
    )

    errors = config.validate()
    assert len(errors) == 0

    assert config.supports_config is True
    assert "title" in config.config_schema
    assert "count" in config.config_schema
    assert config.default_config["title"] == "My Widget"
    assert config.default_config["count"] == 20
