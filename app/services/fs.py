import re
import shutil
from pathlib import Path
from typing import List, Optional

from app.config import CLAUDE_DIR, PROJECTS_DIR, READ_ONLY
from app.models import MemoryCreate, MemoryFile, MemoryMeta, MemoryUpdate, Project, SearchResult
from app.services.parser import parse, render


def _decode_project_id(project_id: str) -> str:
    # Each non-alphanumeric char in the original path was encoded as a dash.
    # Heuristic: groups of 2+ consecutive dashes represent path separators or
    # multi-char sequences (e.g. unicode chars in directory names).
    result = re.sub(r'-{2,}', '/', project_id)
    if result.startswith('-'):
        result = '/' + result[1:]
    return result


def _safe_path(project_id: str, filename: str) -> Path:
    if '..' in project_id or '/' in project_id or '\\' in project_id:
        raise ValueError("Invalid project_id")
    if '..' in filename or '/' in filename or '\\' in filename:
        raise ValueError("Invalid filename")
    if not filename.endswith('.md'):
        raise ValueError("Only .md files are allowed")
    path = (PROJECTS_DIR / project_id / "memory" / filename).resolve()
    if not str(path).startswith(str(PROJECTS_DIR.resolve())):
        raise ValueError("Path traversal detected")
    return path


def _backup(path: Path) -> None:
    bak = path.parent / (path.name + '.bak')
    shutil.copy2(path, bak)


def list_projects() -> List[Project]:
    if not PROJECTS_DIR.exists():
        return []
    result = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        mem_dir = d / "memory"
        if not mem_dir.exists():
            continue
        md_files = [
            f for f in mem_dir.glob("*.md")
            if f.name != "MEMORY.md" and not f.name.endswith('.bak')
        ]
        has_index = (mem_dir / "MEMORY.md").exists()
        if not md_files and not has_index:
            continue
        result.append(Project(
            id=d.name,
            label=_decode_project_id(d.name),
            memory_count=len(md_files),
        ))
    return result


def list_memories(project_id: str) -> List[MemoryMeta]:
    if '..' in project_id or '/' in project_id:
        raise ValueError("Invalid project_id")
    mem_dir = PROJECTS_DIR / project_id / "memory"
    if not mem_dir.exists():
        return []
    result: List[MemoryMeta] = []

    index = mem_dir / "MEMORY.md"
    if index.exists():
        content = index.read_text(encoding='utf-8')
        meta, _ = parse(content)
        result.append(MemoryMeta(
            filename="MEMORY.md",
            name=meta.get('name', 'Memory Index'),
            description=meta.get('description', 'Index of all memory files'),
            type='index',
            project_id=project_id,
            is_index=True,
        ))

    for f in sorted(mem_dir.glob("*.md")):
        if f.name == "MEMORY.md" or f.name.endswith('.bak'):
            continue
        try:
            content = f.read_text(encoding='utf-8')
            meta, _ = parse(content)
            result.append(MemoryMeta(
                filename=f.name,
                name=meta.get('name', f.stem),
                description=meta.get('description', ''),
                type=meta.get('type', 'unknown'),
                project_id=project_id,
                is_index=False,
            ))
        except Exception:
            continue
    return result


def read_memory(project_id: str, filename: str) -> MemoryFile:
    path = _safe_path(project_id, filename)
    if not path.exists():
        raise FileNotFoundError(f"{filename} not found in project {project_id}")
    content = path.read_text(encoding='utf-8')
    meta, body = parse(content)
    return MemoryFile(
        filename=filename,
        name=meta.get('name', filename),
        description=meta.get('description', ''),
        type=meta.get('type', 'index' if filename == 'MEMORY.md' else 'unknown'),
        project_id=project_id,
        is_index=filename == 'MEMORY.md',
        body=body,
    )


def write_memory(project_id: str, filename: str, update: MemoryUpdate) -> MemoryFile:
    if READ_ONLY:
        raise PermissionError("Service is in read-only mode")
    path = _safe_path(project_id, filename)
    if not path.exists():
        raise FileNotFoundError(f"{filename} not found")
    _backup(path)
    if filename == 'MEMORY.md':
        path.write_text(update.body, encoding='utf-8')
    else:
        meta = {
            'name': update.name,
            'description': update.description,
            'type': update.type,
        }
        path.write_text(render(meta, update.body), encoding='utf-8')
    return read_memory(project_id, filename)


def create_memory(data: MemoryCreate) -> MemoryFile:
    if READ_ONLY:
        raise PermissionError("Service is in read-only mode")
    filename = data.filename if data.filename.endswith('.md') else data.filename + '.md'
    path = _safe_path(data.project_id, filename)
    if path.exists():
        raise FileExistsError(f"{filename} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        'name': data.name,
        'description': data.description,
        'type': data.type,
    }
    path.write_text(render(meta, data.body), encoding='utf-8')
    return read_memory(data.project_id, filename)


def delete_memory(project_id: str, filename: str) -> None:
    if READ_ONLY:
        raise PermissionError("Service is in read-only mode")
    path = _safe_path(project_id, filename)
    if not path.exists():
        raise FileNotFoundError(f"{filename} not found")
    _backup(path)
    path.unlink()


def search_memories(query: str, type_filter: Optional[str] = None) -> List[SearchResult]:
    query_lower = query.lower()
    results: List[SearchResult] = []
    if not PROJECTS_DIR.exists():
        return results
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        mem_dir = project_dir / "memory"
        if not mem_dir.exists():
            continue
        for f in mem_dir.glob("*.md"):
            if f.name.endswith('.bak'):
                continue
            try:
                content = f.read_text(encoding='utf-8')
                meta, body = parse(content)
                file_type = meta.get('type', 'index' if f.name == 'MEMORY.md' else 'unknown')
                if type_filter and file_type != type_filter:
                    continue
                if query_lower not in content.lower():
                    continue
                idx = content.lower().find(query_lower)
                start = max(0, idx - 60)
                end = min(len(content), idx + len(query) + 60)
                snippet = ('...' if start > 0 else '') + content[start:end].strip() + ('...' if end < len(content) else '')
                results.append(SearchResult(
                    project_id=project_dir.name,
                    project_label=_decode_project_id(project_dir.name),
                    filename=f.name,
                    name=meta.get('name', f.stem),
                    type=file_type,
                    snippet=snippet,
                ))
            except Exception:
                continue
    return results[:50]
