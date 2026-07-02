from agents.base_agent import BaseAgent
from models import Finding, Task, DecisionLog, KnowledgeBase
import json, re
from datetime import datetime

class LearningAgent(BaseAgent):
    name = "LearningAgent"
    role = "Continuous Learning & Pattern Recognition"
    model = "llama-3.1-8b-instant"
    
    SYSTEM_PROMPT = """You are a security intelligence analyst.
    You analyze past scan results to improve future scans.
    Focus on patterns, tool effectiveness, and target behavior.
    Always return valid JSON only."""
    
    def analyze_and_learn(self, target: str, scan_data: dict) -> dict:
        prompt = f"""
        Analyze these security scan results for target: {target}
        
        Tools used: {scan_data.get("tools_used", [])}
        Confirmed findings: {scan_data.get("confirmed", 0)}
        False positives: {scan_data.get("false_positives", 0)}
        Finding titles: {scan_data.get("finding_titles", [])}
        
        Generate learnings for future scans:
        
        Return ONLY this JSON:
        {{
            "effective_tools": ["tool1", "tool2"],
            "ineffective_tools": ["tool3"],
            "patterns": ["pattern1", "pattern2"],
            "target_profile": "brief description",
            "next_scan_priority": ["tool1", "tool2", "tool3"],
            "vulnerability_focus": "specific area to focus next time"
        }}
        """
        response = self.think(prompt, self.SYSTEM_PROMPT)
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {
            "effective_tools": [],
            "ineffective_tools": [],
            "patterns": [],
            "target_profile": "Unknown",
            "next_scan_priority": ["nuclei", "httpx", "nmap"],
            "vulnerability_focus": "general"
        }
    
    def get_past_learnings(self, db, target: str) -> str:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.title.like(f"learnings:{target}%")
        ).order_by(KnowledgeBase.created_at.desc()).first()
        return kb.content if kb else ""
    
    def execute(self, project_id: int, target: str, context: dict) -> dict:
        db = context.get("db")
        
        findings = db.query(Finding).filter(
            Finding.project_id == project_id
        ).all()
        
        tasks = db.query(Task).filter(
            Task.project_id == project_id
        ).all()
        
        scan_data = {
            "tools_used": list(set([t.tool_name for t in tasks if t.tool_name])),
            "confirmed": len([f for f in findings if f.status == "Confirmed"]),
            "false_positives": len([f for f in findings if f.status == "False Positive"]),
            "finding_titles": [f.title[:50] for f in findings[:10]]
        }
        
        learnings = self.analyze_and_learn(target, scan_data)
        
        kb_entry = KnowledgeBase(
            title=f"learnings:{target}:{datetime.utcnow().date()}",
            content=json.dumps(learnings),
            created_at=datetime.utcnow()
        )
        db.add(kb_entry)
        db.commit()
        
        self.log_action(
            db, project_id,
            "Learning cycle completed",
            f"Effective tools: {learnings.get('effective_tools')}"
        )
        
        return {
            "agent": self.name,
            "learnings": learnings,
            "status": "completed"
        }