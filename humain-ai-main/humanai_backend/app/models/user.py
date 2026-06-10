from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import uuid, enum

class UserRole(str, enum.Enum):
    collaborateur = "collaborateur"
    manager = "manager"
    rh = "rh"
    direction = "direction"
    admin = "admin"
    qvt = "qvt"

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=True)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.collaborateur)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
