from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.tender import Tender
from backend.app.schemas.tender import TenderCreate, TenderResponse

import shutil
from pathlib import Path
from fastapi import UploadFile, File
from backend.app.services.pdf_service import extract_text_from_pdf
from backend.app.services.ai_service import extract_tender_intelligence

router = APIRouter(prefix="/api/tenders", tags=["Tenders"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

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

@router.post("/extract-pdf")
async def extract_pdf_endpoint(file: UploadFile = File(...)):
    """Uploads a tender PDF, extracts text, and returns structured AI intelligence."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 1. Extract text from the PDF file
    extracted_text = extract_text_from_pdf(str(file_path))

    # 2. Extract intelligence via Gemini
    ai_data = extract_tender_intelligence(extracted_text)

    return {
        "filename": file.filename,
        "raw_text_preview": extracted_text[:400],
        "extracted_intelligence": ai_data
    }