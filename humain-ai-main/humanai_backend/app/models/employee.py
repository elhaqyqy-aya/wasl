from sqlalchemy import Column, String, Date, Numeric, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy import DateTime, Boolean
from app.database import Base
import uuid, enum

class ContractType(str, enum.Enum):
    cdi = "cdi"
    cdd = "cdd"
    stage = "stage"
    consultant = "consultant"

class EmployeeStatus(str, enum.Enum):
    actif = "actif"
    inactif = "inactif"
    en_sortie = "en_sortie"

class Employee(Base):
    __tablename__ = "employees"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    matricule = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    position_id = Column(UUID(as_uuid=True), ForeignKey("positions.id"), nullable=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    hire_date = Column(Date, nullable=True)
    contract_type = Column(SAEnum(ContractType), default=ContractType.cdi)
    salary_band = Column(Text, nullable=True)  # encrypted
    status = Column(SAEnum(EmployeeStatus), default=EmployeeStatus.actif)
    sirh_sync_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
