from agents.base_agent import BaseAgent
from models import Finding, Evidence
import asyncio
from typing import Optional

class AttackAgent(BaseAgent):
    name = "AttackAgent"
    role = "Exploit Verification Specialist"
    model = "llama-3.1-8b-instant"
    
    SYSTEM_PROMPT = """You are an exploit verification specialist.
    You verify if a finding is actually exploitable in a SAFE, READ-ONLY manner.
    You DO NOT perform destructive actions. You only confirm existence.
    Return JSON: {"verified": true/false, "notes": "1 line reason"}"""
    
    def execute(self, project_id: int, target: str, context: dict) -> dict:
        db = context.get("db")
        
        # Support single finding verification via context
        single_finding_id = context.get("single_finding_id")
        
        if single_finding_id:
            # Only query the specific finding if ID is provided
            findings = db.query(Finding).filter(
                Finding.id == single_finding_id,
                Finding.status == "Confirmed"
            ).all()
        else:
            # Default behavior: query all Confirmed findings for the project
            findings = db.query(Finding).filter(
                Finding.project_id == project_id,
                Finding.status == "Confirmed"
            ).all()
        
        verified_count = 0
        for finding in findings:
            is_verified = False
            notes = "Not verified"
            
            # Safe, non-destructive verification logic
            if finding.tool == "dalfox" or "XSS" in finding.title:
                from core.plugin_manager import plugin_manager
                plugin = plugin_manager.get_plugin("dalfox")
                if plugin:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(plugin.execute(finding.target))
                    loop.close()
                    
                    # Heuristic check for Dalfox output
                    # NOTE: This is a heuristic approach. Dalfox prints output only when it finds something.
                    # If Dalfox supports '--format json' in the future, use that for structured parsing.
                    if result.get("status") == "Completed" and result.get("output", "").strip():
                        is_verified = True
                        notes = f"Dalfox re-scan output: {result.get('output', '')[:100]}"
                        
            elif finding.tool == "ffuf" or "Hidden" in finding.title:
                # Just check HTTP status code via httpx
                from core.plugin_manager import plugin_manager
                plugin = plugin_manager.get_plugin("httpx")
                if plugin:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(plugin.execute(finding.target))
                    loop.close()
                    
                    # FIX 2: Precise check for httpx status code format [200]
                    if "[200]" in result.get("output", ""):
                        is_verified = True
                        notes = "Endpoint accessible (200 OK)"
                        
            elif finding.tool in ["nmap", "naabu"]:
                # Re-run banner grab
                from core.plugin_manager import plugin_manager
                plugin = plugin_manager.get_plugin("nmap")
                if plugin:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(plugin.execute(finding.target))
                    loop.close()
                    if "open" in result.get("output", "").lower():
                        is_verified = True
                        notes = "Port still open and service confirmed"
            
            finding.poc_verified = is_verified
            finding.poc_verification_notes = notes
            if is_verified: verified_count += 1
            db.commit()
            
        self.log_action(db, project_id, f"PoC verified {verified_count}/{len(findings)} findings", "")
        return {"agent": self.name, "verified": verified_count, "status": "completed"}