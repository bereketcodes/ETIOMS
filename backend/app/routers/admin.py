from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.organization import OrganizationProfile
from backend.app.models.opportunity import OpportunityTracking
from backend.app.models.tender import Tender
from backend.app.models.users import User
from backend.app.security import get_current_user

router = APIRouter(
    prefix="/api/admin",
    tags=["Administration"],
    dependencies=[Depends(get_current_user)],
)


def _normalized_role(value: Optional[str]) -> str:
    return (value or "").strip()


def _require_role(current_user: User, permitted_roles: set[str]) -> None:
    role = _normalized_role(current_user.role)
    if role not in permitted_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to the permitted administrator roles.",
        )


@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return organization stats for Organization Admins and system stats for System Admins."""
    role = _normalized_role(current_user.role)

    if role == "System Admin":
        org = db.query(OrganizationProfile).filter(OrganizationProfile.id == current_user.organization_id).first()
        org_name = org.company_name if org else "Default Organization"
        total_team_members = db.query(User).filter(User.organization_id == current_user.organization_id).count()
        all_users_count = db.query(User).count()
        total_tenders = db.query(Tender).count()
        open_tenders = db.query(Tender).filter(Tender.status == "Open").count()
        sector_counts = (
            db.query(Tender.sector, func.count(Tender.id))
            .group_by(Tender.sector)
            .all()
        )
        sectors_summary = {sector or "Uncategorized": count for sector, count in sector_counts}
        stage_counts = (
            db.query(OpportunityTracking.status, func.count(OpportunityTracking.id))
            .group_by(OpportunityTracking.status)
            .all()
        )
        pipeline_by_stage = {stage: count for stage, count in stage_counts}
        total_opportunities = sum(pipeline_by_stage.values())
        submitted_count = pipeline_by_stage.get("Submitted", 0)
        awarded_count = pipeline_by_stage.get("Awarded", 0)

        return {
            "scope": "system",
            "organization": {
                "name": org_name,
                "id": str(current_user.organization_id),
                "team_size": total_team_members,
                "total_system_users": all_users_count,
            },
            "tenders": {
                "total_ingested": total_tenders,
                "open_tenders": open_tenders,
                "sectors_breakdown": sectors_summary,
            },
            "pipeline": {
                "total_tracked": total_opportunities,
                "by_stage": pipeline_by_stage,
                "submitted": submitted_count,
                "awarded": awarded_count,
            },
            "system_health": {
                "api_status": "Operational",
                "database_engine": "SQLite / SQLAlchemy (ACID Compliant)",
                "ai_engine": "Google Gemini 3.6/Flash + RAG Grounding",
                "auth_security": "JWT Bearer + bcrypt hashing",
            },
        }

    _require_role(current_user, {"Organization Admin"})

    org = db.query(OrganizationProfile).filter(OrganizationProfile.id == current_user.organization_id).first()
    org_name = org.company_name if org else "Default Organization"
    total_team_members = db.query(User).filter(User.organization_id == current_user.organization_id).count()
    total_tenders = db.query(Tender).filter(Tender.organization_id == current_user.organization_id).count()
    open_tenders = (
        db.query(Tender)
        .filter(Tender.organization_id == current_user.organization_id, Tender.status == "Open")
        .count()
    )
    sector_counts = (
        db.query(Tender.sector, func.count(Tender.id))
        .filter(Tender.organization_id == current_user.organization_id)
        .group_by(Tender.sector)
        .all()
    )
    sectors_summary = {sector or "Uncategorized": count for sector, count in sector_counts}
    stage_counts = (
        db.query(OpportunityTracking.status, func.count(OpportunityTracking.id))
        .filter(OpportunityTracking.organization_id == current_user.organization_id)
        .group_by(OpportunityTracking.status)
        .all()
    )
    pipeline_by_stage = {stage: count for stage, count in stage_counts}
    total_opportunities = sum(pipeline_by_stage.values())
    submitted_count = pipeline_by_stage.get("Submitted", 0)
    awarded_count = pipeline_by_stage.get("Awarded", 0)

    return {
        "scope": "organization",
        "organization": {
            "name": org_name,
            "id": str(current_user.organization_id),
            "team_size": total_team_members,
        },
        "tenders": {
            "total_ingested": total_tenders,
            "open_tenders": open_tenders,
            "sectors_breakdown": sectors_summary,
        },
        "pipeline": {
            "total_tracked": total_opportunities,
            "by_stage": pipeline_by_stage,
            "submitted": submitted_count,
            "awarded": awarded_count,
        },
    }


@router.get("/system-stats")
def get_system_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """System-wide administrative statistics; only System Admins may access this route."""
    _require_role(current_user, {"System Admin"})
    return get_admin_stats(db=db, current_user=current_user)
