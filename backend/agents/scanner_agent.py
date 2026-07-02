from agents.base_agent import BaseAgent
from core.plugin_manager import plugin_manager
from services.scan_service import parse_and_create_findings
import asyncio

class ScannerAgent(BaseAgent):
    name = "ScannerAgent"
    role = "Vulnerability Scanner"
    model = "llama-3.3-70b-versatile"
    
    SYSTEM_PROMPT = """You are an expert vulnerability scanner.
    You analyze recon data and decide which vulnerability 
    scanning tools to run. Focus on finding real bugs.
    Always return valid JSON only."""
    
    def plan_vulnerability_scan(self, target: str, recon_data: str) -> list:
        prompt = f"""
        Target: {target}
        Recon findings: {recon_data[:500]}
        
        Based on what recon found, select best vuln scan tools:
        Available: nuclei, nikto, nmap-nse, sslyze, dalfox, 
                   ffuf, arjun, wpscan
        
        If recon shows many subdomains → nuclei is priority
        If recon shows open ports → nmap-nse, sslyze
        If web app found → dalfox, ffuf, arjun
        
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
        
        tools = self.plan_vulnerability_scan(target, recon_summary)
        self.log_action(db, project_id, f"Vuln scan plan", str(tools))
        self.send_message(db, project_id, "ValidatorAgent",
                         f"Running vuln tools: {tools}")
        
        total_findings = 0
        for tool_name in tools:
            plugin = plugin_manager.get_plugin(tool_name)
            if plugin:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(plugin.execute(target))
                loop.close()
                if result["status"] == "Completed" and result.get("output"):
                    count = parse_and_create_findings(
                        db, project_id, target, tool_name, result["output"]
                    )
                    total_findings += count
        
        self.send_message(db, project_id, "ValidatorAgent",
                         f"Scan complete. {total_findings} findings found.")
        
        return {
            "agent": self.name,
            "tools_run": tools,
            "total_findings": total_findings,
            "status": "completed"
        }