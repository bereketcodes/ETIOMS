import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from backend.app.database import Base
from backend.app.models.tender import GUID

class OpportunityTracking(Base):
    __tablename__ = "opportunity_tracking"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        GUID(),
        ForeignKey("organization_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tender_id = Column(
        GUID(),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SRS Pipeline states: Discovered -> Interested -> Analyzing -> Preparing -> Submitted -> Awarded / Not Awarded
    status = Column(String(50), nullable=False, default="Discovered", index=True)
    notes = Column(Text, nullable=True)
    updated_by_user_id = Column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
