import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String

from backend.app.database import Base
from backend.app.models.tender import GUID


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String(254), nullable=False, unique=True, index=True)
    user_name = Column(String(120), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    organization_id = Column(
        GUID(),
        ForeignKey("organization_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True)
