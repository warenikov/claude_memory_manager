from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services import logs

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/sessions")
def sessions(project_id: Optional[str] = None, days: int = Query(30, ge=0, le=3650)):
    return logs.list_sessions(project_id, days)


@router.get("/live")
async def live():
    """Server-sent events stream of file-touch events as Claude works."""
    return StreamingResponse(
        logs.live_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/session-detail")
def session_detail(session_id: str, project_id: Optional[str] = None):
    d = logs.get_session_detail(session_id, project_id)
    if d is None:
        raise HTTPException(404, "Session not found")
    return d


# ── Aggregate endpoints (kept for cross-session analysis, not used by default UI) ──

@router.get("/stats")
def stats(project_id: Optional[str] = None, days: int = Query(30, ge=0, le=3650)):
    return logs.get_stats(project_id, days)


@router.get("/token-burn")
def token_burn(project_id: Optional[str] = None, days: int = Query(30, ge=0, le=3650)):
    return logs.get_token_burn(project_id, days)


@router.get("/file-graph")
def file_graph(project_id: Optional[str] = None, days: int = Query(30, ge=0, le=3650),
               top_n: int = Query(50, ge=5, le=300)):
    return logs.get_file_graph(project_id, days, top_n)
