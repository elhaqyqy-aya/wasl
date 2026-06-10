from pydantic import BaseModel
from typing import Generic, TypeVar, List, Optional
T = TypeVar("T")

class PaginationParams(BaseModel):
    page: int = 1
    limit: int = 20

    @property
    def offset(self):
        return (self.page - 1) * self.limit

class PagedResponse(BaseModel, Generic[T]):
    data: List[T]
    total: int
    page: int
    limit: int
    pages: int

def make_paged(items, total, page, limit):
    import math
    return {"data": items, "total": total, "page": page, "limit": limit, "pages": math.ceil(total/limit) if limit else 1}
