from pydantic import BaseModel
from typing import Optional


class Project(BaseModel):
    id: str
    label: str
    memory_count: int
    total_tokens: int = 0


class ConfigFile(BaseModel):
    name: str
    path: str
    exists: bool
    file_type: str   # "markdown" | "json"
    content: str = ""
    tokens: int = 0


class MemoryMeta(BaseModel):
    filename: str
    name: str
    description: str
    type: str
    project_id: str
    is_index: bool
    tokens: int = 0


class MemoryFile(MemoryMeta):
    body: str
    file_path: str = ""


class RawUpdate(BaseModel):
    raw_content: str


class MemoryUpdate(BaseModel):
    name: str
    description: str
    type: str
    body: str


class MemoryCreate(BaseModel):
    project_id: str
    filename: str
    name: str
    description: str
    type: str
    body: str


class SearchResult(BaseModel):
    project_id: str
    project_label: str
    filename: str
    name: str
    type: str
    snippet: str


class SkillMeta(BaseModel):
    id: str               # filename stem (yaml) or directory name (bundle)
    name: str             # display name from frontmatter
    description: str
    skill_type: str       # "yaml" | "bundle"
    path: str             # host path of the actual editable file
    tokens: int = 0


class SkillFile(SkillMeta):
    content: str = ""
