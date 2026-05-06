import re
import shutil
from collections import deque
from pathlib import Path
from typing import List, Optional

from app.config import CLAUDE_DIR, CLAUDE_DIR_REAL, HOST_HOME, HOST_HOME_REAL, HOST_SEP, PROJECTS_DIR, READ_ONLY
from app.models import ConfigFile, MemoryCreate, MemoryFile, MemoryMeta, MemoryUpdate, RawUpdate, Project, SearchResult
from app.services.parser import parse, render


def to_host_path(mounted: Path) -> str:
    """Translate a Docker-mounted path back to its real host path for display.

    /host-home/<rel>  -> HOST_HOME_REAL/<rel>     (project files)
    /data/<rel>       -> CLAUDE_DIR_REAL/<rel>    (~/.claude files)
    """
    s = str(mounted)

    def _join(base: str, rel: str) -> str:
        if not rel:
            return base
        if HOST_SEP == "\\":
            rel = rel.replace("/", "\\")
        return f"{base}{HOST_SEP}{rel}"

    if HOST_HOME and HOST_HOME_REAL:
        h = str(HOST_HOME)
        if s == h:
            return HOST_HOME_REAL
        if s.startswith(h + "/"):
            return _join(HOST_HOME_REAL, s[len(h) + 1:])

    if CLAUDE_DIR_REAL:
        c = str(CLAUDE_DIR)
        if s == c:
            return CLAUDE_DIR_REAL
        if s.startswith(c + "/"):
            return _join(CLAUDE_DIR_REAL, s[len(c) + 1:])

    return s


