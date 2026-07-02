from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import asyncio
import models
from database import get_db, SessionLocal
from core.dependencies import get_current_user, validate_target
from core.plugin_manager import plugin_manager
from services.scan_service import parse_and_create_findings, autonomous_worker
from plugins.base import ACTIVE_PROCESSES

router = APIRouter(tags=["Scans & Execution"])

@router.post("/api/execute/scan/{project_id}")
async def execute_scan(project_id: int, target: str, tool: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    validate_target(target)
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    
    from models import DecisionLog
    log_entry = DecisionLog(project_id=project_id, agent_name="Orchestrator", decision=f"Execute {tool.upper()} on {target}", reason="Manual Scan", result_status="Running")
    db.add(log_entry); db.commit(); db.refresh(log_entry)

    plugin = plugin_manager.get_plugin(tool)
    if not plugin: scan_result = {"status": "Failed", "error": "Tool not registered"}
    else: scan_result = await plugin.execute(target)

    findings_count = 0
    if scan_result["status"] == "Completed" and scan_result.get("output"):
        findings_count = parse_and_create_findings(db, project_id, target, tool, scan_result["output"])
        log_entry.result_status = "Completed"; log_entry.output_data = f"Completed. {findings_count} findings extracted."
    else:
        log_entry.result_status = scan_result["status"]; log_entry.output_data = scan_result.get("error", "Unknown error")
    db.commit()
    return {"status": "success", "raw_output": scan_result.get("output", scan_result.get("error")), "findings_extracted": findings_count}

@router.post("/api/execute/autonomous/{project_id}")
def execute_autonomous_scan(project_id: int, target: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    validate_target(target)
    background_tasks.add_task(autonomous_worker, project_id, target)
    return {"status": "success", "message": "Multi-Agent Autonomous State Machine Started."}

@router.post("/api/council/{finding_id}")
def run_council_review(
    finding_id: int, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    from agents.orchestrator import orchestrator
    finding = db.query(models.Finding).filter(
        models.Finding.id == finding_id
    ).first()
    if not finding:
        raise HTTPException(404, "Finding not found")
    
    result = orchestrator.run_council_review(
        db=db,
        project_id=finding.project_id,
        finding_id=finding_id
    )
    return result

@router.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") == "stop":
                proc = ACTIVE_PROCESSES.get(id(websocket))
                if proc:
                    proc.kill()
                    await websocket.send_text("[!] Scan stopped by user.")
                continue

            pid = data.get("project_id"); target = data.get("target"); tool = data.get("tool")
            validate_target(target)
            await websocket.send_text(f"[~] Initializing {tool.upper()} for {target}...")
            
            plugin = plugin_manager.get_plugin(tool)
            if not plugin:
                await websocket.send_text("[!] Error: Plugin not found.")
                continue
                
            result = await plugin.execute(target, websocket)
            db = SessionLocal()
            try:
                from models import DecisionLog
                log_entry = DecisionLog(project_id=pid, agent_name="WS Orchestrator", decision=f"Execute {tool} on {target}", reason="Live Scan", result_status=result["status"])
                db.add(log_entry); db.commit(); db.refresh(log_entry)
                if result["status"] == "Completed" and result.get("output"):
                    findings_count = parse_and_create_findings(db, pid, target, tool, result["output"])
                    await websocket.send_text(f"\n[✅] Scan Completed. Extracted {findings_count} findings. Saved to DB.")
                elif result["status"] == "TimedOut":
                    await websocket.send_text(f"\n[⏱️] Scan Timed Out (exceeded 5 minutes).")
                else:
                    await websocket.send_text(f"\n[❌] Scan Failed or Stopped.")
            finally:
                db.close()
    except WebSocketDisconnect:
        proc = ACTIVE_PROCESSES.get(id(websocket))
        if proc: proc.kill()