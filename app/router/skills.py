from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.models import RawUpdate, SkillFile, SkillMeta
from app.services import skills

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=List[SkillMeta])
def list_all():
    return skills.list_skills()


@router.get("/file", response_model=SkillFile)
def get_skill(id: str = Query(...)):
    try:
        return skills.read_skill(id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.put("/file", response_model=SkillFile)
def update_skill(update: RawUpdate, id: str = Query(...)):
    try:
        return skills.write_skill(id, update.raw_content)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


# ── Bundle internal .md docs (linked from SKILL.md) ──

@router.get("/doc")
def get_doc(id: str = Query(...), doc: str = Query(...)):
    try:
        return skills.read_skill_doc(id, doc)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.put("/doc")
def update_doc(update: RawUpdate, id: str = Query(...), doc: str = Query(...)):
    try:
        return skills.write_skill_doc(id, doc, update.raw_content)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
