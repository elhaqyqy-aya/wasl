from sqlalchemy import Column, String, Text, ForeignKey, Enum as SAEnum, DateTime, Boolean, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base
import uuid, enum

class PlanStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    completed = "completed"

class OnboardingPlan(Base):
    __tablename__ = "onboarding_plans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    status = Column(SAEnum(PlanStatus), default=PlanStatus.draft)
    day_30_calendar = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class OnboardingStep(Base):
    __tablename__ = "onboarding_steps"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("onboarding_plans.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    is_alert_triggered = Column(Boolean, default=False)
    day_number = Column(String, nullable=True)
