from typing import List, Optional

from fastapi import APIRouter, Query

from app.models import SearchResult
from app.services.fs import search_memories

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=List[SearchResult])
def search(
    q: str = Query(..., min_length=2),
    type: Optional[str] = Query(None),
):
    return search_memories(q, type)
