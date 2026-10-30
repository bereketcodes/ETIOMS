from datetime import date, timedelta
import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.tender import Tender
from backend.app.models.users import User
from backend.app.schemas.tender import TenderCreate, TenderIngestRequest, TenderResponse
from backend.app.services.embedding_service import cosine_similarity, generate_text_embedding
from backend.app.services.ingestion_service import parse_deadline, parse_tender_notice_text
from backend.app.services.pdf_service import extract_text_from_pdf
from backend.app.services.rag_service import answer_tender_question
from backend.app.security import get_current_user

logger = logging.getLogger(__name__)


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
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


def _public_or_organization_scope(user: User):
    return or_(Tender.organization_id.is_(None), Tender.organization_id == user.organization_id)


def _get_accessible_tender(db: Session, tender_id: UUID, current_user: User) -> Tender:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found.")
    if tender.organization_id not in (None, current_user.organization_id):
        raise HTTPException(status_code=403, detail="You do not have access to this tender.")
    return tender


async def save_upload_safely(file: UploadFile) -> Path:
    """Validate size and extension, then persist an uploaded file on disk with a UUID name."""
    original_name = Path(file.filename or "").name
    ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: .pdf, .txt",
        )

    try:
        file.file.seek(0)
    except (AttributeError, OSError):
        pass

    safe_filename = f"{uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / safe_filename

    size = 0
    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File is too large. Maximum allowed size is 20 MB.",
                    )
                buffer.write(chunk)
    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    return file_path


