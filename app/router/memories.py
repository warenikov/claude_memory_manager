from typing import List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.models import MemoryCreate, MemoryFile, MemoryMeta, MemoryUpdate
from app.services import fs

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("", response_model=List[MemoryMeta])
def list_memories(project_id: str = Query(...)):
    try:
        return fs.list_memories(project_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/file", response_model=MemoryFile)
def get_memory(
    project_id: str = Query(...),
    filename: str = Query(...),
):
    try:
        return fs.read_memory(project_id, filename)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/file", response_model=MemoryFile)
def update_memory(
    update: MemoryUpdate,
    project_id: str = Query(...),
    filename: str = Query(...),
):
    try:
        return fs.write_memory(project_id, filename, update)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("", response_model=MemoryFile, status_code=201)
def create_memory(data: MemoryCreate):
    try:
        return fs.create_memory(data)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/file", status_code=204)
def delete_memory(
    project_id: str = Query(...),
    filename: str = Query(...),
):
    try:
        fs.delete_memory(project_id, filename)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return Response(status_code=204)
