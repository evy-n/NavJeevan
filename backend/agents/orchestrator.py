from agents.recon_agent import ReconAgent
from agents.scanner_agent import ScannerAgent
from agents.validator_agent import ValidatorAgent
from agents.attack_agent import AttackAgent # NEW
from agents.learning_agent import LearningAgent
from agents.reporting_agent import ReportingAgent
from agents.council_agent import CouncilAgent
from models import AgentMessage, KnowledgeBase, Task
from datetime import datetime
import models

class AgentOrchestrator:
    def __init__(self):
        self.recon = ReconAgent()
        self.scanner = ScannerAgent()
        self.validator = ValidatorAgent()
        self.attack = AttackAgent() # NEW
        self.learner = LearningAgent()
        self.reporter = ReportingAgent()
        self.council = CouncilAgent()
    
    def run_full_autonomous_scan(self, db, project_id: int, target: str, project=None) -> dict:
        self._log_orchestrator(db, project_id, "Full autonomous scan started")
        
        past_kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.title.like(f"learnings:{target}%")
        ).order_by(KnowledgeBase.created_at.desc()).first()
        past_learnings = past_kb.content if past_kb else ""
        
        from ai_engine import ai_gateway
        tool_plan = ai_gateway.get_autonomous_plan_with_context(
            project.name if project else "Project", target, past_learnings
        )
        
        db.query(Task).filter(Task.project_id == project_id, Task.status == "Pending").delete()
        for tool_name in tool_plan:
            db.add(Task(project_id=project_id, name=f"Run {tool_name.upper()} Scan", tool_name=tool_name, status="Pending", priority="High"))
        db.commit()
        
        context = {"db": db, "project": project, "past_learnings": past_learnings}
        
        self._log_orchestrator(db, project_id, "Stage 1: Recon started")
        recon_result = self.recon.execute(project_id, target, context)
        context["recon_results"] = recon_result.get("results", {})
        
        self._log_orchestrator(db, project_id, "Stage 2: Vuln scan started")
        scan_result = self.scanner.execute(project_id, target, context)
        
        self._log_orchestrator(db, project_id, "Stage 3: Validation started")
        validation_result = self.validator.execute(project_id, target, context)
        
        # NEW: PoC Verification
        self._log_orchestrator(db, project_id, "Stage 4: PoC Verification started")
        attack_result = self.attack.execute(project_id, target, context)
        
        self._log_orchestrator(db, project_id, "Stage 5: Learning started")
        learning_result = self.learner.execute(project_id, target, context)
        
        self._log_orchestrator(db, project_id, "Stage 6: Report generation")
        report_result = self.reporter.execute(project_id, target, context)
        
        self._log_orchestrator(db, project_id, "Full scan completed")
        return {"status": "completed"}
    
    def run_council_review(self, db, project_id: int, finding_id: int) -> dict:
        context = {"db": db, "finding_id": finding_id}
        return self.council.execute(project_id, "", context)
    
    def _log_orchestrator(self, db, project_id: int, message: str):
        msg = AgentMessage(project_id=project_id, sender_agent="Orchestrator", receiver_agent="System", message_type="Status", content=message, timestamp=datetime.utcnow())
        db.add(msg); db.commit()

orchestrator = AgentOrchestrator()