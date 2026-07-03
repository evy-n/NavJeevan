from agents.base_agent import BaseAgent
from models import Finding, Evidence, KnowledgeBase
from datetime import datetime
import json, re

class ValidatorAgent(BaseAgent):
    name = "ValidatorAgent"
    role = "Security Validator & False Positive Checker"
    model = "llama-3.3-70b-versatile"
    
    SYSTEM_PROMPT = """You are a senior application security engineer.
    Your job: validate security findings and eliminate false positives.
    Be strict — only confirm findings with clear evidence.
    Always return valid JSON only."""
    
    VALIDATION_PROMPT = """
    Analyze this security finding:
    Tool: {tool}
    Title: {title}
    Raw Evidence: {evidence}
    Target: {target}
    Severity claimed: {severity}
    Return ONLY this JSON:
    {{
        "verdict": "TRUE_POSITIVE" or "FALSE_POSITIVE" or "NEEDS_REVIEW",
        "owasp_category": "A01" to "A10" or "N/A",
        "cvss_score": 0.0 to 10.0,
        "confidence": 0 to 100,
        "false_positive_reason": "reason if FP else null",
        "recommendation": "1 line fix"
    }}
    """
    
    def validate_finding(self, finding, evidence_text: str) -> dict:
        prompt = self.VALIDATION_PROMPT.format(
            tool=finding.tool,
            title=finding.title,
            evidence=evidence_text[:800],
            target=finding.target,
            severity=finding.severity
        )
        # P2.9: Using JSON mode
        response = self.think(prompt, self.SYSTEM_PROMPT, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {"verdict": "NEEDS_REVIEW", "owasp_category": "N/A", "cvss_score": 0.0, "confidence": 50, "false_positive_reason": None, "recommendation": "Manual review needed"}
    
    def execute(self, project_id: int, target: str, context: dict) -> dict:
        db = context.get("db")
        findings = db.query(Finding).filter(
            Finding.project_id == project_id,
            Finding.status == "Auto-Detected"
        ).all()
        
        # P2.8: Historical accuracy layer
        tool_accuracy = {}
        kbs = db.query(KnowledgeBase).filter(KnowledgeBase.title.like("learnings:%")).all()
        for kb in kbs:
            try:
                data = json.loads(kb.content)
                eff_tools = data.get("effective_tools", [])
                inef_tools = data.get("ineffective_tools", [])
                for t in eff_tools:
                    tool_accuracy[t] = tool_accuracy.get(t, 0) + 10
                for t in inef_tools:
                    tool_accuracy[t] = tool_accuracy.get(t, 0) - 10
            except:
                pass
        
        validated = 0
        false_positives = 0
        
        for finding in findings:
            evidences = db.query(Evidence).filter(Evidence.finding_id == finding.id).all()
            evidence_text = "\n".join([e.raw_output for e in evidences])
            
            result = self.validate_finding(finding, evidence_text)
            
            base_confidence = result.get("confidence", finding.confidence)
            # P2.8: Apply historical weighting
            history_modifier = tool_accuracy.get(finding.tool, 0)
            final_confidence = max(0, min(100, base_confidence + history_modifier))
            
            finding.confidence = final_confidence
            if hasattr(finding, 'cvss_score'):
                finding.cvss_score = result.get("cvss_score", 0.0)
            if hasattr(finding, 'owasp_category'):
                finding.owasp_category = result.get("owasp_category", "N/A")
            
            if result["verdict"] == "FALSE_POSITIVE":
                finding.status = "False Positive"
                false_positives += 1
            elif result["verdict"] == "TRUE_POSITIVE":
                finding.status = "Confirmed"
                validated += 1
            else:
                finding.status = "Needs Review"
            
            db.commit()
        
        self.log_action(db, project_id, f"Validated {len(findings)} findings", f"Confirmed: {validated}, FP: {false_positives}")
        self.send_message(db, project_id, "ReportingAgent", f"Validation done. {validated} confirmed, {false_positives} FP")
        
        return {"agent": self.name, "total_validated": len(findings), "confirmed": validated, "false_positives": false_positives, "status": "completed"}