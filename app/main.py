from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import READ_ONLY
from app.router import global_files, logs, memories, project_config, projects, search, skills

app = FastAPI(title="Claude Memory Manager", version="1.0.0")

app.include_router(projects.router)
app.include_router(memories.router)
app.include_router(search.router)
app.include_router(global_files.router)
app.include_router(project_config.router)
app.include_router(logs.router)
app.include_router(skills.router)

_FRONTEND = Path(__file__).parent.parent / "frontend" / "index.html"


@app.get("/api/config")
def get_config():
    return {"read_only": READ_ONLY}


@app.get("/")
def index():
    return FileResponse(_FRONTEND)
