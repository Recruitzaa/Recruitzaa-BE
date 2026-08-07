"""
shared/utils/serialization.py — camelCase Pydantic model base.

FE TypeScript uses camelCase for all API response fields.
Using alias_generator ensures Pydantic automatically converts
snake_case field names to camelCase in JSON output.
"""

from typing import Any
from pydantic import BaseModel, ConfigDict


def _to_camel(s: str) -> str:
    """Convert snake_case string to camelCase."""
    components = s.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


class CamelModel(BaseModel):
    """
    Base model that serializes to camelCase JSON.

    Usage:
        class MyResponse(CamelModel):
            display_name: str      # -> "displayName" in JSON
            available_roles: list  # -> "availableRoles" in JSON
    """

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,  # allow both snake_case and camelCase input
        use_enum_values=True,  # serialize enums to their .value
    )


class APIResponse(CamelModel):
    """Standard API envelope for success responses."""

    success: bool = True
    message: str = "OK"
    data: Any = None


class PaginatedResponse(CamelModel):
    """Paginated list response."""

    items: list
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