def estimate_tokens(text: str) -> int:
    """Approximate Claude token count.
    ASCII (English/code) ≈ 4 chars/token, non-ASCII (Cyrillic/CJK) ≈ ~1.5 chars/token.
    """
    if not text:
        return 0
    ascii_count = sum(1 for c in text if c.isascii())
    other_count = len(text) - ascii_count
    return max(1, round(ascii_count / 4 + other_count / 1.5))


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
        index_path = mem_dir / "MEMORY.md"
        has_index = index_path.exists()
        if not md_files and not has_index:
            continue
        total_tokens = 0
        for f in md_files:
            try:
                total_tokens += estimate_tokens(f.read_text(encoding='utf-8'))
            except Exception:
                pass
        if has_index:
            try:
                total_tokens += estimate_tokens(index_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        result.append(Project(
            id=d.name,
            label=_decode_project_id(d.name),
            memory_count=len(md_files),
            total_tokens=total_tokens,
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
            tokens=estimate_tokens(content),
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
                tokens=estimate_tokens(content),
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
        file_path=to_host_path(path),
        tokens=estimate_tokens(content),
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


def read_raw(project_id: str, filename: str) -> str:
    path = _safe_path(project_id, filename)
    if not path.exists():
        raise FileNotFoundError(f"{filename} not found in project {project_id}")
    return path.read_text(encoding='utf-8')


def write_raw(project_id: str, filename: str, update: RawUpdate) -> MemoryFile:
    if READ_ONLY:
        raise PermissionError("Service is in read-only mode")
    path = _safe_path(project_id, filename)
    if not path.exists():
        raise FileNotFoundError(f"{filename} not found")
    _backup(path)
    path.write_text(update.raw_content, encoding='utf-8')
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


# ── Global config files ──────────────────────────────────────────────────────

_GLOBAL_FILES = [
    ("CLAUDE.md",           "markdown"),
    ("settings.json",       "json"),
    ("settings.local.json", "json"),
    (".mcp.json",           "json"),
]


def list_global_files() -> List[ConfigFile]:
    result = []
    for name, ftype in _GLOBAL_FILES:
        path = CLAUDE_DIR / name
        tokens = 0
        if path.exists():
            try:
                tokens = estimate_tokens(path.read_text(encoding='utf-8'))
            except Exception:
                pass
        result.append(ConfigFile(name=name, path=to_host_path(path), exists=path.exists(), file_type=ftype, tokens=tokens))
    return result


def read_global_file(name: str) -> ConfigFile:
    for fname, ftype in _GLOBAL_FILES:
        if fname == name:
            path = CLAUDE_DIR / name
            content = path.read_text(encoding='utf-8') if path.exists() else ''
            return ConfigFile(name=name, path=to_host_path(path), exists=path.exists(), file_type=ftype, content=content, tokens=estimate_tokens(content))
    raise ValueError(f"Unknown global file: {name!r}")


def write_global_file(name: str, content: str) -> ConfigFile:
    if READ_ONLY:
        raise PermissionError("Service is in read-only mode")
    for fname, ftype in _GLOBAL_FILES:
        if fname == name:
            path = CLAUDE_DIR / name
            if path.exists():
                _backup(path)
            path.write_text(content, encoding='utf-8')
            return ConfigFile(name=name, path=to_host_path(path), exists=True, file_type=ftype, content=content, tokens=estimate_tokens(content))
    raise ValueError(f"Unknown global file: {name!r}")


# ── Project config files ─────────────────────────────────────────────────────

_PROJECT_CONFIG_FILES = [
    ("CLAUDE.md",                   "markdown"),
    (".claude/settings.json",       "json"),
    (".claude/settings.local.json", "json"),
]


def _encode_path(path_str: str) -> str:
    return ''.join(ch if (ch.isascii() and ch.isalnum()) else '-' for ch in path_str)


def _find_project_path(project_id: str) -> Optional[Path]:
    """BFS through HOST_HOME mount to find the directory that encodes to project_id."""
    if HOST_HOME is None or not HOST_HOME.exists():
        return None

    def encode_as_host(mounted: Path) -> str:
        if HOST_HOME_REAL:
            try:
                rel = mounted.relative_to(HOST_HOME)
                host_path = str(Path(HOST_HOME_REAL) / rel)
            except ValueError:
                host_path = str(mounted)
        else:
            host_path = str(mounted)
        return _encode_path(host_path)

    queue: deque = deque([(HOST_HOME, 0)])
    visited = 0
    while queue and visited < 3000:
        current, depth = queue.popleft()
        visited += 1
        encoded = encode_as_host(current)
        if encoded == project_id:
            return current
        if depth >= 5 or not project_id.startswith(encoded):
            continue
        try:
            for child in sorted(current.iterdir()):
                if child.is_dir():
                    queue.append((child, depth + 1))
        except (PermissionError, OSError):
            pass
    return None


def list_project_config(project_id: str) -> List[ConfigFile]:
    if '..' in project_id or '/' in project_id:
        raise ValueError("Invalid project_id")
    project_path = _find_project_path(project_id)
    result = []
    for rel, ftype in _PROJECT_CONFIG_FILES:
        if project_path:
            path = project_path / rel
            tokens = 0
            if path.exists():
                try:
                    tokens = estimate_tokens(path.read_text(encoding='utf-8'))
                except Exception:
                    pass
            result.append(ConfigFile(name=rel, path=to_host_path(path), exists=path.exists(), file_type=ftype, tokens=tokens))
        else:
            result.append(ConfigFile(name=rel, path="", exists=False, file_type=ftype))
    return result


def read_project_config_file(project_id: str, name: str) -> ConfigFile:
    if '..' in project_id or '/' in project_id:
        raise ValueError("Invalid project_id")
    valid = {rel: ft for rel, ft in _PROJECT_CONFIG_FILES}
    if name not in valid:
        raise ValueError(f"Unknown config file: {name!r}")
    project_path = _find_project_path(project_id)
    if project_path is None:
        raise FileNotFoundError("Project directory not found on host")
    path = project_path / name
    if not path.exists():
        raise FileNotFoundError(f"{name} not found")
    content = path.read_text(encoding='utf-8')
    return ConfigFile(name=name, path=to_host_path(path), exists=True, file_type=valid[name], content=content, tokens=estimate_tokens(content))


def write_project_config_file(project_id: str, name: str, content: str) -> ConfigFile:
    if READ_ONLY:
        raise PermissionError("Service is in read-only mode")
    if '..' in project_id or '/' in project_id:
        raise ValueError("Invalid project_id")
    valid = {rel: ft for rel, ft in _PROJECT_CONFIG_FILES}
    if name not in valid:
        raise ValueError(f"Unknown config file: {name!r}")
    project_path = _find_project_path(project_id)
    if project_path is None:
        raise FileNotFoundError("Project directory not found on host")
    path = project_path / name
    if path.exists():
        _backup(path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return ConfigFile(name=name, path=to_host_path(path), exists=True, file_type=valid[name], content=content, tokens=estimate_tokens(content))
