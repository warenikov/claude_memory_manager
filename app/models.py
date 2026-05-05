from pydantic import BaseModel
from typing import Optional


class Project(BaseModel):
    id: str
    label: str
    memory_count: int


class MemoryMeta(BaseModel):
    filename: str
    name: str
    description: str
    type: str
    project_id: str
    is_index: bool


class MemoryFile(MemoryMeta):
    body: str


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
