from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="Pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    assets = relationship("Asset", back_populates="project")
    tasks = relationship("Task", back_populates="project")

class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String, index=True)
    type = Column(String)
    status = Column(String, default="Active")
    source = Column(String, nullable=True)
    project = relationship("Project", back_populates="assets")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String, index=True)
    # BUG 4 FIX: Added tool_name column for robust tool extraction
    tool_name = Column(String, nullable=True)
    status = Column(String, default="Pending")
    priority = Column(String, default="Medium")
    project = relationship("Project", back_populates="tasks")

class DecisionLog(Base):
    __tablename__ = "decision_logs"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    agent_name = Column(String)
    decision = Column(Text)
    reason = Column(Text)
    result_status = Column(String, default="Pending")
    output_data = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    target = Column(String)
    tool = Column(String)
    title = Column(String)
    severity = Column(String, default="Info")
    status = Column(String, default="New")
    confidence = Column(Integer, default=0)
    raw_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True, index=True)
    finding_id = Column(Integer, ForeignKey("findings.id"))
    source = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    raw_output = Column(Text)

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True, index=True)
    value = Column(String)

class AgentMessage(Base):
    __tablename__ = "agent_messages"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    sender_agent = Column(String)
    receiver_agent = Column(String)
    message_type = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)