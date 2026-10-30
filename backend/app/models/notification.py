import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from backend.app.database import Base
from backend.app.models.tender import GUID

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Types: "NEW_MATCH", "DEADLINE_APPROACHING", "PIPELINE_UPDATE", "SYSTEM"
    type = Column(String(50), nullable=False, default="NEW_MATCH")
    message = Column(Text, nullable=False)
    read_flag = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
