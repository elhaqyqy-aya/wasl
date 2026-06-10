from sqlalchemy import Column, String, Text, ForeignKey, Enum as SAEnum, DateTime, Integer, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base
import uuid, enum

class SentimentType(str, enum.Enum):
    positif = "positif"
    neutre = "neutre"
    negatif = "negatif"

class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class EngagementSurvey(Base):
    __tablename__ = "engagement_surveys"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    questions = Column(JSONB, nullable=False, default=list)
    is_anonymous = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SurveyResponse(Base):
    __tablename__ = "survey_responses"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("engagement_surveys.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    answers = Column(JSONB, nullable=False, default=dict)
    score = Column(Integer, nullable=True)
    sentiment = Column(SAEnum(SentimentType), nullable=True)
    responded_at = Column(DateTime(timezone=True), server_default=func.now())

class AnnualReview(Base):
    __tablename__ = "annual_reviews"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    review_date = Column(DateTime(timezone=True), server_default=func.now())
    rating = Column(Numeric(3, 1), nullable=True)
    workload_score = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)  # encrypted

class DisengagementSignal(Base):
    __tablename__ = "disengagement_signals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())
    risk_score = Column(Numeric(5, 2), nullable=False, default=0)
    risk_level = Column(SAEnum(RiskLevel), default=RiskLevel.low)
    signals = Column(JSONB, nullable=True, default=dict)
    action_plan = Column(JSONB, nullable=True, default=dict)
