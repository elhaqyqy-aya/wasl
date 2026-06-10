from sqlalchemy import Column, String, Text, ForeignKey, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base
from pgvector.sqlalchemy import Vector
import uuid

class RagDocument(Base):
    __tablename__ = "rag_documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # policy|convention|guide|procedure|faq
    content_raw = Column(Text, nullable=True)
    minio_path = Column(String, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class RagDocumentAccess(Base):
    __tablename__ = "rag_document_access"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("rag_documents.id"), nullable=False)
    allowed_role = Column(String, nullable=False)

class RagChunk(Base):
    __tablename__ = "rag_chunks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("rag_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    token_count = Column(Integer, nullable=True)
