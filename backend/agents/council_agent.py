from agents.base_agent import BaseAgent
from models import Finding, Evidence
import asyncio
from groq import Groq
import os, json, re

class CouncilAgent(BaseAgent):
    name = "CouncilAgent"
    role = "Multi-Perspective Finding Reviewer"
    
    RED_TEAM_SYSTEM = """You are an elite offensive security researcher 
    and ethical hacker. Analyze from pure attacker perspective. 
    Be direct and technical. Max 4 lines."""
    
    BLUE_TEAM_SYSTEM = """You are a senior defensive security engineer.
    Analyze exploitability in real conditions with mitigations considered.
    Be practical. Max 4 lines."""
    
    BUSINESS_SYSTEM = """You are a CISO advising the board.
    Analyze business and regulatory impact only.
    Non-technical language. Max 4 lines."""
    
    def _call_groq(self, system: str, prompt: str, model: str) -> str:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=300
        )
        return response.choices[0].message.content
    
    def review_finding(self, finding, evidence_text: str) -> dict:
        finding_info = f"""
        Tool: {finding.tool}
        Finding: {finding.title}
        Severity: {finding.severity}
        Evidence: {evidence_text[:400]}
        Target: {finding.target}
        """
        
        # Run 3 perspectives (sequential for simplicity, 
        # can be made parallel with threading)
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            red_future = executor.submit(
                self._call_groq,
                self.RED_TEAM_SYSTEM,
                f"From attacker perspective:\n{finding_info}",
                "llama-3.1-8b-instant"
            )
            blue_future = executor.submit(
                self._call_groq,
                self.BLUE_TEAM_SYSTEM,
                f"From defender perspective:\n{finding_info}",
                "llama-3.1-8b-instant"
            )
            biz_future = executor.submit(
                self._call_groq,
                self.BUSINESS_SYSTEM,
                f"From business perspective:\n{finding_info}",
                "llama-3.1-8b-instant"
            )
            
            red_view = red_future.result()
            blue_view = blue_future.result()
            biz_view = biz_future.result()
        
        # Determine council verdict
        red_exploitable = any(word in red_view.lower() 
            for word in ["exploit", "attack", "gain", "critical", "can be"])
        blue_exploitable = any(word in blue_view.lower() 
            for word in ["vulnerable", "risk", "patch", "fix immediately"])
        
        if red_exploitable and blue_exploitable:
            verdict = "EXPLOIT"
        elif red_exploitable or blue_exploitable:
            verdict = "PATCH_SOON"
        elif any(word in biz_view.lower() 
                 for word in ["compliance", "gdpr", "regulatory"]):
            verdict = "MONITOR"
        else:
            verdict = "CLOSE"
        
        return {
            "red_team": red_view,
            "blue_team": blue_view,
            "business": biz_view,
            "council_verdict": verdict
        }
    
    def execute(self, project_id: int, target: str, context: dict) -> dict:
        db = context.get("db")
        finding_id = context.get("finding_id")
        
        finding = db.query(Finding).filter(
            Finding.id == finding_id
        ).first()
        
        if not finding:
            return {"error": "Finding not found"}
        
        evidences = db.query(Evidence).filter(
            Evidence.finding_id == finding_id
        ).all()
        evidence_text = "\n".join([e.raw_output for e in evidences])
        
        result = self.review_finding(finding, evidence_text)
        
        # Save verdict to finding
        if hasattr(finding, 'council_verdict'):
            finding.council_verdict = result["council_verdict"]
            db.commit()
        
        self.log_action(
            db, project_id,
            f"Council review: {finding.title[:30]}",
            f"Verdict: {result['council_verdict']}"
        )
        
        return {
            "agent": self.name,
            "finding_id": finding_id,
            **result,
            "status": "completed"
        }