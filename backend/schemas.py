from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Asset Schema
class AssetBase(BaseModel):
    name: str
    type: str
    status: Optional[str] = "Active"
    source: Optional[str] = None

class AssetCreate(AssetBase):
    project_id: int

class AssetResponse(AssetBase):
    id: int
    project_id: int

    class Config:
        from_attributes = True

# Task Schema
class TaskBase(BaseModel):
    name: str
    status: Optional[str] = "Pending"
    priority: Optional[str] = "Medium"

class TaskCreate(TaskBase):
    project_id: int

class TaskResponse(TaskBase):
    id: int
    project_id: int

    class Config:
        from_attributes = True

# Project Schema
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = "Pending"

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: int
    created_at: datetime
    assets: list[AssetResponse] = []
    tasks: list[TaskResponse] = []

    class Config:
        from_attributes = True