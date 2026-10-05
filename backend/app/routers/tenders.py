from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.tender import Tender
from backend.app.schemas.tender import TenderCreate, TenderResponse

import shutil
from pathlib import Path
from backend.app.services.pdf_service import extract_text_from_pdf
from backend.app.services.ai_service import extract_tender_intelligence

from datetime import datetime, date

from backend.app.services.embedding_service import generate_text_embedding, cosine_similarity


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

@router.post("/extract-pdf", response_model=TenderResponse, status_code=status.HTTP_201_CREATED)
async def extract_and_save_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    1. Uploads tender PDF dossier
    2. Extracts clean text with pypdf
    3. Gemini structures requirements into verified JSON
    4. Automatically persists as an active tender in the database
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 1. Extract plain text
    extracted_text = extract_text_from_pdf(str(file_path))

    # 2. Extract intelligence via Gemini
    ai_data = extract_tender_intelligence(extracted_text)

    # 3. Parse deadline safely (fallback to 30 days ahead if ambiguous)
    deadline_val = date.today()
    if ai_data.get("submission_deadline"):
        try:
            # Assumes YYYY-MM-DD
            deadline_val = datetime.strptime(ai_data["submission_deadline"][:10], "%Y-%m-%d").date()
        except ValueError:
            deadline_val = date.today()

    # 4. Save directly to Database
    new_tender = Tender(
        title=f"Procurement by {ai_data.get('procuring_entity', 'Public Entity')}",
        procuring_entity=ai_data.get("procuring_entity", "Unknown Entity"),
        sector="General Procurement",
        region="Ethiopia",
        deadline=deadline_val,
        status="Open",
        description=ai_data.get("executive_summary", ""),
        budget=ai_data.get("bid_bond_etb"),
        requirements=ai_data.get("eligibility_criteria", []) + ai_data.get("required_documents", []),
        raw_document_path=str(file_path),
        ai_summary=ai_data.get("executive_summary"),
        extracted_requirements=ai_data
    )

    db.add(new_tender)
    db.commit()
    db.refresh(new_tender)

    return new_tender

@router.get("/semantic-search")
def search_tenders(query: str, db: Session = Depends(get_db)):
    """Finds tenders by meaning rather than exact word matching."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be blank.")

    # 1. Turn the user's search text into numbers
    query_vector = generate_text_embedding(query)

    # 2. Get all tenders from the database
    tenders = db.query(Tender).all()
    if not tenders:
        return []

    ranked_results = []

    # 3. Compare each tender against the query
    for tender in tenders:
        # If the tender does not have an embedding yet, make one on the fly
        if not tender.embedding:
            text_to_embed = f"{tender.title}. {tender.description or ''}"
            tender.embedding = generate_text_embedding(text_to_embed)
            db.commit()

        # Calculate closeness
        try:
            score = cosine_similarity(query_vector, tender.embedding)
        except ValueError:
            score = 0.0

        ranked_results.append({
            "id": str(tender.id),
            "title": tender.title,
            "procuring_entity": tender.procuring_entity,
            "similarity_score": round(score, 3)
        })

    # 4. Sort from highest match to lowest match
    ranked_results.sort(key=lambda item: item["similarity_score"], reverse=True)
    return ranked_results