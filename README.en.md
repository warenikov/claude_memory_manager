# 🧠 Claude Memory Manager

[Русский](./README.md) · **English**

A web UI for browsing, editing, and auditing everything Claude Code stores locally: auto-memory, global and per-project `CLAUDE.md`, MCP servers, settings, and session logs.

## The problem

Claude Code keeps **several independent layers of memory** in parallel:

1. `CLAUDE.md` — context loaded into every prompt (global and per-project)
2. **Auto-memory** in `~/.claude/projects/<id>/memory/` — Claude decides on its own what to record about you and the project
3. **Settings and MCP servers** — `~/.claude/settings.json`, `.mcp.json`, and their per-project counterparts
4. **JSONL session logs** in `~/.claude/projects/<id>/*.jsonl` — full transcripts of every tool call
5. **File-history snapshots** in `~/.claude/file-history/` — versioned file snapshots

Real-world pain points fall out of this:

- **Opacity.** What rules has Claude already recorded about your style, habits, projects? You can't tell. Browsing this from a file manager is hopeless: hundreds of files spread across encoded project paths, plus global configs in several other places.
- **Stale rules.** Records rot — feedback that was correct half a year ago gets in the way today. They have to be cleaned periodically — but doing it by hand with `cat` + `vim` is grim.
- **Context bloat.** Memory files are loaded into **every** prompt. The bigger they are, the more expensive each session and the faster the context window fills up. The size in tokens is shown nowhere.
- **Configuration scattered everywhere.** Global `~/.claude/CLAUDE.md`, per-project `<repo>/CLAUDE.md`, `~/.claude/.mcp.json`, `~/.claude/settings.json`, `<repo>/.claude/settings.json` — each lives in its own place, in different formats (md / json), and there's no consolidated view.
- **Audit black box.** What Claude **actually** read or edited in your session lives in JSONL logs at `~/.claude/projects/<id>/*.jsonl`, but without a UI it's unreadable.

## The solution

### Memory Files
- All memory files grouped by project, with frontmatter (`name`, `description`, `type`) and a markdown preview
- **Preview / Edit / RAW** — three modes: rendered view, structured editor that parses frontmatter, and raw `.md` editing
- Full-text search across all memory files (Ctrl+K)
- The real host path right in the file header — copy and open in your editor

### Global Config
A dedicated "Global Config" section for fast access and editing:
- `~/.claude/CLAUDE.md` — global instructions
- `~/.claude/settings.json`, `settings.local.json`
- `~/.claude/.mcp.json` — global MCP servers

### Project Config
Inside each project, a "Config" sub-section for files that live in the **actual** project working directory rather than under `~/.claude/`:
- `<project>/CLAUDE.md`
- `<project>/.claude/settings.json`, `settings.local.json`

### Token counter
Every markdown file gets a **token** size estimate (heuristic: ASCII / 4 + non-ASCII / 1.5). You see at a glance which memory files are heavy and weighing down the context. Per-project totals in the sidebar, section totals in the header.

### Activity — session audit
A JSONL log viewer with two modes: historical (Sessions) and online (Live).

**Sessions** — lazy parsing: the session list opens instantly (just `stat()` plus the first 30 lines for a preview); the full file is parsed only when you click into a specific session. A per-file mtime cache makes repeat opens instant.

Each session has three tabs:
- **Token Burn** — Chart.js stacked bar by day; four series: input / output / cache create / cache read. Shows where tokens actually go
- **File Graph** — force-directed graph (Cytoscape + fcose). Nodes = files, size = touch count, color = file extension. Edges = temporal proximity of two files in the tool-call stream. Hover highlights neighbours and shows the per-tool breakdown (Read / Edit / Write). **Right-click** on a node → context menu with Copy full path / filename / parent directory
- **Sequence** — a chronological feed of every `Read / Edit / Write / MultiEdit / NotebookEdit` in the session, newest on top. Sticky day separators (using the client-local timezone — sessions can be resumed via `--resume` and a single session can stretch across several days). Substring filter on filename/path and per-tool toggles. Times are shown in the browser's timezone

**Live** — observe Claude as it works, in real time. Server-Sent Events stream: every 1.5 seconds the backend scans only active JSONL files (mtime within the last 10 minutes), reads new bytes after the saved offset, parses, and pushes to the client. Partial-line guard — only bytes up to the last `\n` are consumed; the rest is picked up on the next iteration:

- **Grafana-style refresh indicator** in the header: a pulsing dot on every tick, "refreshed Ns ago · every 1.5s", stale state (amber) if the server hasn't responded for > 3× the tick interval
- For each event: time in local TZ, color-coded tool badge (Read = blue, Edit = amber, Write = red), **color-coded project pill** (deterministic color per `project_id` hash — the same project is always the same color), short session ID, filename, directory
- Pause / Resume and Clear feed
- Auto-scroll only kicks in when you're already at the bottom (scroll up and the stream stops yanking you back down)
- Memory cap of 500 events, oldest get trimmed
- Project filter: when a single project is selected, the project pill is hidden (everything is one color anyway)
- Right-click on a row → the same path-copy context menu

