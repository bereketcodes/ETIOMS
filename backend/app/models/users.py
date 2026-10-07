import uuid
from sqlalchemy import Column, String, Integer, JSON, Text
from backend.app.database import Base
from backend.app.models.tender import GUID

class OrganizationProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_name = Column(String, nullable=False)
    sectors = Column(JSON, default=list)  # e.g., ["Information Technology", "Cloud Services"]
    operating_regions = Column(JSON, default=list)  # e.g., ["Addis Ababa", "Oromia"]
    years_experience = Column(Integer, default=0)
    certifications = Column(JSON, default=list)  # e.g., ["ISO 27001", "Cisco CCIE"]
    past_projects_summary = Column(Text, nullable=True)