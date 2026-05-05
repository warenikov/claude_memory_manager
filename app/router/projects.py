from typing import List

from fastapi import APIRouter

from app.models import Project
from app.services.fs import list_projects

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=List[Project])
def get_projects():
    return list_projects()
