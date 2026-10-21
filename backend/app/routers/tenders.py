from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.tender import Tender
from backend.app.schemas.tender import TenderCreate, TenderIngestRequest, TenderResponse

import shutil
from pathlib import Path
from backend.app.services.pdf_service import extract_text_from_pdf
from backend.app.services.ingestion_service import parse_deadline, parse_tender_notice_text
from backend.app.services.embedding_service import generate_text_embedding, cosine_similarity
from backend.app.services.rag_service import answer_tender_question
from backend.app.security import get_current_user
from sqlalchemy import or_


class TenderQuestionRequest(BaseModel):
    question: str = Field(..., min_length=2, description="Natural language question about tender specifications")


class TenderCompareRequest(BaseModel):
    tender_ids: List[UUID] = Field(..., min_length=2, max_length=5, description="List of tender UUIDs to compare")


router = APIRouter(
    prefix="/api/tenders",
    tags=["Tenders"],
    dependencies=[Depends(get_current_user)],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB in bytes
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

async def save_upload_safely(file: UploadFile) -> tuple[Path, bytes]:
    """
    Validates file extension and size, saves to disk with a random UUID name,
    and returns (saved_path, raw_bytes).
    """
    # 1. Safely extract only the file extension (ignores any ../ path tricks)
    original_name = Path(file.filename or "").name
    ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: .pdf, .txt"
        )

    # 2. Read bytes and enforce the 20 MB limit
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is too large. Maximum allowed size is 20 MB."
        )

    # 3. Generate a safe, collision-proof filename on disk
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / safe_filename

    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)

    return file_path, file_bytes
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
def get_all_tenders(
    query: Optional[str] = None,
    sector: Optional[str] = None,
    region: Optional[str] = None,
    status: Optional[str] = None,
    days_until_deadline: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Fetch and filter tenders by sector, region, status, search keyword, and deadline window (FR-06)."""
    q = db.query(Tender)
    if status:
        q = q.filter(Tender.status == status)
    if sector and sector.lower() != "all sectors":
        q = q.filter(Tender.sector.ilike(f"%{sector}%"))
    if region and region.lower() != "all regions":
        q = q.filter(Tender.region.ilike(f"%{region}%"))
    if query and query.strip():
        term = f"%{query.strip()}%"
        q = q.filter(
            (Tender.title.ilike(term))
            | (Tender.procuring_entity.ilike(term))
            | (Tender.description.ilike(term))
        )
    if days_until_deadline is not None:
        today = date.today()
        cutoff = today + timedelta(days=days_until_deadline)
        q = q.filter(Tender.deadline >= today, Tender.deadline <= cutoff)

    return q.order_by(Tender.deadline.asc()).all()

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
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    1. Uploads tender PDF dossier
    2. Extracts clean text with pypdf
    3. Gemini ingestion structures title, entity, sector, region, deadline, budget, requirements
    4. Automatically persists as an active tender in the database
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_path, _ = await save_upload_safely(file)
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

    try:
        query_vector = generate_text_embedding(query)
    except Exception:
        # Fallback to lexical search if embedding service encounters error
        term = f"%{query.strip()}%"
        matches = db.query(Tender).filter(
            (Tender.title.ilike(term)) | (Tender.procuring_entity.ilike(term))
        ).all()
        return [
            {
                "id": str(t.id),
                "title": t.title,
                "procuring_entity": t.procuring_entity,
                "similarity_score": 1.0,
            }
            for t in matches
        ]

    tenders = db.query(Tender).all()
    if not tenders:
        return []

    ranked_results = []
    for tender in tenders:
        if not tender.embedding:
            try:
                text_to_embed = f"{tender.title}. {tender.description or ''}"
                tender.embedding = generate_text_embedding(text_to_embed)
                db.commit()
            except Exception:
                pass

        if tender.embedding:
            try:
                score = cosine_similarity(query_vector, tender.embedding)
            except Exception:
                score = 0.0
        else:
            score = 0.0

        ranked_results.append({
            "id": str(tender.id),
            "title": tender.title,
            "procuring_entity": tender.procuring_entity,
            "similarity_score": round(score, 3),
        })

    ranked_results.sort(key=lambda item: item["similarity_score"], reverse=True)
    return ranked_results


@router.post("/compare")
def compare_tenders(payload: TenderCompareRequest, db: Session = Depends(get_db)):
    """Side-by-side comparison of 2 to 5 tender opportunities (FR-17)."""
    tenders = db.query(Tender).filter(Tender.id.in_(payload.tender_ids)).all()
    if len(tenders) < 2:
        raise HTTPException(status_code=404, detail="Could not find sufficient matching tenders to compare.")

    comparison = []
    for t in tenders:
        comparison.append({
            "id": str(t.id),
            "title": t.title,
            "procuring_entity": t.procuring_entity,
            "sector": t.sector,
            "region": t.region,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "budget": t.budget,
            "status": t.status,
            "requirements": t.requirements or [],
            "ai_summary": t.ai_summary or t.description,
        })
    return comparison


@router.post("/{tender_id}/ask")
def ask_tender_question(
    tender_id: UUID,
    payload: TenderQuestionRequest,
    db: Session = Depends(get_db),
):
    """
    Natural-language question answering grounded in tender documents with citations (FR-14).
    Complies with SRS acceptance criteria:
    - Retrieves relevant document sections and returns answer citing source section/page.
    - If answer cannot be found in documents, clearly states information is unavailable.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found.")

    return answer_tender_question(tender, payload.question)

@router.post("/extract-pdf") 
async def upload_tender_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  
):
    new_tender = Tender(
        title=extracted["title"],
        # ... other existing fields ...
        organization_id=current_user.organization_id  
    )
    db.add(new_tender)
    db.commit()
    
@router.get("/{tender_id}", response_model=TenderResponse)
def get_tender_by_id(tender_id: UUID, db: Session = Depends(get_db)):
    """Fetch a single tender by its UUID."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender
@router.get("")
def get_all_tenders(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    tenders = db.query(Tender).filter(
        or_(
            Tender.organization_id == None,
            Tender.organization_id == current_user.organization_id
        )
    ).all()
    
    return tenders