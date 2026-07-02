from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from pydantic import BaseModel
import models
import schemas
from database import engine, get_db, SessionLocal
from ai_engine import ai_gateway
from core.plugin_manager import plugin_manager, TOOL_CATEGORIES, TOOL_CONFIGS
from core.agent_runtime import agent_runtime
from models import Finding, Evidence, DecisionLog, KnowledgeBase, Setting, AgentMessage
import jwt
from fpdf import FPDF
import csv
import asyncio
import os
import shutil
import re
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv() # .env file load karega

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Navjeevan API", version="3.1")
app.mount("/static", StaticFiles(directory="."), name="static")

# Fix: Hardcoded values hata kar .env se laya
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "navjeevan")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# Fix: Target input validator
def validate_target(t: str):
    if not re.match(r'^[a-zA-Z0-9.\-:/]+$', t):
        raise HTTPException(status_code=400, detail="Invalid target format")

@app.get("/dashboard", response_class=HTMLResponse)
def read_dashboard():
    with open("index.html", encoding="utf-8") as f:
        return f.read()

@app.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == ADMIN_USER and form_data.password == ADMIN_PASS:
        token = jwt.encode({"sub": ADMIN_USER}, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/projects/", response_model=schemas.ProjectResponse)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_project = models.Project(name=project.name, description=project.description, status=project.status)
    db.add(db_project); db.commit(); db.refresh(db_project)
    return db_project

@app.get("/api/projects/", response_model=List[schemas.ProjectResponse])
def get_projects(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(models.Project).all()

@app.post("/api/assets/", response_model=schemas.AssetResponse)
def create_asset(asset: schemas.AssetCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_asset = models.Asset(**asset.dict())
    db.add(db_asset); db.commit(); db.refresh(db_asset)
    return db_asset

@app.post("/api/import/csv/{project_id}")
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

@app.post("/api/import/config/{project_id}")
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

@app.post("/api/tasks/", response_model=schemas.TaskResponse)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_task = models.Task(**task.dict())
    db.add(db_task); db.commit(); db.refresh(db_task)
    return db_task

@app.get("/api/tasks/{project_id}", response_model=List[schemas.TaskResponse])
def get_tasks(project_id: int, db: Session = Depends(get_db)):
    return db.query(models.Task).filter(models.Task.project_id == project_id).all()

@app.put("/api/tasks/{task_id}")
def update_task_status(task_id: int, status_update: TaskStatusUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task: raise HTTPException(status_code=404, detail="Task not found")
    task.status = status_update.status; db.commit()
    return {"status": "success"}

@app.get("/api/ai/plan/{project_id}")
def generate_ai_plan(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    
    tool_plan = ai_gateway.get_autonomous_plan(project.name, "target.com")
    db.query(models.Task).filter(models.Task.project_id == project_id, models.Task.status == "Pending").delete()
    
    for tool_name in tool_plan:
        new_task = models.Task(project_id=project_id, name=f"Run {tool_name.upper()} Scan", status="Pending", priority="High")
        db.add(new_task)
    db.commit()
    
    assets = db.query(models.Asset).filter(models.Asset.project_id == project_id).all()
    asset_list = [{"name": a.name, "type": a.type} for a in assets]
    text_plan = ai_gateway.generate_workflow_plan(project.name, project.description, asset_list)
    return {"status": "success", "ai_plan": text_plan, "tools_planned": tool_plan}

@app.get("/api/ai/correlate/{project_id}")
def correlate_project_findings(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    findings = db.query(Finding).filter(Finding.project_id == project_id).all()
    if not findings: raise HTTPException(status_code=400, detail="No findings to correlate.")
    findings_list = [{"tool": f.tool, "severity": f.severity, "title": f.title, "target": f.target} for f in findings]
    correlation_report = ai_gateway.correlate_findings(project.name, findings_list)
    return {"status": "success", "correlation_report": correlation_report}

# Feature: Improved PDF Report
@app.get("/api/reports/pdf/{project_id}")
def generate_pdf_report(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    findings = db.query(Finding).filter(Finding.project_id == project_id).all()
    
    # Severity Summary Count
    sev_count = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    for f in findings:
        if f.severity in sev_count: sev_count[f.severity] += 1
            
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=15, style='B')
    pdf.cell(200, 10, txt="Navjeevan Security Report", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Project: {project.name}  |  Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 10, txt="Severity Summary:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Critical: {sev_count['Critical']} | High: {sev_count['High']} | Medium: {sev_count['Medium']} | Low: {sev_count['Low']} | Info: {sev_count['Info']}", ln=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 10, txt="Detailed Findings:", ln=True)
    pdf.set_font("Arial", size=10)
    
    if not findings:
        pdf.cell(200, 10, txt="- No findings extracted yet.", ln=True)
    else:
        for f in findings:
            pdf.multi_cell(0, 10, txt=f"- [{f.severity}] {f.title} (Confidence: {f.confidence}%)")
            
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    headers = {"Content-Disposition": f"attachment; filename=report_{project_id}.pdf"}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

@app.get("/api/system_health")
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
    return {
        "health_score": 100 if db_status=="Online" and ai_status=="Online" else 70,
        "database": db_status, "ai_engine": ai_status, "tool_engine": "Ready",
        "agents": agents, "active_agents": f"{active_agents}/8",
        "stats": {"projects": db.query(models.Project).count(), "tasks": db.query(models.Task).count(), "logs": db.query(DecisionLog).count()}
    }

@app.get("/api/tools/status")
def get_tools_status():
    status_list = []
    for tool_name in TOOL_CONFIGS.keys():
        is_installed = shutil.which(tool_name) is not None
        status_list.append({"name": tool_name, "status": "Ready" if is_installed else "Missing"})
    return status_list

@app.get("/api/intelligence-map/{project_id}")
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

@app.get("/api/logs/{project_id}")
def get_decision_logs(project_id: int, db: Session = Depends(get_db)):
    return db.query(DecisionLog).filter(DecisionLog.project_id == project_id).all()

@app.get("/api/findings/{project_id}")
def get_findings(project_id: int, db: Session = Depends(get_db)):
    return db.query(Finding).filter(Finding.project_id == project_id).all()

# Fix: DB commit optimized (collect objects, commit once at end)
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
    
    # Evidence add karne ke liye finding IDs chahiye, isliye ab evidence add karenge
    ev_objects = []
    for f in objects_to_add:
        ev_objects.append(Evidence(finding_id=f.id, source=tool, raw_output=f.raw_data))
    
    db.add_all(ev_objects)
    db.commit()
    findings_count = len(objects_to_add)
    return findings_count

@app.post("/api/execute/scan/{project_id}")
async def execute_scan(project_id: int, target: str, tool: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    validate_target(target) # Fix: Target validation
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
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

# Feature: Retry logic in autonomous_worker
def autonomous_worker(project_id: int, target: str):
    db = SessionLocal()
    try:
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        tool_plan = ai_gateway.get_autonomous_plan(project.name, target)
        
        db.query(models.Task).filter(models.Task.project_id == project_id, models.Task.status == "Pending").delete()
        for tool_name in tool_plan:
            db.add(models.Task(project_id=project_id, name=f"Run {tool_name.upper()} Scan", status="Pending", priority="High"))
        db.commit()
        
        pending_tasks = db.query(models.Task).filter(models.Task.project_id == project_id, models.Task.status == "Pending").all()
        
        for task in pending_tasks:
            tool_name = task.name.replace("Run ", "").replace(" Scan", "").lower()
            task.status = "Running"; db.commit()
            
            log_entry = DecisionLog(project_id=project_id, agent_name="Workflow Engine", decision=f"Execute {tool_name.upper()} on {target}", reason="Autonomous State Machine", result_status="Running")
            db.add(log_entry); db.commit(); db.refresh(log_entry)
            
            plugin = plugin_manager.get_plugin(tool_name)
            if plugin:
                # Retry Logic
                max_retries = 1
                retry_count = 0
                while retry_count <= max_retries:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    scan_result = loop.run_until_complete(plugin.execute(target))
                    loop.close()
                    
                    if scan_result["status"] == "Failed" and retry_count < max_retries:
                        retry_count += 1
                        db.add(DecisionLog(project_id=project_id, agent_name="Workflow Engine", decision=f"Retry {tool_name.upper()} on {target}", reason="Previous attempt failed", result_status="Running"))
                        db.commit()
                        time.sleep(3)
                        continue
                    break
                
                if scan_result["status"] == "Completed" and scan_result.get("output"):
                    parse_and_create_findings(db, project_id, target, tool_name, scan_result["output"])
                    task.status = "Completed"; log_entry.result_status = "Completed"
                else:
                    task.status = "Failed"; log_entry.result_status = scan_result["status"]
            else:
                task.status = "Failed"; log_entry.result_status = "Failed"
            db.commit()
    except Exception as e:
        print(f"Workflow Engine Error: {e}")
    finally:
        db.close()

@app.post("/api/execute/autonomous/{project_id}")
def execute_autonomous_scan(project_id: int, target: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    validate_target(target) # Fix: Target validation
    background_tasks.add_task(autonomous_worker, project_id, target)
    return {"status": "success", "message": "Autonomous State Machine Started."}

@app.get("/api/global_logs")
def get_global_logs(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(DecisionLog).order_by(DecisionLog.id.desc()).limit(50).all()

@app.get("/api/knowledge_base")
def get_kb(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return db.query(KnowledgeBase).all()

@app.post("/api/knowledge_base")
def add_kb(data: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    entry = KnowledgeBase(title=data['title'], content=data['content'])
    db.add(entry); db.commit(); db.refresh(entry)
    return {"status": "success"}

@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)):
    return {s.key: s.value for s in db.query(Setting).all()}

@app.post("/api/settings")
def update_settings(data: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    for key, value in data.items():
        existing = db.query(Setting).filter(Setting.key == key).first()
        if existing: existing.value = str(value)
        else: db.add(Setting(key=key, value=str(value)))
    db.commit()
    return {"status": "success"}

@app.get("/api/tools/categories")
def get_tool_categories(user: dict = Depends(get_current_user)):
    return TOOL_CATEGORIES

# Fix: Finding pehle create karo, phir uska ID use karo
@app.post("/api/browser/intelligence/{project_id}")
async def browser_intel(project_id: int, target: str, db: Session = Depends(get_db)):
    validate_target(target)
    log_entry = DecisionLog(project_id=project_id, agent_name="Browser Agent", decision=f"Headless Scan {target}", reason="JS Intelligence", result_status="Running")
    db.add(log_entry); db.commit()
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log_entry.result_status = "Failed"; log_entry.output_data = "Playwright not installed."; db.commit()
        return {"status": "failed", "error": "Playwright not installed."}
        
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(target, timeout=20000)
            title = await page.title(); content = await page.content()
            
            # Pehle Finding banao
            new_finding = Finding(project_id=project_id, target=target, tool="Playwright", title=f"Browser Intel: {title}", severity="Info", confidence=100, raw_data=content[:1000], status="Auto-Detected")
            db.add(new_finding); db.commit(); db.refresh(new_finding)
            
            # Ab us finding ID ke saath Evidence banao
            db.add(Evidence(finding_id=new_finding.id, source="Playwright", raw_output=f"Title: {title}\nLength: {len(content)}"))
            db.commit()
            
            log_entry.result_status = "Completed"; log_entry.output_data = f"Title: {title}"; db.commit()
            await browser.close()
            return {"status": "success", "title": title}
    except Exception as e:
        log_entry.result_status = "Failed"; log_entry.output_data = str(e); db.commit()
        return {"status": "failed", "error": str(e)}

@app.post("/api/plugins/upload")
async def upload_plugin(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    file_path = os.path.join("plugins", file.filename)
    with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    return {"status": "success", "message": f"Plugin {file.filename} uploaded."}

@app.get("/api/agent_messages/{project_id}")
def get_agent_messages(project_id: int, db: Session = Depends(get_db)):
    return db.query(AgentMessage).filter(AgentMessage.project_id == project_id).order_by(AgentMessage.id.desc()).limit(20).all()

@app.get("/api/ai/wordlist/{target}")
def get_ai_wordlist(target: str):
    wordlist = ai_gateway.generate_wordlist(target)
    with open("ai_wordlist.txt", "w") as f: f.write("\n".join(wordlist))
    return {"wordlist": wordlist, "saved_to": "ai_wordlist.txt"}

from plugins.base import ACTIVE_PROCESSES
@app.websocket("/ws/terminal")
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