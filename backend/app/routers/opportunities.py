from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.opportunity import OpportunityTracking
from backend.app.models.tender import Tender
from backend.app.models.tender_matches import TenderMatch
from backend.app.models.users import User
from backend.app.security import get_current_user

router = APIRouter(
    prefix="/api/opportunities",
    tags=["Opportunity Pipeline"],
    dependencies=[Depends(get_current_user)],
)

ALLOWED_STATUSES = [
    "Discovered",
    "Interested",
    "Analyzing",
    "Preparing",
    "Submitted",
    "Awarded",
    "Not Awarded",
]


class OpportunityStatusUpdate(BaseModel):
    status: str = Field(..., description="One of: Discovered, Interested, Analyzing, Preparing, Submitted, Awarded, Not Awarded")
    notes: Optional[str] = Field(None, description="Stage progression notes or rationale")


class OpportunityItemResponse(BaseModel):
    id: str
    tender_id: str
    organization_id: str
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tender_title: str
    procuring_entity: str
    sector: str
    region: str
    deadline: Optional[str] = None
    budget: Optional[float] = None
    match_score: Optional[float] = None
    compliance_decision: Optional[str] = None


@router.get("", response_model=List[OpportunityItemResponse])
def get_pipeline(
    status_filter: Optional[str] = Query(None, description="Filter by status: Discovered, Interested, etc."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists the organization's tracked tender pipeline (FR-16)."""
    query = (
        db.query(OpportunityTracking, Tender, TenderMatch)
        .join(Tender, OpportunityTracking.tender_id == Tender.id)
        .outerjoin(
            TenderMatch,
            (TenderMatch.tender_id == OpportunityTracking.tender_id)
            & (TenderMatch.profile_id == str(current_user.organization_id)),
        )
        .filter(OpportunityTracking.organization_id == current_user.organization_id)
    )

    if status_filter:
        query = query.filter(OpportunityTracking.status == status_filter)

    results = query.order_by(OpportunityTracking.updated_at.desc()).all()

    pipeline_items = []
    for opp, tender, match in results:
        pipeline_items.append(
            OpportunityItemResponse(
                id=str(opp.id),
                tender_id=str(tender.id),
                organization_id=str(opp.organization_id),
                status=opp.status,
                notes=opp.notes,
                created_at=opp.created_at,
                updated_at=opp.updated_at,
                tender_title=tender.title,
                procuring_entity=tender.procuring_entity,
                sector=tender.sector,
                region=tender.region,
                deadline=tender.deadline.isoformat() if tender.deadline else None,
                budget=tender.budget,
                match_score=match.total_score if match else None,
                compliance_decision=match.compliance_decision if match else None,
            )
        )
    return pipeline_items


@router.post("/save/{tender_id}", status_code=status.HTTP_200_OK)
def save_opportunity(
    tender_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Saves/bookmarks a tender into the organization's pipeline in 'Discovered' state (FR-15)."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found.")

    existing = (
        db.query(OpportunityTracking)
        .filter(
            OpportunityTracking.organization_id == current_user.organization_id,
            OpportunityTracking.tender_id == tender_id,
        )
        .first()
    )

    if existing:
        return {
            "message": "Opportunity already saved in pipeline.",
            "opportunity_id": str(existing.id),
            "status": existing.status,
            "saved": True,
        }

    new_opp = OpportunityTracking(
        organization_id=current_user.organization_id,
        tender_id=tender_id,
        status="Discovered",
        updated_by_user_id=current_user.id,
    )
    db.add(new_opp)
    db.commit()
    db.refresh(new_opp)

    return {
        "message": "Tender successfully saved to opportunity pipeline.",
        "opportunity_id": str(new_opp.id),
        "status": new_opp.status,
        "saved": True,
    }


@router.put("/{opportunity_id}/status", status_code=status.HTTP_200_OK)
def update_opportunity_status(
    opportunity_id: UUID,
    payload: OpportunityStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates opportunity pipeline progression state and adds stage notes (FR-16)."""
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.status}'. Allowed values: {', '.join(ALLOWED_STATUSES)}",
        )

    opp = (
        db.query(OpportunityTracking)
        .filter(
            OpportunityTracking.id == opportunity_id,
            OpportunityTracking.organization_id == current_user.organization_id,
        )
        .first()
    )

    if not opp:
        raise HTTPException(status_code=404, detail="Tracked opportunity not found.")

    opp.status = payload.status
    if payload.notes is not None:
        opp.notes = payload.notes
    opp.updated_by_user_id = current_user.id
    opp.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(opp)

    return {
        "message": "Opportunity status updated successfully.",
        "opportunity_id": str(opp.id),
        "status": opp.status,
        "notes": opp.notes,
        "updated_at": opp.updated_at.isoformat(),
    }


@router.delete("/{opportunity_id}", status_code=status.HTTP_200_OK)
def delete_opportunity(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Removes an opportunity from tracking."""
    opp = (
        db.query(OpportunityTracking)
        .filter(
            OpportunityTracking.id == opportunity_id,
            OpportunityTracking.organization_id == current_user.organization_id,
        )
        .first()
    )

    if not opp:
        raise HTTPException(status_code=404, detail="Tracked opportunity not found.")

    db.delete(opp)
    db.commit()
    return {"message": "Opportunity removed from pipeline.", "deleted": True}
