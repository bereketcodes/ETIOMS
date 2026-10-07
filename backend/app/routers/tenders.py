from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.tender import Tender
from backend.app.schemas.tender import TenderCreate, TenderIngestRequest, TenderResponse

import shutil
from pathlib import Path
from backend.app.services.pdf_service import extract_text_from_pdf
from backend.app.services.ingestion_service import parse_deadline, parse_tender_notice_text

from backend.app.services.embedding_service import generate_text_embedding, cosine_similarity


router = APIRouter(prefix="/api/tenders", tags=["Tenders"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def _persist_ingested_tender(
    db: Session,
    parsed: dict,
    raw_document_path: Optional[str] = None,
) -> Tender:
    """Map Gemini ingestion output onto a Tender row and save it."""
    new_tender = Tender(
        title=parsed.get("title") or "Untitled Tender",
        procuring_entity=parsed.get("procuring_entity") or "Unknown Entity",
        sector=parsed.get("sector") or "General Procurement",
        region=parsed.get("region") or "Ethiopia",
        deadline=parse_deadline(parsed.get("deadline")),
        status="Open",
        description=parsed.get("description") or "",
        budget=parsed.get("budget"),
        requirements=parsed.get("requirements") or [],
        raw_document_path=raw_document_path,
        ai_summary=parsed.get("description"),
        extracted_requirements=parsed,
    )
    db.add(new_tender)
    db.commit()
    db.refresh(new_tender)
    return new_tender


def _ingest_notice_text(raw_text: str) -> dict:
    if not raw_text or not raw_text.strip():
        raise HTTPException(status_code=400, detail="Tender notice text is empty.")
    try:
        return parse_tender_notice_text(raw_text)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to parse tender notice: {exc}",
        ) from exc


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


@router.post("/ingest", response_model=TenderResponse, status_code=status.HTTP_201_CREATED)
def ingest_tender_notice(
    payload: TenderIngestRequest,
    db: Session = Depends(get_db),
):
    """
    Parse pasted procurement notice text with Gemini and persist an Open tender.
    Use this when the notice is copied from a portal rather than uploaded as PDF.
    """
    parsed = _ingest_notice_text(payload.text)
    return _persist_ingested_tender(db, parsed)


@router.post("/extract-pdf", response_model=TenderResponse, status_code=status.HTTP_201_CREATED)
async def extract_and_save_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    1. Uploads tender PDF dossier
    2. Extracts clean text with pypdf
    3. Gemini ingestion structures title, entity, sector, region, deadline, budget, requirements
    4. Automatically persists as an active tender in the database
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    extracted_text = extract_text_from_pdf(str(file_path))
    parsed = _ingest_notice_text(extracted_text)
    return _persist_ingested_tender(db, parsed, raw_document_path=str(file_path))


@router.post("/upload", response_model=TenderResponse, status_code=status.HTTP_201_CREATED)
async def upload_tender_notice(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Ingest a procurement notice from an uploaded .pdf/.txt file or pasted text.
    """
    raw_text = (text or "").strip()
    saved_path = None

    if file and file.filename:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in {".pdf", ".txt"}:
            raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported.")

        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_path = str(file_path)

        if suffix == ".pdf":
            raw_text = extract_text_from_pdf(saved_path)
        else:
            raw_text = Path(saved_path).read_text(encoding="utf-8", errors="ignore")

    parsed = _ingest_notice_text(raw_text)
    return _persist_ingested_tender(db, parsed, raw_document_path=saved_path)


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


@router.get("/{tender_id}", response_model=TenderResponse)
def get_tender_by_id(tender_id: UUID, db: Session = Depends(get_db)):
    """Fetch a single tender by its UUID."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender