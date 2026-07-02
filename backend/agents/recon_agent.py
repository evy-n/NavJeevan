from agents.base_agent import BaseAgent
from core.plugin_manager import plugin_manager
import asyncio

class ReconAgent(BaseAgent):
    name = "ReconAgent"
    role = "Reconnaissance Specialist"
    model = "llama-3.1-8b-instant"  # fast model for planning
    
    SYSTEM_PROMPT = """You are an elite reconnaissance specialist.
    Your job: analyze a target and decide which recon tools to run.
    Available tools: subfinder, dnsx, httpx, gau, katana, waybackurls
    Always return valid JSON only."""
    
    def plan_recon(self, target: str, past_context: str = "") -> list:
        prompt = f"""
        Target: {target}
        Past scan context: {past_context or "First scan on this target"}
        
        Select 3 recon tools best suited for this target.
        Consider: is it a domain? IP? subdomain?
        
        Return ONLY JSON array: ["tool1", "tool2", "tool3"]
        """
        response = self.think(prompt, self.SYSTEM_PROMPT)
        import json, re
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            return json.loads(match.group())
        return ["subfinder", "httpx", "gau"]
    
    def execute(self, project_id: int, target: str, context: dict) -> dict:
        db = context.get("db")
        past_context = context.get("past_learnings", "")
        
        tools = self.plan_recon(target, past_context)
        self.log_action(db, project_id, f"Recon plan for {target}", str(tools))
        self.send_message(db, project_id, "ScannerAgent", 
                         f"Recon tools selected: {tools}. Target: {target}")
        
        results = {}
        for tool_name in tools:
            plugin = plugin_manager.get_plugin(tool_name)
            if plugin:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(plugin.execute(target))
                loop.close()
                results[tool_name] = result
        
        return {
            "agent": self.name,
            "tools_run": tools,
            "results": results,
            "status": "completed"
        }