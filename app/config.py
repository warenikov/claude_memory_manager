from pathlib import Path
import os
import platform


def _default_claude_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "Claude"
        return Path.home() / "AppData" / "Roaming" / "Claude"
    return Path.home() / ".claude"


CLAUDE_DIR = Path(os.getenv("CLAUDE_DIR", _default_claude_dir()))
READ_ONLY = os.getenv("READ_ONLY", "false").lower() == "true"
PROJECTS_DIR = CLAUDE_DIR / "projects"

# Path where host ~ is mounted inside Docker (for project config files)
_host_home_env = os.getenv("HOST_HOME", "")
HOST_HOME = Path(_host_home_env) if _host_home_env else None

# Actual ~ path on host (for path encoding verification AND display)
HOST_HOME_REAL = os.getenv("HOST_HOME_REAL", "")


def _detect_host_os(home_real: str) -> str:
    if not home_real:
        return "unix"
    if "\\" in home_real or (len(home_real) >= 2 and home_real[1] == ":"):
        return "windows"
    return "unix"


HOST_OS = _detect_host_os(HOST_HOME_REAL)
HOST_SEP = "\\" if HOST_OS == "windows" else "/"


def _compute_claude_dir_real() -> str:
    if not HOST_HOME_REAL:
        return ""
    if HOST_OS == "windows":
        return f"{HOST_HOME_REAL}\\AppData\\Roaming\\Claude"
    return f"{HOST_HOME_REAL}/.claude"


# Actual ~/.claude path on host (for display)
CLAUDE_DIR_REAL = os.getenv("CLAUDE_DIR_REAL", "") or _compute_claude_dir_real()
