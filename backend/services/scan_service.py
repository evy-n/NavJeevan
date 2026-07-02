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