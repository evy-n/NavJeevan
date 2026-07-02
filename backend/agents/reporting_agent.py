from agents.base_agent import BaseAgent
from models import Finding, Evidence, DecisionLog, KnowledgeBase
from fpdf import FPDF
import json

class ReportingAgent(BaseAgent):
    name = "ReportingAgent"
    role = "Professional Report Generator"
    model = "mixtral-8x7b-32768"  # large context for full report
    
    SYSTEM_PROMPT = """You are a senior security consultant 
    writing professional penetration testing reports.
    Write clearly for both technical and business audiences."""
    
    def generate_executive_summary(self, project_name: str, 
                                    findings: list) -> str:
        critical = len([f for f in findings if f.severity == "Critical"])
        high = len([f for f in findings if f.severity == "High"])
        medium = len([f for f in findings if f.severity == "Medium"])
        
        findings_text = "\n".join([
            f"- {f.severity}: {f.title}" for f in findings[:10]
        ])
        
        prompt = f"""
        Project: {project_name}
        Total findings: {len(findings)}
        Critical: {critical}, High: {high}, Medium: {medium}
        
        Key findings:
        {findings_text}
        
        Write a 2-paragraph executive summary for a CISO.
        Para 1: Overall security posture and key risks
        Para 2: Immediate actions required
        
        Keep it concise, non-technical language.
        """
        return self.think(prompt, self.SYSTEM_PROMPT)
    
    def execute(self, project_id: int, target: str, context: dict) -> dict:
        db = context.get("db")
        project = context.get("project")
        
        findings = db.query(Finding).filter(
            Finding.project_id == project_id
        ).all()
        
        summary = self.generate_executive_summary(
            project.name if project else "Security Audit", 
            findings
        )
        
        self.log_action(
            db, project_id,
            "Professional report generated",
            f"{len(findings)} findings included"
        )
        
        return {
            "agent": self.name,
            "executive_summary": summary,
            "findings_count": len(findings),
            "status": "completed"
        }