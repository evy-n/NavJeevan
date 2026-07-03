from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import csv
import models, schemas
from database import get_db
from core.dependencies import get_current_user

router = APIRouter(prefix="/api", tags=["Projects & Tasks"])

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

@router.post("/projects/", response_model=schemas.ProjectResponse)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_project = models.Project(name=project.name, description=project.description, status=project.status)
    db.add(db_project); db.commit(); db.refresh(db_project)
    return db_project

@router.get("/projects/", response_model=List[schemas.ProjectResponse])
def get_projects(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(models.Project).all()

# FEATURE 1: Project Rename
@router.patch("/projects/{project_id}", response_model=schemas.ProjectResponse)
def rename_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    
    if data.name: project.name = data.name
    if data.description is not None: project.description = data.description
    db.commit(); db.refresh(project)
    return project

# FEATURE 2: Project Delete with Cascade
@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    
    # SQLAlchemy cascade="all, delete-orphan" will handle related tables automatically
    db.delete(project)
    db.commit()
    return {"status": "success", "message": "Project and all related data deleted"}

# Asset Endpoints
class AssetCreate(BaseModel):
    project_id: int
    name: str
    type: str = "domain"
    status: str = "Active"

@router.post("/assets/")
def create_asset(asset: AssetCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_asset = models.Asset(project_id=asset.project_id, name=asset.name, type=asset.type, status=asset.status)
    db.add(db_asset); db.commit(); db.refresh(db_asset)
    return db_asset

@router.get("/assets/{project_id}")
def get_assets(project_id: int, db: Session = Depends(get_db)):
    return db.query(models.Asset).filter(models.Asset.project_id == project_id).all()

@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not asset: raise HTTPException(status_code=404, detail="Asset not found")
    db.delete(asset); db.commit()
    return {"status": "success"}

@router.post("/import/csv/{project_id}")
async def import_csv(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    content = await file.read()
    lines = content.decode("utf-8").splitlines()
    reader = csv.reader(lines)
    count = 0
    for row in reader:
        if row:
            target = row[0].strip()
            if target:
                db_asset = models.Asset(project_id=project_id, name=target, type="Domain", status="Active")
                db.add(db_asset)
                count += 1
    db.commit()
    return {"status": "success", "message": f"Imported {count} targets"}

# Task Endpoints
class TaskStatusUpdate(BaseModel):
    status: str

@router.post("/tasks/", response_model=schemas.TaskResponse)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_task = models.Task(**task.dict())
    db.add(db_task); db.commit(); db.refresh(db_task)
    return db_task

@router.get("/tasks/{project_id}", response_model=List[schemas.TaskResponse])
def get_tasks(project_id: int, db: Session = Depends(get_db)):
    return db.query(models.Task).filter(models.Task.project_id == project_id).all()

@router.put("/tasks/{task_id}")
def update_task_status(task_id: int, status_update: TaskStatusUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: raise HTTPException(status_code=404, detail="Task not found")
    task.status = status_update.status; db.commit()
    return {"status": "success"}