from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
import csv
import models, schemas
from database import get_db
from core.dependencies import get_current_user

router = APIRouter(prefix="/api", tags=["Projects & Tasks"])

@router.post("/projects/", response_model=schemas.ProjectResponse)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_project = models.Project(name=project.name, description=project.description, status=project.status)
    db.add(db_project); db.commit(); db.refresh(db_project)
    return db_project

@router.get("/projects/", response_model=List[schemas.ProjectResponse])
def get_projects(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(models.Project).all()

@router.post("/assets/", response_model=schemas.AssetResponse)
def create_asset(asset: schemas.AssetCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_asset = models.Asset(**asset.dict())
    db.add(db_asset); db.commit(); db.refresh(db_asset)
    return db_asset

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

@router.post("/import/config/{project_id}")
async def import_config_file(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    content = await file.read()
    file_str = content.decode("utf-8")
    lines = file_str.splitlines()
    count = 0
    for line in lines:
        target = line.strip().replace('"', '').replace(',', '')
        if target and not target.startswith("#"):
            db_asset = models.Asset(project_id=project_id, name=target, type="Config_Target", status="Active")
            db.add(db_asset)
            count += 1
    db.commit()
    return {"status": "success", "message": f"Extracted {count} targets from Config File"}

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

@router.post("/tasks/execute/{task_id}")
def execute_task_from_checklist(task_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: raise HTTPException(status_code=404, detail="Task not found")
    tool_name = task.name.replace("Run ", "").replace(" Scan", "").lower()
    asset = db.query(models.Asset).filter(models.Asset.project_id == task.project_id).first()
    if not asset: raise HTTPException(status_code=400, detail="No target asset found in project to scan.")
    target = asset.name
    task.status = "Running"; db.commit()
    # Note: For simplicity, not backgrounding this specific call in this refactor,
    # but it runs the plugin directly.
    from core.plugin_manager import plugin_manager
    import asyncio
    plugin = plugin_manager.get_plugin(tool_name)
    if plugin:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        scan_result = loop.run_until_complete(plugin.execute(target))
        loop.close()
        if scan_result["status"] == "Completed" and scan_result.get("output"):
            from services.scan_service import parse_and_create_findings
            parse_and_create_findings(db, task.project_id, target, tool_name, scan_result["output"])
            task.status = "Completed"
        else:
            task.status = "Failed"
    else:
        task.status = "Failed"
    db.commit()
    return {"status": "success", "message": f"Executed {tool_name}"}