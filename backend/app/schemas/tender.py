from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class TenderBase(BaseModel):
    title: str = Field(..., example="Website Development Project")
    procuring_entity: str = Field(..., example="Commercial Bank of Ethiopia")
    sector: str = Field(..., example="Information Technology")
    region: str = Field(..., example="Addis Ababa")
    deadline: date = Field(..., example="2026-12-31")
    status: str = Field(default="Open", example="Open")
    description: Optional[str] = Field(None, example="Looking for a vendor to develop an enterprise portal.")
    budget: Optional[float] = Field(None, ge=0, example=50000.00)
    requirements: List[str] = Field(default_factory=list, example=["Responsive Design", "Security Hardened"])
    contact_email: Optional[str] = Field(None, example="procurement@cbe.com.et")

class TenderCreate(TenderBase):
    """Payload sent by the admin/client when creating a tender record."""
    raw_document_path: Optional[str] = Field(None, example="/uploads/tenders/tender_01.pdf")


class TenderIngestRequest(BaseModel):
    """Raw procurement notice text to parse with Gemini and persist as a tender."""
    text: str = Field(..., min_length=20, example="The Ministry of Health invites sealed bids for hospital IT systems...")

class TenderResponse(TenderBase):
    """Payload returned back to the React client."""
    id: UUID
    raw_document_path: Optional[str] = None
    ai_summary: Optional[str] = None
    extracted_requirements: Optional[Dict[str, Any]] = None

    # Allows automatic serialization directly from SQLAlchemy ORM models
    model_config = ConfigDict(from_attributes=True)