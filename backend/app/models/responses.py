"""
NEXUS AI — Standard API Response Models
Consistent response envelope for all endpoints.
"""

from typing import Any, Generic, Optional, TypeVar
from datetime import datetime, timezone

from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Generic success response envelope."""

    success: bool = True
    data: T
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: str
    detail: Optional[Any] = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    success: bool = True
    data: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
