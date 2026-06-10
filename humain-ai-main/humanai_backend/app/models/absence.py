from sqlalchemy import Column, String, Date, Numeric, ForeignKey, Enum as SAEnum, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import uuid, enum

class AbsenceType(str, enum.Enum):
    conge_paye = "conge_paye"
    maladie = "maladie"
    sans_solde = "sans_solde"
    autre = "autre"

class AbsenceStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"

class Absence(Base):
    __tablename__ = "absences"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    type = Column(SAEnum(AbsenceType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    duration_days = Column(Numeric(5, 1), nullable=True)
    motif = Column(Text, nullable=True)
    status = Column(SAEnum(AbsenceStatus), default=AbsenceStatus.pending)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
