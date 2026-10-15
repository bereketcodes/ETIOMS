import uuid
from sqlalchemy import Column, String, Float, Date, JSON, Text
from sqlalchemy.types import TypeDecorator, CHAR
from backend.app.database import Base

class GUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value

class Tender(Base):
    __tablename__ = "tenders"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
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