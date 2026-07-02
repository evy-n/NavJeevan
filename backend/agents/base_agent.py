from abc import ABC, abstractmethod
from groq import Groq
import os
from database import SessionLocal
from models import AgentMessage, DecisionLog
from datetime import datetime

class BaseAgent(ABC):
    name: str = "BaseAgent"
    role: str = "Generic"
    model: str = "llama-3.3-70b-versatile"
    
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    def think(self, prompt: str, system_prompt: str = None) -> str:
        """Groq se response lo"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.1,
            max_tokens=1000
        )
        return response.choices[0].message.content
    
    def log_action(self, db, project_id: int, action: str, result: str):
        """Har agent action DB mein log karo"""
        entry = DecisionLog(
            project_id=project_id,
            agent_name=self.name,
            decision=action,
            reason=f"Agent: {self.role}",
            result_status="Completed",
            output_data=result[:500],
            timestamp=datetime.utcnow()
        )
        db.add(entry)
        db.commit()
    
    def send_message(self, db, project_id: int, to_agent: str, message: str):
        """Agent-to-agent communication log karo"""
        msg = AgentMessage(
            project_id=project_id,
            sender_agent=self.name,
            receiver_agent=to_agent,
            message_type="Task",
            content=message,
            timestamp=datetime.utcnow()
        )
        db.add(msg)
        db.commit()
    
    @abstractmethod
    def execute(self, project_id: int, target: str, context: dict) -> dict:
        pass