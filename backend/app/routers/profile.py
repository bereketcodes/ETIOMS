from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from backend.app.database import get_db
from backend.app.models.organization import OrganizationProfile
from backend.app.models.tender import Tender
from backend.app.schemas.organization import OrganizationCreate, OrganizationResponse
from backend.app.services.matching_service import calculate_match_score

router = APIRouter(prefix="/api/profile", tags=["Organization Profile"])

@router.get("", response_model=OrganizationResponse)
def get_profile(db: Session = Depends(get_db)):
    profile = db.query(OrganizationProfile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Organization profile not yet created.")
    return profile

@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_or_update_profile(payload: OrganizationCreate, db: Session = Depends(get_db)):
    profile = db.query(OrganizationProfile).first()
    if not profile:
        profile = OrganizationProfile(**payload.model_dump())
        db.add(profile)
    else:
        for key, val in payload.model_dump().items():
            setattr(profile, key, val)
    db.commit()
    db.refresh(profile)
    return profile

@router.get("/match/{tender_id}")
def match_tender(tender_id: UUID, db: Session = Depends(get_db)):
    """Computes hybrid compatibility score between organization and a tender."""
    profile = db.query(OrganizationProfile).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Setup company profile first before matching.")

    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found.")

    return calculate_match_score(profile, tender)