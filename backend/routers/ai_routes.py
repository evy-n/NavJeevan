from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import os, shutil, json, re
import models
from database import get_db, SessionLocal
from core.dependencies import get_current_user, validate_target
from ai_engine import ai_gateway
from models import Finding, Evidence, DecisionLog, AgentMessage, KnowledgeBase, Task, Asset

router = APIRouter(prefix="/api", tags=["AI & Browser"])

@router.get("/ai/plan/{project_id}")
def generate_ai_plan(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    
    asset = db.query(Asset).filter(Asset.project_id == project_id).first()
    target_for_plan = asset.name if asset else project.name
    
    tool_plan = ai_gateway.get_autonomous_plan(project.name, target_for_plan)
    
    db.query(Task).filter(Task.project_id == project_id, Task.status == "Pending").delete()
    for tool_name in tool_plan:
        db.add(Task(project_id=project_id, name=f"Run {tool_name.upper()} Scan", tool_name=tool_name, status="Pending", priority="High"))
    db.commit()
    
    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    asset_list = [{"name": a.name, "type": a.type} for a in assets]
    text_plan = ai_gateway.generate_workflow_plan(project.name, project.description, asset_list)
    return {"status": "success", "ai_plan": text_plan, "tools_planned": tool_plan}

@router.post("/ai/smart-plan/{project_id}")
def generate_smart_plan(project_id: int, data: dict, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    
    context = data.get("context", "")
    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    target_list = [a.name for a in assets]
    
    if not ai_gateway.client:
        raise HTTPException(status_code=500, detail="AI Not Configured")
        
    prompt = f"""
    You are an elite penetration tester and bug bounty hunter.
    
    Target URLs: {target_list}
    Mission Context: {context}
    
    Create a detailed attack plan:
    1. Tool selection with REASON (why this tool for this target)
    2. Execution ORDER (what to run first and why)
    3. What vulnerabilities to EXPECT based on the context
    4. Estimated time per phase
    
    Then return tools JSON: ["tool1", "tool2", "tool3"]
    
    Format:
    ## Phase 1: Reconnaissance
    Tools: subfinder, httpx
    Why: [reason based on context]
    Expected findings: [what might we find]
    
    ## Phase 2: Scanning
    ...
    
    TOOLS_JSON: ["subfinder", "httpx", "nuclei"]
    """
    
    response = ai_gateway.client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=ai_gateway.model_smart
    )
    plan_text = response.choices[0].message.content
    
    match = re.search(r'TOOLS_JSON:\s*(\[.*?\])', plan_text)
    tools = json.loads(match.group(1)) if match else ["subfinder","httpx","nuclei"]
    
    db.query(Task).filter(Task.project_id == project_id, Task.status == "Pending").delete()
    for t in tools:
        db.add(Task(project_id=project_id, name=f"Run {t.upper()}", tool_name=t, status="Pending", priority="High"))
    db.commit()
    
    return {"plan": plan_text, "tools": tools}

@router.get("/ai/correlate/{project_id}")
def correlate_project_findings(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    findings = db.query(Finding).filter(Finding.project_id == project_id).all()
    if not findings: raise HTTPException(status_code=400, detail="No findings to correlate.")
    findings_list = [{"tool": f.tool, "severity": f.severity, "title": f.title, "target": f.target} for f in findings]
    correlation_report = ai_gateway.correlate_findings(project.name, findings_list)
    return {"status": "success", "correlation_report": correlation_report}

# ==========================================
# FEATURE 1: Validate All Findings
# ==========================================
@router.post("/ai/validate-all/{project_id}")
def validate_all_findings(project_id: int, db: Session = Depends(get_db)):
    findings = db.query(Finding).filter(
        Finding.project_id == project_id,
        Finding.status == "Auto-Detected"
    ).all()
    
    if not findings:
        return {"validated": 0, "confirmed": 0, "fp_removed": 0}
        
    from agents.validator_agent import ValidatorAgent
    validator = ValidatorAgent()
    
    confirmed = 0
    fp_removed = 0
    
    for finding in findings:
        evidences = db.query(Evidence).filter(Evidence.finding_id == finding.id).all()
        evidence_text = "\n".join([e.raw_output for e in evidences])
        
        result = validator.validate_finding(finding, evidence_text)
        
        finding.confidence = result.get("confidence", finding.confidence)
        if hasattr(finding, 'cvss_score'):
            finding.cvss_score = result.get("cvss_score", 0.0)
        if hasattr(finding, 'owasp_category'):
            finding.owasp_category = result.get("owasp_category", "N/A")
            
        if result["verdict"] == "FALSE_POSITIVE":
            finding.status = "False Positive"
            fp_removed += 1
        elif result["verdict"] == "TRUE_POSITIVE":
            finding.status = "Confirmed"
            confirmed += 1
        else:
            finding.status = "Needs Review"
            
        db.commit()
        
    return {
        "validated": len(findings),
        "confirmed": confirmed,
        "fp_removed": fp_removed
    }

@router.get("/audit/owasp/{project_id}")
def owasp_audit(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    findings = db.query(Finding).filter(Finding.project_id == project_id).all()
    if not findings: raise HTTPException(status_code=400, detail="No findings to audit.")
    
    if not ai_gateway.client: raise HTTPException(status_code=500, detail="AI Not Configured")

    owasp_map = { "A01": "Broken Access Control", "A02": "Cryptographic Failures", "A03": "Injection", "A04": "Insecure Design", "A05": "Security Misconfiguration", "A06": "Vulnerable/Outdated Components", "A07": "Authentication Failures", "A08": "Software Integrity Failures", "A09": "Security Logging Failures", "A10": "SSRF", "N/A": "Not Applicable" }
    owasp_breakdown = {}; total_points = 0; points_map = {"Critical": 10, "High": 7, "Medium": 4, "Low": 1, "Info": 0}
    
    for f in findings:
        prompt = f"You are an OWASP Top 10 specialist.\nFinding: {f.title}\nTool: {f.tool}\nSeverity: {f.severity}\nClassify into ONE OWASP Top 10 (2021) category code (A01-A10 or N/A).\nReturn ONLY the code (e.g., A03)."
        response = ai_gateway.client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant")
        cat_code = response.choices[0].message.content.strip()
        if cat_code not in owasp_map: cat_code = "N/A"
        cat_name = f"{cat_code}-{owasp_map[cat_code]}"
        if cat_name not in owasp_breakdown: owasp_breakdown[cat_name] = {"count": 0, "findings": []}
        owasp_breakdown[cat_name]["count"] += 1
        owasp_breakdown[cat_name]["findings"].append(f.id)
        total_points += points_map.get(f.severity, 0)
        if hasattr(f, 'owasp_category'): f.owasp_category = cat_code; db.commit()

    risk_score = int((total_points / (len(findings) * 10)) * 100) if findings else 0
    top_category = max(owasp_breakdown, key=lambda k: owasp_breakdown[k]['count']) if owasp_breakdown else "N/A"
    narrative_prompt = f"Security audit results for {project.name}:\nTotal findings: {len(findings)}\nOWASP breakdown: {json.dumps(owasp_breakdown)}\nRisk score: {risk_score}/100\nWrite 2-paragraph executive summary for CISO. Plain English, no jargon."
    narrative_resp = ai_gateway.client.chat.completions.create(messages=[{"role": "user", "content": narrative_prompt}], model="llama-3.3-70b-versatile")
    narrative = narrative_resp.choices[0].message.content
    return {"risk_score": risk_score, "owasp_breakdown": owasp_breakdown, "top_category": top_category, "total_findings": len(findings), "narrative": narrative}

# ==========================================
# FEATURE 4: AI Learnings project filter fix
# ==========================================
@router.get("/ai/learnings/{project_id}")
def get_ai_learnings(project_id: int, db: Session = Depends(get_db)):
    # Try to filter by project_id first, fallback to global learnings
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.title.like(f"learnings:{project_id}:%")
    ).order_by(KnowledgeBase.created_at.desc()).first()
    
    if not kb:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.title.like("learnings:%")
        ).order_by(KnowledgeBase.created_at.desc()).first()
        
    if not kb:
        return {"status": "no_learnings", "message": "Run at least one complete autonomous scan first"}
    
    try:
        return json.loads(kb.content)
    except:
        return {"raw_content": kb.content}

@router.get("/ai/validate/{finding_id}")
def ai_validate_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding: raise HTTPException(status_code=404, detail="Finding not found")
    evidences = db.query(Evidence).filter(Evidence.finding_id == finding_id).all()
    evidence_text = "\n".join([e.raw_output for e in evidences]) or "No raw evidence."
    finding_dict = {"tool": finding.tool, "title": finding.title}
    validation_result = ai_gateway.validate_finding(finding_dict, evidence_text)
    return {"validation_result": validation_result}

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