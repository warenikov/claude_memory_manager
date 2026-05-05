from pathlib import Path
import os

CLAUDE_DIR = Path(os.getenv("CLAUDE_DIR", Path.home() / ".claude"))
READ_ONLY = os.getenv("READ_ONLY", "false").lower() == "true"
PROJECTS_DIR = CLAUDE_DIR / "projects"
