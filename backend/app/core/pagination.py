import math
from typing import Any, Dict, List, Optional, Sequence, TypeVar
from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.common import PaginatedResponse

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


def get_pagination_params(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size (max 100)"),
) -> PaginationParams:
    """Dependency that parses and validates pagination query parameters."""
    return PaginationParams(page=page, page_size=page_size)


async def paginate_select(
    db: AsyncSession,
    select_query: Select,
    page_params: PaginationParams,
    sort_column: Optional[Any] = None,
    sort_order: str = "desc",
) -> tuple[Sequence[Any], int, int]:
    """
    Apply safe pagination and sorting to a SQLAlchemy Select statement.
    Returns (items, total_count, total_pages).
    """
    # 1. Total count
    count_subquery = select_query.order_by(None).subquery()
    count_query = select(func.count()).select_from(count_subquery)
    count_result = await db.execute(count_query)
    total = count_result.scalar_one_or_none() or 0

    # 2. Sorting
    if sort_column is not None:
        if sort_order.lower() == "asc":
            select_query = select_query.order_by(asc(sort_column))
        else:
            select_query = select_query.order_by(desc(sort_column))

    # 3. Limit & Offset
    offset = (page_params.page - 1) * page_params.page_size
    paginated_query = select_query.offset(offset).limit(page_params.page_size)

    result = await db.execute(paginated_query)
    items = result.scalars().all()

    total_pages = math.ceil(total / page_params.page_size) if total > 0 else 1
    return items, total, total_pages
