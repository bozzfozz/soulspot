"""Pagination schemas for API responses."""

from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for pagination."""

    page: int = Field(default=1, ge=1, description="Page number (starts at 1)")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Number of items per page"
    )

    @property
    def skip(self) -> int:
        """Calculate number of records to skip."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get the limit (same as page_size)."""
        return self.page_size


class PaginatedResponse[T](BaseModel):
    """Generic paginated response model."""

    items: list[T] = Field(description="List of items for current page")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Number of items per page")
    pages: int = Field(description="Total number of pages")

    @classmethod
    def create(
        cls, items: list[T], total: int, page: int, page_size: int
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
