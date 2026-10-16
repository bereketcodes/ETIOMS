from datetime import date, datetime, timedelta, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.notification import Notification
from backend.app.models.opportunity import OpportunityTracking
from backend.app.models.tender import Tender
from backend.app.models.users import User
from backend.app.security import get_current_user

router = APIRouter(
    prefix="/api/notifications",
    tags=["Notifications"],
    dependencies=[Depends(get_current_user)],
)


class NotificationResponse(BaseModel):
    id: str
    type: str
    message: str
    read_flag: bool
    created_at: datetime


@router.get("", response_model=List[NotificationResponse])
def get_user_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves in-app notifications (FR-18).
    Auto-detects tenders closing within 7 days and alerts the user.
    """
    today = date.today()
    upcoming_limit = today + timedelta(days=7)

    # Check for opportunities or tenders closing within 7 days
    urgent_tenders = (
        db.query(Tender)
        .filter(
            Tender.status == "Open",
            Tender.deadline >= today,
            Tender.deadline <= upcoming_limit,
        )
        .all()
    )

    for tender in urgent_tenders:
        # Check if an alert already exists for this tender
        alert_msg = f"Approaching deadline: '{tender.title}' closes on {tender.deadline.isoformat()}."
        existing_notif = (
            db.query(Notification)
            .filter(
                Notification.user_id == current_user.id,
                Notification.message == alert_msg,
            )
            .first()
        )
        if not existing_notif:
            notif = Notification(
                user_id=current_user.id,
                type="DEADLINE_APPROACHING",
                message=alert_msg,
                read_flag=False,
            )
            db.add(notif)

    db.commit()

    user_notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )

    return [
        NotificationResponse(
            id=str(n.id),
            type=n.type,
            message=n.message,
            read_flag=n.read_flag,
            created_at=n.created_at,
        )
        for n in user_notifications
    ]


@router.patch("/{notification_id}/read", status_code=status.HTTP_200_OK)
def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks a specific notification as read."""
    notif = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found.")

    notif.read_flag = True
    db.commit()
    return {"message": "Notification marked as read.", "read": True}


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks all notifications for the authenticated user as read."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read_flag == False,
    ).update({"read_flag": True})
    db.commit()
    return {"message": "All notifications marked as read."}
