from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.tender import Tender
from backend.app.schemas.tender import TenderCreate, TenderResponse

router = APIRouter(prefix="/api/tenders", tags=["Tenders"])

@router.get("", response_model=List[TenderResponse])
def get_all_tenders(db: Session = Depends(get_db)):
    """Fetch all tenders persisted in the database."""
    return db.query(Tender).all()

@router.post("", response_model=TenderResponse, status_code=status.HTTP_201_CREATED)
def create_tender(payload: TenderCreate, db: Session = Depends(get_db)):
    """Creates and persists a tender to the database."""
    new_tender = Tender(**payload.model_dump())
    db.add(new_tender)
    db.commit()
    db.refresh(new_tender)
    return new_tender

@router.get("/{tender_id}", response_model=TenderResponse)
def get_tender_by_id(tender_id: UUID, db: Session = Depends(get_db)):
    """Fetch a single tender by its UUID."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender