import asyncio
import time
from database import SessionLocal
import models
from models import Finding, Evidence, DecisionLog
from ai_engine import ai_gateway
from core.plugin_manager import plugin_manager

def parse_and_create_findings(db, project_id, target, tool, output_text):
    findings_count = 0
    objects_to_add = []
    for line in output_text.split('\n'):
        if not line.strip(): continue
        severity = "Info"; title = line.strip(); confidence = 50
        if tool in ["nuclei", "dalfox"]:
            if "[critical]" in line.lower(): severity = "Critical"; confidence = 95; title = f"BUG: {line.split('[')[0].strip()}"
            elif "[high]" in line.lower(): severity = "High"; confidence = 90; title = f"BUG: {line.split('[')[0].strip()}"
            elif "[medium]" in line.lower(): severity = "Medium"; confidence = 80; title = f"BUG: {line.split('[')[0].strip()}"
            elif "[low]" in line.lower(): severity = "Low"; confidence = 70; title = f"BUG: {line.split('[')[0].strip()}"
            else: continue
        elif tool in ["nmap", "naabu"]:
            if "open" in line.lower(): severity = "Info"; confidence = 100; title = f"Open Port: {line.strip()}"
            else: continue
        elif tool == "ffuf":
            if line.strip().startswith("http"): severity = "Medium"; confidence = 75; title = f"Hidden Dir: {line.strip()}"
            else: continue
        
        if len(title) > 5:
            finding = Finding(project_id=project_id, target=target, tool=tool, title=title[:255], severity=severity, confidence=confidence, raw_data=line, status="Auto-Detected")
            objects_to_add.append(finding)
            
    db.add_all(objects_to_add)
    db.commit()
    
    ev_objects = []
    for f in objects_to_add:
        ev_objects.append(Evidence(finding_id=f.id, source=tool, raw_output=f.raw_data))
    
    db.add_all(ev_objects)
    db.commit()
    findings_count = len(objects_to_add)
    return findings_count

def autonomous_worker(project_id: int, target: str):
    from agents.orchestrator import orchestrator
    from database import SessionLocal
    import models
    
    db = SessionLocal()
    try:
        project = db.query(models.Project).filter(
            models.Project.id == project_id
        ).first()
        
        orchestrator.run_full_autonomous_scan(
            db=db,
            project_id=project_id,
            target=target,
            project=project
        )
    except Exception as e:
        from models import DecisionLog
        from datetime import datetime
        error_log = DecisionLog(
            project_id=project_id,
            agent_name="Orchestrator",
            decision="Autonomous scan failed",
            reason=str(e),
            result_status="Failed",
            timestamp=datetime.utcnow()
        )
        db.add(error_log)
        db.commit()
    finally:
        db.close()