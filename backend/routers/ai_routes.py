from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import os, shutil
import models
from database import get_db, SessionLocal
from core.dependencies import get_current_user, validate_target
from ai_engine import ai_gateway
from models import Finding, Evidence, DecisionLog, AgentMessage

router = APIRouter(prefix="/api", tags=["AI & Browser"])

@router.get("/ai/plan/{project_id}")
def generate_ai_plan(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    
    tool_plan = ai_gateway.get_autonomous_plan(project.name, "target.com")
    db.query(models.Task).filter(models.Task.project_id == project_id, models.Task.status == "Pending").delete()
    
    for tool_name in tool_plan:
        db.add(models.Task(project_id=project_id, name=f"Run {tool_name.upper()} Scan", status="Pending", priority="High"))
    db.commit()
    
    assets = db.query(models.Asset).filter(models.Asset.project_id == project_id).all()
    asset_list = [{"name": a.name, "type": a.type} for a in assets]
    text_plan = ai_gateway.generate_workflow_plan(project.name, project.description, asset_list)
    return {"status": "success", "ai_plan": text_plan, "tools_planned": tool_plan}

@router.get("/ai/correlate/{project_id}")
def correlate_project_findings(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    findings = db.query(Finding).filter(Finding.project_id == project_id).all()
    if not findings: raise HTTPException(status_code=400, detail="No findings to correlate.")
    findings_list = [{"tool": f.tool, "severity": f.severity, "title": f.title, "target": f.target} for f in findings]
    correlation_report = ai_gateway.correlate_findings(project.name, findings_list)
    return {"status": "success", "correlation_report": correlation_report}

@router.get("/ai/validate/{finding_id}")
def ai_validate_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding: raise HTTPException(status_code=404, detail="Finding not found")
    evidences = db.query(Evidence).filter(Evidence.finding_id == finding_id).all()
    evidence_text = "\n".join([e.raw_output for e in evidences]) or "No raw evidence."
    if not ai_gateway.client: return {"validation_result": "AI Not Configured."}
    
    prompt = f"Act as a Senior Application Security Expert. Tool: {finding.tool} Finding Title: {finding.title} Raw Evidence: {evidence_text} Analyze this evidence. Is this a True Positive or False Positive? Reply strictly in format: Verdict: [True/False] Reason: [1-2 lines]"
    try:
        chat_completion = ai_gateway.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192"
        )
        return {"validation_result": chat_completion.choices[0].message.content}
    except Exception as e: return {"validation_result": f"AI Error: {str(e)}"}

@router.get("/ai/wordlist/{target}")
def get_ai_wordlist(target: str):
    wordlist = ai_gateway.generate_wordlist(target)
    with open("ai_wordlist.txt", "w") as f: f.write("\n".join(wordlist))
    return {"wordlist": wordlist, "saved_to": "ai_wordlist.txt"}

@router.post("/browser/intelligence/{project_id}")
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
            
            new_finding = Finding(project_id=project_id, target=target, tool="Playwright", title=f"Browser Intel: {title}", severity="Info", confidence=100, raw_data=content[:1000], status="Auto-Detected")
            db.add(new_finding); db.commit(); db.refresh(new_finding)
            db.add(Evidence(finding_id=new_finding.id, source="Playwright", raw_output=f"Title: {title}\nLength: {len(content)}"))
            db.commit()
            
            log_entry.result_status = "Completed"; log_entry.output_data = f"Title: {title}"; db.commit()
            await browser.close()
            return {"status": "success", "title": title}
    except Exception as e:
        log_entry.result_status = "Failed"; log_entry.output_data = str(e); db.commit()
        return {"status": "failed", "error": str(e)}

@router.post("/plugins/upload")
async def upload_plugin(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    file_path = os.path.join("plugins", file.filename)
    with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    return {"status": "success", "message": f"Plugin {file.filename} uploaded."}

@router.get("/agent_messages/{project_id}")
def get_agent_messages(project_id: int, db: Session = Depends(get_db)):
    return db.query(AgentMessage).filter(AgentMessage.project_id == project_id).order_by(AgentMessage.id.desc()).limit(20).all()