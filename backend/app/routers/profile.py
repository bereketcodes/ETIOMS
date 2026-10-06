from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.app.database import get_db
from backend.app.models.organization import OrganizationProfile
from backend.app.models.tender import Tender
from backend.app.models.tender_matches import TenderMatch
from backend.app.services.matching_service import calculate_match_score
from backend.app.services.compliance_service import evaluate_compliance

router = APIRouter(prefix="/api/profile", tags=["Organization Profile & Intelligence"])


# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------
class OrganizationProfileSchema(BaseModel):
    company_name: str = Field(..., example="AfroTech Solutions PLC")
    sectors: List[str] = Field(default_factory=list, example=["Information Technology", "Consulting"])
    operating_regions: List[str] = Field(default_factory=list, example=["Addis Ababa", "Oromia"])
    years_experience: int = Field(default=0, ge=0, example=5)
    certifications: List[str] = Field(default_factory=list, example=["Renewed Trade License", "Tax Clearance", "VAT Certificate"])
    past_projects_summary: Optional[str] = Field(None, example="Developed enterprise e-procurement and web portals.")


# ---------------------------------------------------------
# Profile Endpoints
# ---------------------------------------------------------
@router.post("/", status_code=status.HTTP_200_OK)
def upsert_organization_profile(
    profile_data: OrganizationProfileSchema,
    db: Session = Depends(get_db)
):
    """
    Creates or updates the single-tenant enterprise profile.
    """
    profile = db.query(OrganizationProfile).first()

    if not profile:
        profile = OrganizationProfile(**profile_data.model_dump())
        db.add(profile)
    else:
        for key, value in profile_data.model_dump().items():
            setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/", status_code=status.HTTP_200_OK)
def get_organization_profile(db: Session = Depends(get_db)):
    """
    Fetches the configured enterprise profile.
    """
    profile = db.query(OrganizationProfile).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No organization profile configured yet. Create one via POST /api/profile."
        )
    return profile


# ---------------------------------------------------------
# Matching Engine with Cache-Aside Pattern
# ---------------------------------------------------------
@router.get("/match/{tender_id}", status_code=status.HTTP_200_OK)
def match_tender(
    tender_id: UUID,
    force_refresh: bool = Query(False, description="Set to true to bypass cache and recalculate via AI"),
    db: Session = Depends(get_db)
):
    """
    Calculates or retrieves the cached qualification match score for a tender.
    Implements Cache-Aside pattern: checks database first, calls AI on miss.
    """
    # 1. Verify Profile exists
    profile = db.query(OrganizationProfile).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure an Organization Profile before running tender matching."
        )

    # 2. Verify Tender exists
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found with the specified ID."
        )

    # 3. Check Cache (if not forced to refresh)
    if not force_refresh:
        cached_match = db.query(TenderMatch).filter(
            TenderMatch.profile_id == str(profile.id),
            TenderMatch.tender_id == str(tender.id)
        ).first()

        if cached_match:
            return {
                "tender_id": cached_match.tender_id,
                "total_score": cached_match.total_score,
                "is_qualified": cached_match.is_qualified,
                "compliance_decision": cached_match.compliance_decision,
                "ai_justification": cached_match.ai_justification,
                "breakdown": cached_match.breakdown,
                "cached": True
            }

    # 4. Cache Miss or Force Refresh: Run scoring engine
    match_result = calculate_match_score(profile, tender)

    # 5. Guard against Cache Poisoning:
    # Do NOT persist temporary network errors or Gemini 503 capacity spikes
    ai_justification = str(match_result.get("breakdown", {}).get("ai_justification", ""))
    has_transient_error = "503" in ai_justification or "temporarily unavailable" in ai_justification.lower()

    if not has_transient_error:
        # Check if record exists (in case force_refresh was used)
        existing_match = db.query(TenderMatch).filter(
            TenderMatch.profile_id == str(profile.id),
            TenderMatch.tender_id == str(tender.id)
        ).first()

        if existing_match:
            existing_match.total_score = match_result["total_score"]
            existing_match.is_qualified = match_result["is_qualified"]
            existing_match.compliance_decision = "BID" if match_result["is_qualified"] else "NO-BID"
            existing_match.ai_justification = ai_justification
            existing_match.breakdown = match_result["breakdown"]
        else:
            new_match = TenderMatch(
                profile_id=str(profile.id),
                tender_id=str(tender.id),
                total_score=match_result["total_score"],
                is_qualified=match_result["is_qualified"],
                compliance_decision="BID" if match_result["is_qualified"] else "NO-BID",
                ai_justification=ai_justification,
                breakdown=match_result["breakdown"]
            )
            db.add(new_match)

        db.commit()

    match_result["cached"] = False
    return match_result


