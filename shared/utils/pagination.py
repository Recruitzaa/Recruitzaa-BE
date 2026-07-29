"""
shared/utils/pagination.py — Pagination utilities.
"""

from __future__ import annotations

from shared.utils.serialization import PaginatedResponse


def paginate(items: list, total: int, page: int, page_size: int) -> PaginatedResponse:
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_prev=page > 1,
    )


def get_skip(page: int, page_size: int) -> int:
    """Calculate MongoDB/SQL offset from page number."""
    return (page - 1) * page_size
