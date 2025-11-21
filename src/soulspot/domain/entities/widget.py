"""Dashboard widget system domain entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Widget:
    """Widget entity representing a widget type in the registry."""

    id: int
    type: str
    name: str
    template_path: str
    default_config: dict[str, Any] | None = None

    # Hey future me, __post_init__ runs AFTER dataclass creates the object! Use it for validation
    # that needs access to all fields. We validate that type/name/template_path aren't empty or
    # whitespace-only (the .strip() catches "   " strings). If validation fails, the object is
    # NEVER created - constructor raises ValueError immediately. Don't put expensive operations
    # here (DB calls, API requests) - this runs on EVERY Widget creation including test fixtures!
    def __post_init__(self) -> None:
        """Validate widget data."""
        if not self.type or not self.type.strip():
            raise ValueError("Widget type cannot be empty")
        if not self.name or not self.name.strip():
            raise ValueError("Widget name cannot be empty")
        if not self.template_path or not self.template_path.strip():
            raise ValueError("Widget template_path cannot be empty")


@dataclass
class Page:
    """Page entity representing a dashboard page."""

    id: int
    name: str
    slug: str
    is_default: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Yo, slug validation is STRICT here! We only allow alphanumeric + hyphens + underscores because
    # slugs are used in URLs (/dashboard/{slug}) and filesystem paths (template names). If you allow
    # spaces, dots, slashes, etc., you open path traversal vulnerabilities or broken URLs! The all()
    # with generator is efficient - stops checking at first invalid char. I learned this after someone
    # tried slug="../admin" and almost accessed restricted pages. Keep it paranoid!
    def __post_init__(self) -> None:
        """Validate page data."""
        if not self.name or not self.name.strip():
            raise ValueError("Page name cannot be empty")
        if not self.slug or not self.slug.strip():
            raise ValueError("Page slug cannot be empty")
        # Validate slug format (alphanumeric, hyphens, underscores only)
        if not all(c.isalnum() or c in ("-", "_") for c in self.slug):
            raise ValueError(
                "Page slug must contain only alphanumeric characters, hyphens, and underscores"
            )

    # Listen future me, update_name is a DOMAIN METHOD (not just setting self.name = x)! It validates
    # the new name AND updates updated_at timestamp. This is important for audit trails and cache
    # invalidation. If you bypass this and do page.name = "foo" directly, updated_at won't change
    # and UI won't refresh! Always use these domain methods for state changes, not direct field access.
    def update_name(self, name: str) -> None:
        """Update page name."""
        if not name or not name.strip():
            raise ValueError("Page name cannot be empty")
        self.name = name
        self.updated_at = datetime.now(UTC)

    # Hey, this marks page as default! Important: the system should only have ONE default page at
    # a time. This method just sets the flag - it's the CALLER's responsibility to unset other pages!
    # If you call this on multiple pages without unsetting others, you get multiple defaults and UI
    # behavior is undefined. Should probably add a unique constraint in DB but that's not done yet.
    def set_as_default(self) -> None:
        """Set this page as default."""
        self.is_default = True
        self.updated_at = datetime.now(UTC)

    def unset_as_default(self) -> None:
        """Unset this page as default."""
        self.is_default = False
        self.updated_at = datetime.now(UTC)


@dataclass
class WidgetInstance:
    """Widget instance entity representing a placed widget on a page."""

    id: int
    page_id: int
    widget_type: str
    position_row: int = 0
    position_col: int = 0
    span_cols: int = 6  # Default half-width (6 of 12 columns)
    config: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate widget instance data."""
        if self.position_row < 0:
            raise ValueError("Position row cannot be negative")
        if self.position_col < 0 or self.position_col >= 12:
            raise ValueError("Position column must be between 0 and 11")
        if self.span_cols < 1 or self.span_cols > 12:
            raise ValueError("Span columns must be between 1 and 12")
        # Validate widget doesn't extend beyond grid
        if self.position_col + self.span_cols > 12:
            raise ValueError("Widget extends beyond 12-column grid")

    def move_to(self, row: int, col: int) -> None:
        """Move widget to new position."""
        if row < 0:
            raise ValueError("Position row cannot be negative")
        if col < 0 or col >= 12:
            raise ValueError("Position column must be between 0 and 11")
        if col + self.span_cols > 12:
            raise ValueError("Widget would extend beyond 12-column grid")
        self.position_row = row
        self.position_col = col
        self.updated_at = datetime.now(UTC)

    def move_up(self) -> None:
        """Move widget up one row."""
        if self.position_row > 0:
            self.position_row -= 1
            self.updated_at = datetime.now(UTC)

    def move_down(self) -> None:
        """Move widget down one row."""
        self.position_row += 1
        self.updated_at = datetime.now(UTC)

    def move_left(self) -> None:
        """Move widget left one column."""
        if self.position_col > 0:
            self.position_col -= 1
            self.updated_at = datetime.now(UTC)

    def move_right(self) -> None:
        """Move widget right one column."""
        if self.position_col + self.span_cols < 12:
            self.position_col += 1
            self.updated_at = datetime.now(UTC)

    def resize(self, span_cols: int) -> None:
        """Resize widget to new column span."""
        if span_cols < 1 or span_cols > 12:
            raise ValueError("Span columns must be between 1 and 12")
        if self.position_col + span_cols > 12:
            raise ValueError("Widget would extend beyond 12-column grid")
        self.span_cols = span_cols
        self.updated_at = datetime.now(UTC)

    def toggle_size(self) -> None:
        """Toggle widget between common sizes (4, 6, 12 columns)."""
        size_progression = {4: 6, 6: 12, 12: 4}
        new_size = size_progression.get(self.span_cols, 6)
        # Check if new size fits
        if self.position_col + new_size <= 12:
            self.span_cols = new_size
            self.updated_at = datetime.now(UTC)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update widget configuration."""
        self.config = config
        self.updated_at = datetime.now(UTC)
