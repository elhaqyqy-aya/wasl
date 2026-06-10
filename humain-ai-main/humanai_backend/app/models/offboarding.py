from sqlalchemy import Column, String, Text, ForeignKey, Enum as SAEnum, DateTime, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import uuid, enum

class DepartureReason(str, enum.Enum):
    demission = "demission"
    licenciement = "licenciement"
    fin_contrat = "fin_contrat"
    retraite = "retraite"

class WorkflowStatus(str, enum.Enum):
    initiated = "initiated"
    in_progress = "in_progress"
    completed = "completed"

class StepType(str, enum.Enum):
    materiel = "materiel"
    acces = "acces"
    admin = "admin"
    transfert = "transfert"
    cloture = "cloture"

class OffboardingWorkflow(Base):
    __tablename__ = "offboarding_workflows"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    departure_reason = Column(SAEnum(DepartureReason), nullable=False)
    departure_date = Column(Date, nullable=False)
    status = Column(SAEnum(WorkflowStatus), default=WorkflowStatus.initiated)
    knowledge_transfer_doc_id = Column(UUID(as_uuid=True), ForeignKey("generated_documents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class OffboardingStep(Base):
    __tablename__ = "offboarding_steps"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("offboarding_workflows.id"), nullable=False)
    step_type = Column(SAEnum(StepType), nullable=False)
    title = Column(String, nullable=False)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
