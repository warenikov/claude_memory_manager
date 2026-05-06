import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from app.config import PROJECTS_DIR

_FILE_CACHE: dict = {}   # Path -> (mtime, list[event])

_FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}


def _iter_jsonl_files() -> Iterable[Path]:
    if not PROJECTS_DIR.exists():
        return
    for d in PROJECTS_DIR.iterdir():
        if d.is_dir():
            yield from d.glob("*.jsonl")


def _parse_line(d: dict, project_id: str):
    ts = d.get("timestamp")
    if not ts:
        return
    sid = d.get("sessionId") or ""
    msg = d.get("message") or {}

    if d.get("type") == "assistant":
        usage = msg.get("usage") or {}
        if usage and (usage.get("input_tokens") or usage.get("output_tokens")
                      or usage.get("cache_creation_input_tokens") or usage.get("cache_read_input_tokens")):
            yield {
                "kind": "tok",
                "ts": ts,
                "p": project_id,
                "s": sid,
                "in": usage.get("input_tokens", 0) or 0,
                "out": usage.get("output_tokens", 0) or 0,
                "cc": usage.get("cache_creation_input_tokens", 0) or 0,
                "cr": usage.get("cache_read_input_tokens", 0) or 0,
            }

    content = msg.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            name = item.get("name") or ""
            if name not in _FILE_TOOLS:
                continue
            inp = item.get("input") or {}
            fpath = inp.get("file_path") or inp.get("path")
            if not fpath or not isinstance(fpath, str):
                continue
            yield {
                "kind": "file",
                "ts": ts,
                "p": project_id,
                "s": sid,
                "tool": name,
                "f": fpath,
            }


def _events_for_file(path: Path) -> list:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    cached = _FILE_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    events: list = []
    proj_id = path.parent.name
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                events.extend(_parse_line(d, proj_id))
    except Exception:
        return []
    _FILE_CACHE[path] = (mtime, events)
    return events


def _all_events() -> list:
    out: list = []
    for p in _iter_jsonl_files():
        out.extend(_events_for_file(p))
    return out


def _filter(events, project_id: Optional[str] = None, days: Optional[int] = None):
    cutoff = None
    if days and days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    for e in events:
        if project_id and e["p"] != project_id:
            continue
        if cutoff and e["ts"] < cutoff:
            continue
        yield e


def get_token_burn(project_id: Optional[str] = None, days: int = 30):
    by_day: dict = defaultdict(lambda: {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0})
    for e in _filter(_all_events(), project_id, days):
        if e["kind"] != "tok":
            continue
        day = e["ts"][:10]
        by_day[day]["input"] += e["in"]
        by_day[day]["output"] += e["out"]
        by_day[day]["cache_create"] += e["cc"]
        by_day[day]["cache_read"] += e["cr"]
    return [
        {"date": d, **v, "total": v["input"] + v["output"] + v["cache_create"] + v["cache_read"]}
        for d, v in sorted(by_day.items())
    ]


def get_file_graph(project_id: Optional[str] = None, days: int = 30,
                   top_n: int = 50, min_edge_weight: int = 2):
    touches: Counter = Counter()
    tool_breakdown: dict = defaultdict(lambda: Counter())
    by_session: dict = defaultdict(set)

    for e in _filter(_all_events(), project_id, days):
        if e["kind"] != "file":
            continue
        f = e["f"]
        touches[f] += 1
        tool_breakdown[f][e["tool"]] += 1
        if e["s"]:
            by_session[e["s"]].add(f)

    top_files = [f for f, _ in touches.most_common(top_n)]
    top_set = set(top_files)

    edges: Counter = Counter()
    for files in by_session.values():
        files_top = sorted(files & top_set)
        for i in range(len(files_top)):
            for j in range(i + 1, len(files_top)):
                edges[(files_top[i], files_top[j])] += 1

    nodes = []
    for f in top_files:
        p = Path(f)
        nodes.append({
            "id": f,
            "label": p.name,
            "value": touches[f],
            "ext": p.suffix.lstrip(".") or "",
            "path": f,
            "tools": dict(tool_breakdown[f]),
        })

    edges_out = [
        {"from": a, "to": b, "value": w}
        for (a, b), w in edges.most_common()
        if w >= min_edge_weight
    ]
    return {"nodes": nodes, "edges": edges_out}


