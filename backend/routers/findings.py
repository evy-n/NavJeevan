from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models
from models import Finding, DecisionLog, KnowledgeBase, Setting
from database import get_db
from core.dependencies import get_current_user

router = APIRouter(prefix="/api", tags=["Findings & Logs"])

@router.get("/logs/{project_id}")
def get_decision_logs(project_id: int, db: Session = Depends(get_db)):
    return db.query(DecisionLog).filter(DecisionLog.project_id == project_id).all()

@router.get("/findings/{project_id}")
def get_findings(project_id: int, db: Session = Depends(get_db)):
    return db.query(Finding).filter(Finding.project_id == project_id).all()

@router.put("/findings/{finding_id}")
def update_finding_status(finding_id: int, status: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding: return {"status": "error", "message": "Not found"}
    finding.status = status; db.commit()
    return {"status": "success"}

@router.get("/global_logs")
def get_global_logs(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(DecisionLog).order_by(DecisionLog.id.desc()).limit(50).all()

@router.get("/knowledge_base")
def get_kb(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(KnowledgeBase).all()

@router.post("/knowledge_base")
def add_kb(data: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    entry = KnowledgeBase(title=data['title'], content=data['content'])
    db.add(entry); db.commit(); db.refresh(entry)
    return {"status": "success"}

@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return {s.key: s.value for s in db.query(Setting).all()}

@router.post("/settings")
def update_settings(data: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    for key, value in data.items():
        existing = db.query(Setting).filter(Setting.key == key).first()
        if existing: existing.value = str(value)
        else: db.add(Setting(key=key, value=str(value)))
    db.commit()
    return {"status": "success"}