"""Widget template system for custom widget development."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Listen future me, WidgetTemplateConfig is a CONFIGURATION SCHEMA not a domain entity! It defines
# what a widget TYPE supports (not a specific widget instance). config_schema is JSON Schema for
# widget configuration (e.g., {"type": "object", "properties": {"refresh_interval": {...}}}). The
# default_config provides initial values when adding widget to page. supports_sse=True means widget
# uses Server-Sent Events for live updates. poll_interval is fallback if SSE not available. The
# validate() method returns error list (empty = valid) - use before saving to DB to catch bad templates!
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

    # Yo, validate() checks ALL business rules for widget template config! Returns list of error
    # messages (empty list = valid). We check required fields, valid ranges, logical consistency
    # (min <= max). Use this BEFORE persisting to DB or registering widget. If you skip validation,
    # bad configs will cause runtime errors when rendering widgets! The errors list lets you show
    # ALL problems at once instead of failing on first error. Validation is pure (no side effects).
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

    # Hey, from_dict is a FACTORY METHOD (alternative constructor)! It creates WidgetTemplateConfig
    # from dictionary (e.g., from JSON file or API response). Uses .get() with defaults so missing
    # fields don't crash - we fall back to sensible defaults. This is more lenient than __init__
    # which requires all fields. Use this when loading from external sources (files, network). If
    # you want strict validation, call .validate() after creating from dict!
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

    # Listen, to_dict is the INVERSE of from_dict! Serializes config to dictionary for JSON storage
    # or API responses. The dict structure matches what from_dict expects (round-trip compatible).
    # All values are JSON-serializable (no Path objects, datetime, etc). Use this before json.dumps()
    # or storing in DB JSON column. If you add new fields to config, add them here too!
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


# Yo future me, WidgetTemplate wraps WidgetTemplateConfig with metadata! It's the full template
# definition including id (unique identifier), type (widget type like "recent_downloads"), config
# (the WidgetTemplateConfig), is_enabled (can toggle on/off), is_system (can't delete system widgets).
# __post_init__ validates config on creation - invalid templates can't be created! Use from_file()
# to load templates from JSON files (typical workflow). The id should be same as type usually.
@dataclass
class WidgetTemplate:
    """Widget template with metadata and configuration."""

    id: str
    type: str
    config: WidgetTemplateConfig
    is_enabled: bool = True
    is_system: bool = False

    # Hey, __post_init__ validates the nested config! It calls config.validate() and raises ValueError
    # if any validation errors. This means you CAN'T create invalid WidgetTemplate objects - they fail
    # at construction time. The error message joins all validation errors into single message. This is
    # fail-fast design - catch errors early before they propagate! If template loads from file, any
    # config errors are caught here immediately, not later during rendering.
    def __post_init__(self) -> None:
        """Validate widget template after initialization."""
        errors = self.config.validate()
        if errors:
            raise ValueError(
                f"Invalid widget template configuration: {', '.join(errors)}"
            )

    # Listen, from_file loads widget template from JSON! It's how you register custom widgets - drop
    # a JSON file in templates directory, call this to parse it. Raises FileNotFoundError if missing,
    # ValueError if JSON is malformed or validation fails. The try/except catches json.JSONDecodeError
    # and re-raises as ValueError with clearer message. If this succeeds, template is valid and ready
    # to register in widget registry. Use during app startup to load all available widget types!
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
            raise ValueError(f"Invalid JSON in template file: {e}") from e
        except Exception as e:
            raise ValueError(f"Error loading template: {e}") from e

    # Yo, to_dict serializes entire template to dictionary! Similar to config.to_dict() but includes
    # template-level fields (id, type, is_enabled, is_system). Use this for API responses or saving
    # to DB. The config.to_dict() nests the config object. Round-trip compatible with from_file() -
    # you can to_dict(), json.dumps(), save to file, then from_file() later and get same template!
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

    # Hey, to_json is convenience method that wraps to_dict() + json.dumps()! The indent=2 makes it
    # human-readable (pretty-printed). Use this to export templates or save to files. Equivalent to
    # json.dumps(template.to_dict(), indent=2) but more concise. Returns string, not bytes!
    def to_json(self) -> str:
        """Convert template to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)
