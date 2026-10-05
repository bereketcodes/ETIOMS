from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from backend.app.models.tender_matches import TenderMatch

from backend.app.database import get_db
from backend.app.models.organization import OrganizationProfile
from backend.app.models.tender import Tender
from backend.app.schemas.organization import OrganizationCreate, OrganizationResponse
from backend.app.services.matching_service import calculate_match_score

from backend.app.services.compliance_service import evaluate_compliance

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization profile not yet created.",
        )

    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found with given ID.",
        )

    return calculate_match_score(profile, tender)




@router.get("/compliance/{tender_id}")
def check_compliance(tender_id: UUID, db: Session = Depends(get_db)):
    """Generates an Ethiopian procurement compliance matrix and Bid/No-Bid recommendation."""
    profile = db.query(OrganizationProfile).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Setup company profile first before compliance checks.")

    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found with given ID.")

    return evaluate_compliance(profile, tender)


@router.get("/match/{tender_id}")
def match_tender(tender_id: UUID, db: Session = Depends(get_db)):
    # 1. Verify Profile exists
    profile = db.query(OrganizationProfile).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Organization profile not found.")

    # 2. Verify Tender exists
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found.")

    # 3. Check the Cache: Has this match already been evaluated?
    cached_match = db.query(TenderMatch).filter(
        TenderMatch.profile_id == str(profile.id),
        TenderMatch.tender_id == str(tender.id)
    ).first()

    if cached_match:
        # Cache Hit! Return the saved data immediately (0 API cost, fast response)
        return {
            "tender_id": cached_match.tender_id,
            "total_score": cached_match.total_score,
            "is_qualified": cached_match.is_qualified,
            "compliance_decision": cached_match.compliance_decision,
            "breakdown": cached_match.breakdown,
            "cached": True
        }

    # 4. Cache Miss: Calculate the score (runs deterministic rules + calls Gemini)
    match_result = calculate_match_score(profile, tender)

    new_match = TenderMatch(
        profile_id=str(profile.id),
        tender_id=str(tender.id),
        total_score=match_result["total_score"],
        is_qualified=match_result["is_qualified"],
        compliance_decision="BID" if match_result["is_qualified"] else "NO-BID",
        breakdown=match_result["breakdown"]
    )
    db.add(new_match)
    db.commit()

    match_result["cached"] = False
    return match_result