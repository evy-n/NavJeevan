from agents.base_agent import BaseAgent
from core.plugin_manager import plugin_manager
from services.scan_service import parse_and_create_findings
import asyncio
from datetime import datetime, timedelta
from models import Asset, DecisionLog

class ScannerAgent(BaseAgent):
    name = "ScannerAgent"
    role = "Vulnerability Scanner"
    model = "llama-3.3-70b-versatile"
    
    SYSTEM_PROMPT = """You are an expert vulnerability scanner.
    You analyze recon data and decide which vulnerability scanning tools to run.
    Always return valid JSON only."""
    
    def plan_vulnerability_scan(self, target: str, recon_data: str) -> list:
        prompt = f"""
        Target: {target}
        Recon findings: {recon_data[:500]}
        Select best vuln scan tools: nuclei, nikto, nmap-nse, sslyze, dalfox, ffuf, arjun, wpscan.
        Return ONLY JSON: ["tool1", "tool2", "tool3"]
        """
        response = self.think(prompt, self.SYSTEM_PROMPT)
        import json, re
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            return json.loads(match.group())
        return ["nuclei", "nmap-nse", "ffuf"]
    
    def execute(self, project_id: int, target: str, context: dict) -> dict:
        db = context.get("db")
        recon_results = context.get("recon_results", {})
        recon_summary = str(recon_results)[:500]
        
        # P3.10: Incremental scan logic
        assets = db.query(Asset).filter(Asset.project_id == project_id).all()
        targets_to_scan = [target] # Default to main target
        if assets:
            targets_to_scan = [a.name for a in assets]
            
        total_findings = 0
        for tgt in targets_to_scan:
            # Check if scanned recently
            recent_scan = db.query(DecisionLog).filter(
                DecisionLog.project_id == project_id,
                DecisionLog.agent_name == self.name,
                DecisionLog.decision.like(f"%{tgt}%")
            ).order_by(DecisionLog.timestamp.desc()).first()
            
            if recent_scan and (datetime.utcnow() - recent_scan.timestamp) < timedelta(hours=24):
                self.log_action(db, project_id, f"Skipping {tgt} (scanned recently)", "")
                continue
                
            tools = self.plan_vulnerability_scan(tgt, recon_summary)
            self.log_action(db, project_id, f"Vuln scan plan for {tgt}", str(tools))
            self.send_message(db, project_id, "ValidatorAgent", f"Running vuln tools on {tgt}: {tools}")
            
            for tool_name in tools:
                plugin = plugin_manager.get_plugin(tool_name)
                if plugin:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(plugin.execute(tgt))
                    loop.close()
                    if result["status"] == "Completed" and result.get("output"):
                        count = parse_and_create_findings(db, project_id, tgt, tool_name, result["output"])
                        total_findings += count
        
        self.send_message(db, project_id, "ValidatorAgent", f"Scan complete. {total_findings} findings found.")
        return {"agent": self.name, "total_findings": total_findings, "status": "completed"}