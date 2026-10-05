import uuid
from sqlalchemy import Column, String, Float, Boolean, Text, ForeignKey, JSON
from backend.app.database import Base

class TenderMatch(Base):
    __tablename__ = "tender_matches"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String, ForeignKey("organization_profiles.id", ondelete="CASCADE"), nullable=False)
    tender_id = Column(String, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    total_score = Column(Float, nullable=False)
    is_qualified = Column(Boolean, default=False)
    compliance_decision = Column(String, default="REVIEW")
    ai_justification = Column(Text, nullable=True)
    breakdown = Column(JSON, nullable=True)