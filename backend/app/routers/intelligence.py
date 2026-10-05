from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.tender import Tender
from backend.app.models.organization import OrganizationProfile
from backend.app.services.matching_service import calculate_match_score
from backend.app.services.compliance_service import evaluate_compliance
from backend.app.services.proposal_service import generate_bid_proposal

router = APIRouter(prefix="/api/intelligence", tags=["Executive Tender Intelligence"])

@router.get("/dossier/{tender_id}")
def generate_full_tender_dossier(
    tender_id: UUID,
    include_proposal: bool = False,
    db: Session = Depends(get_db)
):
    """
    Executes the complete ETIOMS AI pipeline:
    1. Fetches active Organization Profile & Target Tender
    2. Calculates Deterministic (70%) + AI Semantic (30%) Match Score
    3. Runs Ethiopian FPPA Preliminary Compliance Audit & Risk Detection
    4. (Optional) Auto-generates Technical Proposal Submission Pack
    """
    profile = db.query(OrganizationProfile).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure an Organization Profile before generating intelligence dossiers."
        )

    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found with the specified UUID."
        )

    # 1. Match Scoring Engine
    match_result = calculate_match_score(profile, tender)

    # 2. Compliance & Risk Audit
    compliance_result = evaluate_compliance(profile, tender)

    # 3. Optional Proposal Generation
    proposal_result = None
    if include_proposal:
        proposal_result = generate_bid_proposal(profile, tender)

    return {
        "tender_id": str(tender.id),
        "tender_title": tender.title,
        "procuring_entity": tender.procuring_entity,
        "deadline": tender.deadline.isoformat() if tender.deadline else None,
        "match_analysis": match_result,
        "compliance_audit": compliance_result,
        "proposal_pack": proposal_result
    }