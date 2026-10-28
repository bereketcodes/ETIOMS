import uuid
from sqlalchemy import Column, Date, Float, ForeignKey, JSON, String, Text
from backend.app.database import Base


class GUID(type):
    pass


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False, index=True)
    procuring_entity = Column(String, nullable=False, index=True)
    sector = Column(String, nullable=False, index=True)
    region = Column(String, nullable=False)
    deadline = Column(Date, nullable=False)
    status = Column(String, default="Open")
    description = Column(Text, nullable=True)
    budget = Column(Float, nullable=True)
    requirements = Column(JSON, default=list)
    contact_email = Column(String, nullable=True)
    raw_document_path = Column(String, nullable=True)
    ai_summary = Column(Text, nullable=True)
    extracted_requirements = Column(JSON, nullable=True)
    embedding = Column(JSON, nullable=True)
    organization_id = Column(String(36), ForeignKey("organization_profiles.id"), nullable=True)