# ---------------------------------------------------------
# FPPA Compliance & Risk Matrix
# ---------------------------------------------------------
@router.get("/compliance/{tender_id}", status_code=status.HTTP_200_OK)
def check_compliance(tender_id: UUID, db: Session = Depends(get_db)):
    """
    Generates an Ethiopian procurement compliance matrix and Go/No-Go decision.
    """
    profile = db.query(OrganizationProfile).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure an Organization Profile first before compliance auditing."
        )

    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found with the specified ID."
        )

    return evaluate_compliance(profile, tender)

@router.get("/matches", status_code=status.HTTP_200_OK)
def get_ranked_matches(
    min_score: float = Query(0.0, ge=0.0, le=100.0, description="Filter tenders by minimum total score"),
    db: Session = Depends(get_db)
):
    """
    Evaluates all tenders against the organization profile and returns 
    a ranked list sorted in descending order by match score.
    """
    profile = db.query(OrganizationProfile).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure an Organization Profile before running batch matching."
        )

    tenders = db.query(Tender).all()
    ranked_results = []

    for tender in tenders:
        # Check cache-aside table first
        cached_match = db.query(TenderMatch).filter(
            TenderMatch.profile_id == str(profile.id),
            TenderMatch.tender_id == str(tender.id)
        ).first()

        if cached_match:
            score_data = {
                "tender_id": cached_match.tender_id,
                "tender_title": tender.title,
                "procuring_entity": tender.procuring_entity,
                "total_score": cached_match.total_score,
                "is_qualified": cached_match.is_qualified,
                "compliance_decision": cached_match.compliance_decision,
                "ai_justification": cached_match.ai_justification,
                "breakdown": cached_match.breakdown,
                "cached": True
            }
        else:
            # Cache miss: compute and persist valid results
            match_res = calculate_match_score(profile, tender)
            ai_justification = str(match_res.get("breakdown", {}).get("ai_justification", ""))
            has_transient_error = "503" in ai_justification or "temporarily unavailable" in ai_justification.lower()

            if not has_transient_error:
                new_match = TenderMatch(
                    profile_id=str(profile.id),
                    tender_id=str(tender.id),
                    total_score=match_res["total_score"],
                    is_qualified=match_res["is_qualified"],
                    compliance_decision="BID" if match_res["is_qualified"] else "NO-BID",
                    ai_justification=ai_justification,
                    breakdown=match_res["breakdown"]
                )
                db.add(new_match)
                db.commit()

            score_data = {
                "tender_id": str(tender.id),
                "tender_title": tender.title,
                "procuring_entity": tender.procuring_entity,
                "total_score": match_res["total_score"],
                "is_qualified": match_res["is_qualified"],
                "compliance_decision": "BID" if match_res["is_qualified"] else "NO-BID",
                "ai_justification": ai_justification,
                "breakdown": match_res["breakdown"],
                "cached": False
            }

        if score_data["total_score"] >= min_score:
            ranked_results.append(score_data)

    # Sort descending by total score
    ranked_results.sort(key=lambda x: x["total_score"], reverse=True)
    return ranked_results