from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import shutil
import models
from database import get_db
from core.dependencies import get_current_user
from ai_engine import ai_gateway
from core.plugin_manager import TOOL_CATEGORIES, TOOL_CONFIGS

router = APIRouter(prefix="/api", tags=["System"])

@router.get("/system_health")
def get_system_health(db: Session = Depends(get_db)):
    db_status = "Online" if db.execute(text("SELECT 1")) else "Offline"
    ai_status = "Online" if ai_gateway.client else "Not Configured"
    agents = [
        {"name": "Manager Agent", "role": "Coordination", "status": "Active"},
        {"name": "Planner Agent", "role": "Workflow Planning", "status": "Active" if ai_status == "Online" else "Offline"},
        {"name": "Recon Agent", "role": "Information Gathering", "status": "Standby"},
        {"name": "Scanner Agent", "role": "Vulnerability Testing", "status": "Standby"},
        {"name": "Validator Agent", "role": "False Positive Check", "status": "Standby"},
        {"name": "Evidence Agent", "role": "Data Collection", "status": "Standby"},
        {"name": "Memory Agent", "role": "Database Management", "status": "Active" if db_status == "Online" else "Error"},
        {"name": "Reporting Agent", "role": "Documentation", "status": "Standby"}
    ]
    active_agents = sum(1 for a in agents if a["status"] != "Offline" and a["status"] != "Error")
    from models import DecisionLog
    return {
        "health_score": 100 if db_status=="Online" and ai_status=="Online" else 70,
        "database": db_status, "ai_engine": ai_status, "tool_engine": "Ready",
        "agents": agents, "active_agents": f"{active_agents}/8",
        "stats": {"projects": db.query(models.Project).count(), "tasks": db.query(models.Task).count(), "logs": db.query(DecisionLog).count()}
    }

@router.get("/tools/status")
def get_tools_status():
    status_list = []
    for tool_name in TOOL_CONFIGS.keys():
        is_installed = shutil.which(tool_name) is not None
        status_list.append({"name": tool_name, "status": "Ready" if is_installed else "Missing"})
    return status_list

@router.get("/tools/categories")
def get_tool_categories(user: dict = Depends(get_current_user)):
    return TOOL_CATEGORIES

@router.get("/intelligence-map/{project_id}")
def get_intelligence_map(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    nodes = [{"id": f"project_{project.id}", "label": project.name, "group": "project"}]
    edges = []
    for a in db.query(models.Asset).filter(models.Asset.project_id == project_id).all():
        nid = f"asset_{a.id}"; nodes.append({"id": nid, "label": a.name, "group": "asset"}); edges.append({"from": f"project_{project.id}", "to": nid})
    for t in db.query(models.Task).filter(models.Task.project_id == project_id).all():
        nid = f"task_{t.id}"; nodes.append({"id": nid, "label": t.name, "group": "task"}); edges.append({"from": f"project_{project.id}", "to": nid})
    from models import DecisionLog
    for l in db.query(DecisionLog).filter(DecisionLog.project_id == project_id).all():
        nid = f"log_{l.id}"; nodes.append({"id": nid, "label": l.decision[:15], "group": "log"}); edges.append({"from": f"project_{project.id}", "to": nid})
    return {"nodes": nodes, "edges": edges}