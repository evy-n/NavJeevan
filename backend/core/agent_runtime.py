import threading
import asyncio
from backend.main import parse_and_create_findings
from core.plugin_manager import plugin_manager
from models import DecisionLog, Finding, Evidence
from database import SessionLocal

class AgentRuntime:
    def __init__(self):
        self.active_tasks = {}

    def execute_task(self, project_id, target, tool_name):
        db = SessionLocal()
        try:
            log_entry = DecisionLog(
                project_id=project_id, agent_name="Agent Runtime",
                decision=f"Execute {tool_name.upper()} on {target}", reason="Background autonomous task", result_status="Running"
            )
            db.add(log_entry); db.commit(); db.refresh(log_entry)

            plugin = plugin_manager.get_plugin(tool_name)
            if not plugin:
                scan_result = {"status": "Failed", "error": "Plugin not found"}
            else:
                # Fix: Proper async event loop for background thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                scan_result = loop.run_until_complete(plugin.execute(target))
                loop.close()

            findings_count = 0
            if scan_result["status"] == "Completed" and scan_result.get("output"):
                findings_count = parse_and_create_findings(db, project_id, target, tool_name, scan_result["output"])
                log_entry.result_status = "Completed"
                log_entry.output_data = f"Execution completed. {findings_count} findings extracted."
            else:
                log_entry.result_status = scan_result["status"]
                log_entry.output_data = scan_result.get("error", "Unknown error")
            db.commit()
        finally:
            db.close()

    def run_async(self, project_id, target, tool_name):
        thread = threading.Thread(target=self.execute_task, args=(project_id, target, tool_name))
        thread.start()
        return {"status": "success", "message": f"Task assigned to Agent Runtime for {tool_name}"}

agent_runtime = AgentRuntime()