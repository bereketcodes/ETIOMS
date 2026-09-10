from datetime import date
from typing import List
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException

# Import the schemas we built
from backend.app.schemas.tender import TenderCreate, TenderResponse

router = APIRouter(prefix="/api/tenders", tags=["Tenders"])

# Temporary in-memory storage (acts like a fake database for testing)
fake_tender_db = [
    {
        "id": uuid4(),
        "title": "National Data Center Cloud Infrastructure",
        "procuring_entity": "Ethio Telecom",
        "sector": "Information Technology",
        "region": "Addis Ababa",
        "deadline": date(2026, 11, 20),
        "status": "Open",
        "description": "Supply of enterprise rack servers, SAN storage, and virtualization licensing.",
        "budget": 15000000.00,
        "requirements": ["Cisco CCIE Certified Engineers", "ISO 27001 Certified Vendor"],
        "contact_email": "tender@ethiotelecom.et",
        "raw_document_path": "/storage/docs/ethio_dc_2026.pdf",
        "ai_summary": "High-budget infrastructure procurement for data center hardware and migration.",
        "extracted_requirements": {"bond_percent": 2.0, "warranty_years": 3}
    }
]

@router.get("", response_model=List[TenderResponse])
def get_all_tenders():
    """Returns a list of all active tenders."""
    return fake_tender_db

@router.post("", response_model=TenderResponse, status_code=201)
def create_tender(payload: TenderCreate):
    """Creates a new tender. Pydantic validates the request body automatically."""
    new_tender = payload.model_dump()
    new_tender["id"] = uuid4()
    new_tender["ai_summary"] = None
    new_tender["extracted_requirements"] = None
    
    fake_tender_db.append(new_tender)
    return new_tender