from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.models import ConfigFile, RawUpdate
from app.services import fs

router = APIRouter(prefix="/api/project-config", tags=["project-config"])


@router.get("", response_model=List[ConfigFile])
def list_project_config(project_id: str = Query(...)):
    try:
        return fs.list_project_config(project_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/file", response_model=ConfigFile)
def get_project_config(project_id: str = Query(...), name: str = Query(...)):
    try:
        return fs.read_project_config_file(project_id, name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.put("/file", response_model=ConfigFile)
def update_project_config(update: RawUpdate, project_id: str = Query(...), name: str = Query(...)):
    try:
        return fs.write_project_config_file(project_id, name, update.raw_content)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
