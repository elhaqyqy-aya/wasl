from sqlalchemy import Column, String, Text, ForeignKey, Enum as SAEnum, DateTime, Boolean, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base
import uuid, enum

class AlertSeverity(str, enum.Enum):
    anomalie = "anomalie"
    repetee = "repetee"
    critique = "critique"
    fuite_donnees = "fuite_donnees"

class SecurityEventType(str, enum.Enum):
    unauthorized_access = "unauthorized_access"
    prompt_injection = "prompt_injection"
    repeated_attempt = "repeated_attempt"
    data_leak_risk = "data_leak_risk"

class HrAlert(Base):
    __tablename__ = "hr_alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    alert_type = Column(String, nullable=False)
    severity = Column(SAEnum(AlertSeverity), nullable=False)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)

class AiSecurityRule(Base):
    __tablename__ = "ai_security_rules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    condition_logic = Column(JSONB, nullable=False, default=dict)
    severity = Column(SAEnum(AlertSeverity), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AiInteraction(Base):
    __tablename__ = "ai_interactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    query_text = Column(Text, nullable=True)  # encrypted
    response_summary = Column(Text, nullable=True)
    role_at_time = Column(String, nullable=False)
    data_scope_requested = Column(ARRAY(String), nullable=True)
    is_security_event = Column(Boolean, default=False)

class AiSecurityEvent(Base):
    __tablename__ = "ai_security_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id = Column(UUID(as_uuid=True), ForeignKey("ai_interactions.id"), nullable=True)
    event_type = Column(SAEnum(SecurityEventType), nullable=False)
    severity = Column(SAEnum(AlertSeverity), nullable=False)
    triggered_rule_id = Column(UUID(as_uuid=True), ForeignKey("ai_security_rules.id"), nullable=True)
    admin_notified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
