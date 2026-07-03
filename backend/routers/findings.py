from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi.responses import Response
import models
from models import Finding, DecisionLog, KnowledgeBase, Setting, Evidence
from database import get_db
from core.dependencies import get_current_user
import csv
import json

router = APIRouter(prefix="/api", tags=["Findings & Logs"])

@router.get("/logs/{project_id}")
def get_decision_logs(project_id: int, db: Session = Depends(get_db)):
    return db.query(DecisionLog).filter(DecisionLog.project_id == project_id).all()

# FEATURE 4a: Findings pagination + filter
@router.get("/findings/{project_id}")
def get_findings(
    project_id: int, 
    severity: str = None, 
    status: str = None, 
    tool: str = None, 
    limit: int = 100, 
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Finding).filter(Finding.project_id == project_id)
    if severity: query = query.filter(Finding.severity == severity)
    if status: query = query.filter(Finding.status == status)
    if tool: query = query.filter(Finding.tool == tool)
    
    total = query.count()
    findings = query.offset(offset).limit(limit).all()
    return {"total": total, "findings": findings}

# FEATURE 4b: Export findings
@router.get("/findings/export/{project_id}")
def export_findings(project_id: int, format: str = "csv", db: Session = Depends(get_db)):
    findings = db.query(Finding).filter(Finding.project_id == project_id).all()
    
    if format == "json":
        data = [{"id": f.id, "title": f.title, "severity": f.severity, "status": f.status, "target": f.target, "tool": f.tool} for f in findings]
        return Response(content=json.dumps(data, indent=4), media_type="application/json", headers={"Content-Disposition": f"attachment; filename=findings_{project_id}.json"})
    else:
        output = [["ID", "Title", "Severity", "Status", "Target", "Tool"]]
        for f in findings:
            output.append([f.id, f.title, f.severity, f.status, f.target, f.tool])
        
        import io
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerows(output)
        return Response(content=si.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=findings_{project_id}.csv"})

@router.put("/findings/{finding_id}")
def update_finding_status(finding_id: int, status: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding: return {"status": "error", "message": "Not found"}
    finding.status = status; db.commit()
    return {"status": "success"}

@router.get("/findings/quality-gate/{project_id}")
def quality_gate(project_id: int, db: Session = Depends(get_db)):
    findings = db.query(Finding).filter(Finding.project_id == project_id).all()
    if not findings: return {"findings_detected": 0, "all_have_evidence": False, "avg_confidence": 0.0, "confirmed_count": 0, "false_positive_count": 0, "gate_passed": False}
        
    total_conf = sum(f.confidence for f in findings)
    avg_confidence = total_conf / len(findings)
    confirmed_count = len([f for f in findings if f.status == "Confirmed"])
    false_positive_count = len([f for f in findings if f.status == "False Positive"])
    
    all_have_evidence = True
    for f in findings:
        evidences = db.query(Evidence).filter(Evidence.finding_id == f.id).count()
        if evidences == 0: all_have_evidence = False; break
            
    gate_passed = len(findings) >= 1 and avg_confidence >= 60 and all_have_evidence
    return {"findings_detected": len(findings), "all_have_evidence": all_have_evidence, "avg_confidence": avg_confidence, "confirmed_count": confirmed_count, "false_positive_count": false_positive_count, "gate_passed": gate_passed}

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