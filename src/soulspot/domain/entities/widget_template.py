"""Widget template system for custom widget development."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WidgetTemplateConfig:
    """Configuration schema for widget templates."""

    # Basic metadata
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""

    # Template information
    template_path: str = ""
    icon: str = "puzzle"
    category: str = "general"

    # Widget behavior
    supports_config: bool = False
    config_schema: dict[str, Any] = field(default_factory=dict)
    default_config: dict[str, Any] = field(default_factory=dict)

    # Size and layout
    default_span_cols: int = 6
    min_span_cols: int = 4
    max_span_cols: int = 12

    # Data and updates
    data_endpoint: str = ""
    supports_sse: bool = False
    sse_events: list[str] = field(default_factory=list)
    poll_interval: int = 5  # seconds

    # Permissions and features
    requires_auth: bool = False
    permissions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """Validate template configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.name or not self.name.strip():
            errors.append("Widget name is required")

        if not self.description or not self.description.strip():
            errors.append("Widget description is required")

        if not self.template_path or not self.template_path.strip():
            errors.append("Template path is required")

        if self.default_span_cols < 1 or self.default_span_cols > 12:
            errors.append("Default span_cols must be between 1 and 12")

        if self.min_span_cols < 1 or self.min_span_cols > 12:
            errors.append("Min span_cols must be between 1 and 12")

        if self.max_span_cols < 1 or self.max_span_cols > 12:
            errors.append("Max span_cols must be between 1 and 12")

        if self.min_span_cols > self.max_span_cols:
            errors.append("Min span_cols cannot be greater than max span_cols")

        if self.poll_interval < 0:
            errors.append("Poll interval must be 0 or greater")

        return errors

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WidgetTemplateConfig":
        """Create config from dictionary.

        Args:
            data: Dictionary with configuration data

        Returns:
            WidgetTemplateConfig instance
        """
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            template_path=data.get("template_path", ""),
            icon=data.get("icon", "puzzle"),
            category=data.get("category", "general"),
            supports_config=data.get("supports_config", False),
            config_schema=data.get("config_schema", {}),
            default_config=data.get("default_config", {}),
            default_span_cols=data.get("default_span_cols", 6),
            min_span_cols=data.get("min_span_cols", 4),
            max_span_cols=data.get("max_span_cols", 12),
            data_endpoint=data.get("data_endpoint", ""),
            supports_sse=data.get("supports_sse", False),
            sse_events=data.get("sse_events", []),
            poll_interval=data.get("poll_interval", 5),
            requires_auth=data.get("requires_auth", False),
            permissions=data.get("permissions", []),
            tags=data.get("tags", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "template_path": self.template_path,
            "icon": self.icon,
            "category": self.category,
            "supports_config": self.supports_config,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "default_span_cols": self.default_span_cols,
            "min_span_cols": self.min_span_cols,
            "max_span_cols": self.max_span_cols,
            "data_endpoint": self.data_endpoint,
            "supports_sse": self.supports_sse,
            "sse_events": self.sse_events,
            "poll_interval": self.poll_interval,
            "requires_auth": self.requires_auth,
            "permissions": self.permissions,
            "tags": self.tags,
        }


@dataclass
class WidgetTemplate:
    """Widget template with metadata and configuration."""

    id: str
    type: str
    config: WidgetTemplateConfig
    is_enabled: bool = True
    is_system: bool = False

    def __post_init__(self) -> None:
        """Validate widget template after initialization."""
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Invalid widget template configuration: {', '.join(errors)}")

    @classmethod
    def from_file(cls, template_file: Path) -> "WidgetTemplate":
        """Load widget template from JSON file.

        Args:
            template_file: Path to JSON template file

        Returns:
            WidgetTemplate instance

        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If template is invalid
        """
        if not template_file.exists():
            raise FileNotFoundError(f"Template file not found: {template_file}")

        try:
            with open(template_file) as f:
                data = json.load(f)

            widget_id = data.get("id", "")
            widget_type = data.get("type", "")
            is_enabled = data.get("is_enabled", True)
            is_system = data.get("is_system", False)

            config = WidgetTemplateConfig.from_dict(data.get("config", {}))

            return cls(
                id=widget_id,
                type=widget_type,
                config=config,
                is_enabled=is_enabled,
                is_system=is_system,
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in template file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading template: {e}")

    def to_dict(self) -> dict[str, Any]:
        """Convert template to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "type": self.type,
            "config": self.config.to_dict(),
            "is_enabled": self.is_enabled,
            "is_system": self.is_system,
        }

    def to_json(self) -> str:
        """Convert template to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)
