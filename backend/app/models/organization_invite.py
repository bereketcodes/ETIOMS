import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String

from backend.app.database import Base
from backend.app.models.tender import GUID


class OrganizationInvite(Base):
    __tablename__ = "organization_invites"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    code_hash = Column(String(64), nullable=False, unique=True, index=True)
    organization_id = Column(
        GUID(),
        ForeignKey("organization_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