def _quick_meta(path: Path) -> dict:
    """Lightweight session metadata: stat + first user prompt only."""
    try:
        st = path.stat()
    except OSError:
        return None  # type: ignore
    info = {
        "session_id": path.stem,
        "project_id": path.parent.name,
        "size_bytes": st.st_size,
        "modified": st.st_mtime,
        "preview": "",
        "first_ts": "",
    }
    try:
        with path.open(encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 40 and info["preview"] and info["first_ts"]:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                ts = d.get("timestamp")
                if ts and not info["first_ts"]:
                    info["first_ts"] = ts
                if not info["preview"] and d.get("type") == "user":
                    msg = d.get("message") or {}
                    c = msg.get("content")
                    text = None
                    if isinstance(c, str):
                        text = c
                    elif isinstance(c, list):
                        for item in c:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text = item.get("text") or ""
                                break
                    if text:
                        text = text.strip()
                        # skip wrapped system/command messages
                        if not (text.startswith("<") and ">" in text[:60]):
                            info["preview"] = text[:200]
    except Exception:
        pass
    return info


def list_sessions(project_id: Optional[str] = None, days: Optional[int] = None) -> list:
    cutoff_mtime = None
    if days and days > 0:
        cutoff_mtime = (datetime.now() - timedelta(days=days)).timestamp()
    out = []
    for path in _iter_jsonl_files():
        if project_id and path.parent.name != project_id:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if cutoff_mtime and mtime < cutoff_mtime:
            continue
        meta = _quick_meta(path)
        if meta:
            out.append(meta)
    out.sort(key=lambda s: -s["modified"])
    return out


def get_session_detail(session_id: str, project_id: Optional[str] = None) -> Optional[dict]:
    target: Optional[Path] = None
    for path in _iter_jsonl_files():
        if path.stem != session_id:
            continue
        if project_id and path.parent.name != project_id:
            continue
        target = path
        break
    if target is None:
        return None

    events = _events_for_file(target)

    by_day: dict = defaultdict(lambda: {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0})
    file_touches: Counter = Counter()
    file_tools: dict = defaultdict(lambda: Counter())
    tools: Counter = Counter()
    first_ts = ""
    last_ts = ""

    for e in events:
        if not first_ts or e["ts"] < first_ts:
            first_ts = e["ts"]
        if e["ts"] > last_ts:
            last_ts = e["ts"]
        if e["kind"] == "tok":
            day = e["ts"][:10]
            by_day[day]["input"] += e["in"]
            by_day[day]["output"] += e["out"]
            by_day[day]["cache_create"] += e["cc"]
            by_day[day]["cache_read"] += e["cr"]
        else:
            file_touches[e["f"]] += 1
            file_tools[e["f"]][e["tool"]] += 1
            tools[e["tool"]] += 1

    burn = [
        {"date": d, **v, "total": v["input"] + v["output"] + v["cache_create"] + v["cache_read"]}
        for d, v in sorted(by_day.items())
    ]
    tot = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
    for v in by_day.values():
        for k in tot:
            tot[k] += v[k]
    tot["total"] = tot["input"] + tot["output"] + tot["cache_create"] + tot["cache_read"]

    # File graph: nodes = files; edges = temporal adjacency within session.
    file_events = sorted([e for e in events if e["kind"] == "file"], key=lambda x: x["ts"])
    WINDOW = 5
    edges_count: Counter = Counter()
    for i in range(len(file_events)):
        for j in range(i + 1, min(i + WINDOW + 1, len(file_events))):
            a, b = file_events[i]["f"], file_events[j]["f"]
            if a == b:
                continue
            key = (a, b) if a < b else (b, a)
            edges_count[key] += 1

    nodes = []
    for f, count in file_touches.items():
        p = Path(f)
        nodes.append({
            "id": f,
            "label": p.name,
            "value": count,
            "ext": p.suffix.lstrip(".") or "",
            "path": f,
            "tools": dict(file_tools[f]),
        })
    nodes.sort(key=lambda n: -n["value"])

    edges = [
        {"from": a, "to": b, "value": w}
        for (a, b), w in edges_count.most_common(300)
    ]

    return {
        "session_id": session_id,
        "project_id": target.parent.name,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "stats": {
            "files": len(file_touches),
            "tools": dict(tools),
            "tokens": tot,
        },
        "token_burn": burn,
        "file_graph": {"nodes": nodes, "edges": edges},
    }


def get_stats(project_id: Optional[str] = None, days: int = 30):
    sessions: set = set()
    files: set = set()
    tot_in = tot_out = tot_cc = tot_cr = 0
    tool_counts: Counter = Counter()
    daily_active: set = set()

    for e in _filter(_all_events(), project_id, days):
        if e["s"]:
            sessions.add(e["s"])
        daily_active.add(e["ts"][:10])
        if e["kind"] == "tok":
            tot_in += e["in"]
            tot_out += e["out"]
            tot_cc += e["cc"]
            tot_cr += e["cr"]
        else:
            files.add(e["f"])
            tool_counts[e["tool"]] += 1

    return {
        "sessions": len(sessions),
        "files": len(files),
        "active_days": len(daily_active),
        "tokens": {
            "input": tot_in,
            "output": tot_out,
            "cache_create": tot_cc,
            "cache_read": tot_cr,
            "total": tot_in + tot_out + tot_cc + tot_cr,
        },
        "tools": dict(tool_counts),
    }
