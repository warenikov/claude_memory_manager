import shutil
from pathlib import Path
from typing import List, Tuple

import yaml

from app.config import READ_ONLY, SKILLS_DIR
from app.models import SkillFile, SkillMeta
from app.services.fs import estimate_tokens, to_host_path


def _iter_skills() -> List[Tuple[str, Path, str]]:
    """Yield (id, file_to_edit, type) for every skill on disk.

    type = "yaml"   for `<id>.skill.yaml` (single-file)
    type = "bundle" for `<id>/SKILL.md`   (bundle directory)
    """
    if not SKILLS_DIR.exists():
        return []
    out: List[Tuple[str, Path, str]] = []
    for entry in sorted(SKILLS_DIR.iterdir()):
        try:
            if entry.is_file() and entry.name.endswith(".skill.yaml"):
                sid = entry.name[: -len(".skill.yaml")]
                out.append((sid, entry, "yaml"))
            elif entry.is_dir():
                md = entry / "SKILL.md"
                if md.exists():
                    out.append((entry.name, md, "bundle"))
        except OSError:
            continue
    return out


def _parse_meta(content: str, skill_type: str) -> dict:
    """Pull `name` + `description` out of skill content."""
    if skill_type == "yaml":
        try:
            data = yaml.safe_load(content) or {}
        except Exception:
            return {"name": "", "description": ""}
        if not isinstance(data, dict):
            return {"name": "", "description": ""}
        return {
            "name": str(data.get("name") or ""),
            "description": str(data.get("description") or ""),
        }

    # bundle: SKILL.md with `---\n<yaml>\n---` frontmatter
    if not content.startswith("---"):
        return {"name": "", "description": ""}
    end = content.find("\n---", 4)
    if end < 0:
        return {"name": "", "description": ""}
    fm = content[3:end].strip()
    try:
        data = yaml.safe_load(fm) or {}
    except Exception:
        return {"name": "", "description": ""}
    if not isinstance(data, dict):
        return {"name": "", "description": ""}
    return {
        "name": str(data.get("name") or ""),
        "description": str(data.get("description") or ""),
    }


def list_skills() -> List[SkillMeta]:
    result: List[SkillMeta] = []
    for sid, path, stype in _iter_skills():
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = _parse_meta(content, stype)
        result.append(SkillMeta(
            id=sid,
            name=meta["name"] or sid,
            description=meta["description"],
            skill_type=stype,
            path=to_host_path(path),
            tokens=estimate_tokens(content),
        ))
    return result


def _validate_id(skill_id: str) -> None:
    if not skill_id or "/" in skill_id or "\\" in skill_id or ".." in skill_id:
        raise ValueError("Invalid skill id")


def _resolve(skill_id: str) -> Tuple[Path, str]:
    _validate_id(skill_id)
    for sid, path, stype in _iter_skills():
        if sid == skill_id:
            return path, stype
    raise FileNotFoundError(f"Skill {skill_id!r} not found")


def read_skill(skill_id: str) -> SkillFile:
    path, stype = _resolve(skill_id)
    content = path.read_text(encoding="utf-8")
    meta = _parse_meta(content, stype)
    return SkillFile(
        id=skill_id,
        name=meta["name"] or skill_id,
        description=meta["description"],
        skill_type=stype,
        path=to_host_path(path),
        tokens=estimate_tokens(content),
        content=content,
    )


def write_skill(skill_id: str, content: str) -> SkillFile:
    if READ_ONLY:
        raise PermissionError("Service is in read-only mode")
    path, _ = _resolve(skill_id)
    bak = path.parent / (path.name + ".bak")
    shutil.copy2(path, bak)
    path.write_text(content, encoding="utf-8")
    return read_skill(skill_id)