def _persist_ingested_tender(
    db: Session,
    parsed: dict,
    raw_document_path: Optional[str] = None,
    organization_id: Optional[UUID] = None,
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
        organization_id=organization_id,
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
        logger.exception("Tender notice validation failed while parsing uploaded notice.")
        raise HTTPException(status_code=500, detail="Unable to parse tender notice at this time.") from exc
    except Exception as exc:
        logger.exception("Unexpected error while parsing tender notice.")
        raise HTTPException(status_code=500, detail="Unable to parse tender notice at this time.") from exc


@router.get("", response_model=List[TenderResponse])
def get_all_tenders(
    query: Optional[str] = None,
    sector: Optional[str] = None,
    region: Optional[str] = None,
    status: Optional[str] = None,
    days_until_deadline: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch and filter tenders by sector, region, status, search keyword, and deadline window (FR-06)."""
    q = db.query(Tender).filter(_public_or_organization_scope(current_user))
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
def create_tender(
    payload: TenderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates and persists a tender to the database."""
    tender_data = payload.model_dump()
    if "organization_id" not in tender_data or tender_data["organization_id"] is None:
        tender_data["organization_id"] = current_user.organization_id
    new_tender = Tender(**tender_data)
    db.add(new_tender)
    db.commit()
    db.refresh(new_tender)
    return new_tender


@router.post("/ingest", response_model=TenderResponse, status_code=status.HTTP_201_CREATED)
def ingest_tender_notice(
    payload: TenderIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parse pasted procurement notice text with Gemini and persist an Open tender."""
    parsed = _ingest_notice_text(payload.text)
    return _persist_ingested_tender(db, parsed, organization_id=current_user.organization_id)


@router.post("/extract-pdf", response_model=TenderResponse, status_code=status.HTTP_201_CREATED)
async def extract_and_save_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF tender dossier, extract text, and persist a tender for this organization."""
    if file.filename is None or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_path = await save_upload_safely(file)
    try:
        extracted_text = extract_text_from_pdf(str(file_path))
    except Exception as exc:
        logger.exception("Failed to extract text from uploaded PDF.")
        raise HTTPException(status_code=500, detail="Unable to process the uploaded tender document.") from exc

    parsed = _ingest_notice_text(extracted_text)
    return _persist_ingested_tender(db, parsed, raw_document_path=str(file_path), organization_id=current_user.organization_id)


@router.post("/upload", response_model=TenderResponse, status_code=status.HTTP_201_CREATED)
async def upload_tender_notice(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ingest a procurement notice from an uploaded .pdf/.txt file or pasted text."""
    raw_text = (text or "").strip()
    saved_path = None

    if file and file.filename:
        saved_path = await save_upload_safely(file)
        if saved_path.suffix.lower() == ".pdf":
            try:
                raw_text = extract_text_from_pdf(str(saved_path))
            except Exception as exc:
                logger.exception("Failed to extract text from uploaded file.")
                raise HTTPException(status_code=500, detail="Unable to process the uploaded tender document.") from exc
        else:
            try:
                raw_text = saved_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                logger.exception("Failed to read uploaded text file.")
                raise HTTPException(status_code=500, detail="Unable to read the uploaded tender file.") from exc
    elif not raw_text:
        raise HTTPException(status_code=400, detail="Provide a tender notice text or upload a .pdf/.txt file.")

    parsed = _ingest_notice_text(raw_text)
    return _persist_ingested_tender(db, parsed, raw_document_path=str(saved_path) if saved_path else None, organization_id=current_user.organization_id)


@router.get("/semantic-search")
def search_tenders(query: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Finds tenders by meaning rather than exact word matching."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be blank.")

    try:
        query_vector = generate_text_embedding(query)
    except Exception:
        term = f"%{query.strip()}%"
        matches = (
            db.query(Tender)
            .filter(_public_or_organization_scope(current_user))
            .filter((Tender.title.ilike(term)) | (Tender.procuring_entity.ilike(term)))
            .all()
        )
        return [
            {"id": str(t.id), "title": t.title, "procuring_entity": t.procuring_entity, "similarity_score": 1.0}
            for t in matches
        ]

    tenders = db.query(Tender).filter(_public_or_organization_scope(current_user)).all()
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

        ranked_results.append(
            {"id": str(tender.id), "title": tender.title, "procuring_entity": tender.procuring_entity, "similarity_score": round(score, 3)}
        )

    ranked_results.sort(key=lambda item: item["similarity_score"], reverse=True)
    return ranked_results


@router.post("/compare")
def compare_tenders(payload: TenderCompareRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Side-by-side comparison of 2 to 5 tender opportunities (FR-17)."""
    tenders = (
        db.query(Tender)
        .filter(Tender.id.in_(payload.tender_ids))
        .filter(_public_or_organization_scope(current_user))
        .all()
    )
    if len(tenders) < 2:
        raise HTTPException(status_code=404, detail="Could not find sufficient matching tenders to compare.")

    comparison = []
    for t in tenders:
        comparison.append(
            {
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
            }
        )
    return comparison


@router.post("/{tender_id}/ask")
def ask_tender_question(
    tender_id: UUID,
    payload: TenderQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Natural-language question answering grounded in tender documents with citations (FR-14)."""
    tender = _get_accessible_tender(db, tender_id, current_user)
    return answer_tender_question(tender, payload.question)


@router.get("/{tender_id}", response_model=TenderResponse)
def get_tender_by_id(tender_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetch a single tender by its UUID."""
    return _get_accessible_tender(db, tender_id, current_user)


@router.get("")
def get_all_tenders_legacy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compatibility alias for older frontend calls; preserves organization-scoped access."""
    return db.query(Tender).filter(_public_or_organization_scope(current_user)).all()


@router.get("/search")
def search_tenders_by_keyword(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Backward-compatible tender search endpoint with organization access enforcement."""
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be blank.")
    term = f"%{query.strip()}%"
    return (
        db.query(Tender)
        .filter(_public_or_organization_scope(current_user))
        .filter((Tender.title.ilike(term)) | (Tender.procuring_entity.ilike(term)) | (Tender.description.ilike(term)))
        .all()
    )


@router.get("/download/{tender_id}")
def download_tender_document(
    tender_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a saved tender document only when the user can access the tender."""
    tender = _get_accessible_tender(db, tender_id, current_user)
    if not tender.raw_document_path:
        raise HTTPException(status_code=404, detail="No document stored for this tender.")
    return {"document_path": tender.raw_document_path}


@router.get("/public")
def get_public_tenders(db: Session = Depends(get_db)):
    """Public tender notices remain globally visible while private tenders stay organization-scoped."""
    return db.query(Tender).filter(Tender.organization_id.is_(None)).all()


@router.get("/org")
def get_org_tenders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List the user's organization tenders and public tenders."""
    return db.query(Tender).filter(_public_or_organization_scope(current_user)).all()


@router.get("/by-organization/{organization_id}")
def get_tenders_by_organization(
    organization_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ensure callers can only inspect their own organization, not another org's private tenders."""
    if current_user.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Organization access denied.")
    return db.query(Tender).filter(_public_or_organization_scope(current_user)).all()


@router.get("/{tender_id}/documents")
def get_tender_documents(
    tender_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return tender document metadata only for accessible tenders."""
    tender = _get_accessible_tender(db, tender_id, current_user)
    if not tender.raw_document_path:
        return []
    return [{"path": tender.raw_document_path, "name": Path(tender.raw_document_path).name}]