### Safety
- A `.bak` backup is written next to the file before every write or delete
- Optional `READ_ONLY=true` in `docker-compose.yml`
- Path traversal protection, filename validation

## Running it

You only need Docker.

```bash
./run.sh
```

The script finds a free port, builds the image, starts the container, waits for it to become ready, and opens the browser. Works on macOS, Linux, and Git Bash / WSL on Windows.

For a fixed port:
```bash
HOST_PORT=8081 docker compose up -d --build
```

## OS support

Paths are detected automatically based on the format of `HOST_HOME_REAL`:

| OS | `~/.claude` mount | Global CLAUDE_DIR |
|----|-------------------|--------------------|
| macOS / Linux | `~/.claude` | `~/.claude` |
| Windows (Git Bash / WSL) | `${USERPROFILE}/.claude` | `${USERPROFILE}/.claude` |

Inside the container, `~/.claude` is mounted at `/data:rw` and the home directory at `/host-home:ro` (needed for access to `<project>/CLAUDE.md` files in real working directories). Internally, paths are translated back to host format for the UI — you see the familiar `/Users/alex/...` or `C:\Users\alex\...` rather than Docker-internal `/host-home/...`.

## Map of Claude's memory

```
~/.claude/                          ← global config dir
├── CLAUDE.md                       ← global instructions          [Global Config → CLAUDE.md]
├── settings.json                   ← global settings              [Global Config → settings.json]
├── settings.local.json                                            [Global Config → settings.local.json]
├── .mcp.json                       ← global MCP servers           [Global Config → .mcp.json]
└── projects/<encoded-path>/
    ├── *.jsonl                     ← session transcripts          [Activity → Sessions]
    ├── memory/                     ← auto-memory                  [Projects → <project> → Memory Files]
    │   ├── MEMORY.md               ← index
    │   ├── user_*.md
    │   ├── feedback_*.md
    │   ├── project_*.md
    │   └── reference_*.md
    └── ...

<project-root>/                     ← actual project directory
├── CLAUDE.md                       ← project-level instructions   [Projects → <project> → Config]
└── .claude/
    ├── settings.json                                              [Projects → <project> → Config]
    └── settings.local.json
```

## Architecture

- **FastAPI** + uvicorn — REST API, serves the SPA
- **Alpine.js + Tailwind (via CDN)** — no bundler, everything in a single `index.html`
- **Cytoscape.js** + `fcose` — force-directed file graph
- **Chart.js** — stacked bar for tokens
- **JSONL parsing** — streaming, with a per-file mtime cache
- **Host path resolution** — BFS over `/host-home` comparing encoded paths (Claude encodes non-ASCII-alnum characters as `-`); works with Cyrillic and any non-Latin paths

## API

| Method | URL | Purpose |
|--------|-----|---------|
| `GET` | `/api/projects` | List of projects with token totals |
| `GET` | `/api/memories?project_id=` | Memory file list |
| `GET/PUT/POST/DELETE` | `/api/memories/file?project_id=&filename=` | CRUD on memory files with frontmatter parsing |
| `GET/PUT` | `/api/memories/raw?project_id=&filename=` | RAW access to file content |
| `GET/PUT` | `/api/global/file?name=` | Global configs |
| `GET/PUT` | `/api/project-config/file?project_id=&name=` | Project-level configs |
| `GET` | `/api/logs/sessions?project_id=&days=` | Session list (lazy) |
| `GET` | `/api/logs/session-detail?session_id=&project_id=` | Full parse of one session |
| `GET` | `/api/logs/live` | Server-Sent Events: live stream of file-touch events (1.5s tick) |
| `GET` | `/api/search?q=` | Full-text search across memory files |

## Project layout

```
.
├── app/
│   ├── main.py                  # FastAPI app, router registration
│   ├── config.py                # CLAUDE_DIR, OS detection, host-path translation
│   ├── models.py                # Pydantic models
│   ├── services/
│   │   ├── fs.py                # File CRUD, host-side project path resolver
│   │   ├── parser.py            # Frontmatter parse/render
│   │   └── logs.py              # JSONL parser + per-file mtime cache
│   └── router/
│       ├── projects.py          # /api/projects
│       ├── memories.py          # /api/memories[/raw|/file]
│       ├── global_files.py      # /api/global
│       ├── project_config.py    # /api/project-config
│       ├── search.py            # /api/search
│       └── logs.py              # /api/logs
├── frontend/
│   └── index.html               # SPA: Alpine + Tailwind + Chart.js + Cytoscape
├── docker-compose.yml
├── Dockerfile
└── run.sh                       # auto-port + browser open
```

## License

MIT
