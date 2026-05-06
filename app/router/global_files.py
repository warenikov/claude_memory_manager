from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.models import ConfigFile, RawUpdate
from app.services import fs

router = APIRouter(prefix="/api/global", tags=["global"])


@router.get("", response_model=List[ConfigFile])
def list_global():
    return fs.list_global_files()


@router.get("/file", response_model=ConfigFile)
def get_global(name: str = Query(...)):
    try:
        return fs.read_global_file(name)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/file", response_model=ConfigFile)
def update_global(update: RawUpdate, name: str = Query(...)):
    try:
        return fs.write_global_file(name, update.raw_content)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
