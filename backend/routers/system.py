from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import shutil
import models
from database import get_db
from core.dependencies import get_current_user
from ai_engine import ai_gateway
from core.plugin_manager import TOOL_CATEGORIES, TOOL_CONFIGS
from models import DecisionLog, AgentMessage
from datetime import datetime

router = APIRouter(prefix="/api", tags=["System"])

# FEATURE 1: Real Agent Network Mapping
REAL_AGENTS = [
  {"name":"Orchestrator","role":"Pipeline Coordinator - Controls all agents"},
  {"name":"ReconAgent","role":"Recon: subfinder, httpx, gau, katana"},
  {"name":"ScannerAgent","role":"Vuln Scanner: nuclei, nmap, dalfox, ffuf"},
  {"name":"ValidatorAgent","role":"False Positive Remover - OWASP + CVSS"},
  {"name":"LearningAgent","role":"Pattern Recognition - saves scan learnings"},
  {"name":"ReportingAgent","role":"PDF + AI Executive Summary Generator"},
  {"name":"CouncilAgent","role":"3-Perspective Reviewer: Red/Blue/Business"},
]

def get_agent_status(db):
    result = []
    for agent in REAL_AGENTS:
        last = db.query(DecisionLog).filter(
            DecisionLog.agent_name == agent["name"]
        ).order_by(DecisionLog.id.desc()).first()
        
        status = "Standby"
        last_action = "Never run"
        last_run = "—"
        
        if last:
            last_action = last.decision[:50]
            last_run = last.timestamp.strftime('%d %b %H:%M')
            if last.result_status == "Failed":
                status = "Error"
            elif last.result_status == "Completed" or last.result_status == "Running":
                status = "Standby" # Stby because it's done running
            
        if agent["name"] == "Orchestrator":
            status = "Active"
            
        result.append({
            **agent,
            "status": status,
            "last_action": last_action,
            "last_run": last_run
        })
    return result

@router.get("/system_health")
def get_system_health(db: Session = Depends(get_db)):
    db_status = "Online" if db.execute(text("SELECT 1")) else "Offline"
    groq_connected = ai_gateway.client is not None
    ai_status = "Online" if groq_connected else "Not Configured"
    
    agents = get_agent_status(db)
    active_agents = sum(1 for a in agents if a["status"] == "Active")
    
    return {
        "health_score": 100 if db_status=="Online" and ai_status=="Online" else 70,
        "database": db_status, 
        "ai_engine": ai_status, 
        "groq_connected": groq_connected,
        "tool_engine": "Ready",
        "agents": agents, 
        "active_agents": f"{active_agents}/{len(agents)}",
        "stats": {
            "projects": db.query(models.Project).count(), 
            "tasks": db.query(models.Task).count(), 
            "logs": db.query(DecisionLog).count()
        }
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
    for l in db.query(DecisionLog).filter(DecisionLog.project_id == project_id).all():
        nid = f"log_{l.id}"; nodes.append({"id": nid, "label": l.decision[:15], "group": "log"}); edges.append({"from": f"project_{project.id}", "to": nid})
    return {"nodes": nodes, "edges": edges}