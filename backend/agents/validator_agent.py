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
    
    Apply OWASP Testing Guide:
    
    Common False Positive patterns to check:
    - Scanner found "admin" in URL but it requires auth
    - "Sensitive file" but no actual data exposed
    - Port open but service not vulnerable
    - Generic error page but no stack trace
    - SSL warning but certificate is valid
    
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
        response = self.think(prompt, self.SYSTEM_PROMPT)
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {
            "verdict": "NEEDS_REVIEW",
            "owasp_category": "N/A",
            "cvss_score": 0.0,
            "confidence": 50,
            "false_positive_reason": None,
            "recommendation": "Manual review needed"
        }
    
    def execute(self, project_id: int, target: str, context: dict) -> dict:
        db = context.get("db")
        findings = db.query(Finding).filter(
            Finding.project_id == project_id,
            Finding.status == "Auto-Detected"
        ).all()
        
        validated = 0
        false_positives = 0
        
        for finding in findings:
            evidences = db.query(Evidence).filter(
                Evidence.finding_id == finding.id
            ).all()
            evidence_text = "\n".join([e.raw_output for e in evidences])
            
            result = self.validate_finding(finding, evidence_text)
            
            # Update finding with AI validation
            finding.confidence = result.get("confidence", finding.confidence)
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
        
        self.log_action(
            db, project_id,
            f"Validated {len(findings)} findings",
            f"Confirmed: {validated}, FP: {false_positives}"
        )
        self.send_message(
            db, project_id, "ReportingAgent",
            f"Validation done. {validated} confirmed, {false_positives} FP"
        )
        
        return {
            "agent": self.name,
            "total_validated": len(findings),
            "confirmed": validated,
            "false_positives": false_positives,
            "status": "completed"
        }