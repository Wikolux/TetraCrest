from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    document_type = Column(String(100), nullable=False, default="general")
    source = Column(String(255), nullable=True)

    # Ingestion metadata. Fields only, per the current milestone - no ingestion
    # pipeline reads or writes these yet.
    source_type = Column(String(50), nullable=False, default="manual")
    classification = Column(String(100), nullable=True)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(150), nullable=True)
    file_size = Column(Integer, nullable=True)
    storage_path = Column(String(500), nullable=True)
    source_url = Column(String(1000), nullable=True)
    ingestion_status = Column(String(50), nullable=False, default="pending")
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="knowledge_documents")
