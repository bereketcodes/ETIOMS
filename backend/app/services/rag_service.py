import json
import os
from pathlib import Path
from typing import List, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from backend.app.models.tender import Tender
from backend.app.services.pdf_service import extract_text_from_pdf


class RAGAnswerSchema(BaseModel):
    answer: str = Field(description="Direct, accurate answer strictly grounded in the document context")
    citations: List[str] = Field(description="Specific citations like 'Page 1' or 'Eligibility Section', empty if not found")
    is_grounded: bool = Field(description="True if answered from text, False if information is unavailable in documents")


def _get_tender_document_text(tender: Tender) -> str:
    """Retrieves full text from tender source file if available, or synthesizes from metadata."""
    if tender.raw_document_path:
        doc_path = Path(tender.raw_document_path)
        if doc_path.exists():
            try:
                if doc_path.suffix.lower() == ".pdf":
                    return extract_text_from_pdf(str(doc_path))
                return doc_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass

    # Fallback context synthesized from extracted fields and notice description
    sections = [
        f"--- Tender Overview ---\nTitle: {tender.title}\nProcuring Entity: {tender.procuring_entity}\nSector: {tender.sector}\nRegion: {tender.region}\nDeadline: {tender.deadline}\nBudget: {tender.budget or 'Not specified'}",
        f"--- Scope of Work & Description ---\n{tender.description or 'No description provided.'}",
    ]
    if tender.requirements:
        req_text = "\n".join(f"- {r}" for r in tender.requirements)
        sections.append(f"--- Mandatory Requirements ---\n{req_text}")
    if tender.ai_summary:
        sections.append(f"--- AI Summary ---\n{tender.ai_summary}")
    if tender.extracted_requirements:
        sections.append(f"--- Extracted Parameters ---\n{json.dumps(tender.extracted_requirements, indent=2)}")

    return "\n\n".join(sections)


def answer_tender_question(tender: Tender, question: str) -> dict:
    """
    Answers natural language questions strictly grounded in the tender's indexed text.
    Cites specific page/section references or states that the information is unavailable.
    """
    if not question or not question.strip():
        return {
            "answer": "Please provide a specific question regarding this tender.",
            "citations": [],
            "is_grounded": False,
        }

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "answer": "AI Q&A service is temporarily unavailable: GEMINI_API_KEY is not configured.",
            "citations": [],
            "is_grounded": False,
        }

    document_text = _get_tender_document_text(tender)

    prompt = f"""
You are an expert procurement assistant for Ethiopian tenders (FPPA NCB/ICB tenders).
Answer the user's question STRICTLY and EXCLUSIVELY using the following tender document text.

CRITICAL INSTRUCTIONS:
1. Grounding: Rely ONLY on facts stated in the text. Do not make assumptions or extrapolate.
2. Citations: Identify and cite specific source references (e.g. "Page 1", "Section: Mandatory Requirements", "Eligibility Section").
3. Unavailable Information: If the provided text does not contain the answer, set is_grounded to false and state: "This information is not available in the provided tender documents." Do NOT invent an answer.

TENDER TITLE: {tender.title}
PROCURING ENTITY: {tender.procuring_entity}

TENDER DOCUMENT TEXT:
\"\"\"
{document_text[:40000]}
\"\"\"

QUESTION:
{question.strip()}
"""

    client = genai.Client(api_key=api_key)
    last_error = None

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RAGAnswerSchema,
                    temperature=0.1,
                ),
            )

            result = json.loads(response.text)
            return {
                "tender_id": str(tender.id),
                "question": question,
                "answer": result.get("answer", "No answer generated."),
                "citations": result.get("citations", []),
                "is_grounded": result.get("is_grounded", True),
            }
        except Exception as exc:
            last_error = exc
            import time
            time.sleep(1.0)

    # Graceful fallback: answer from structured metadata if Gemini free-tier experiences high-traffic spikes
    q_lower = question.lower()
    fallback_parts = []
    citations = []

    if any(k in q_lower for k in ["procuring", "who", "entity", "client", "issuer", "organization"]):
        if tender.procuring_entity:
            fallback_parts.append(f"Procuring Entity: {tender.procuring_entity}")
            citations.append("Tender Specifications: Procuring Entity")

    if any(k in q_lower for k in ["budget", "amount", "cost", "price", "cpo", "etb", "bond"]):
        if tender.budget:
            fallback_parts.append(f"Estimated Budget: {tender.budget:,.2f} ETB")
            citations.append("Tender Specifications: Financial Parameters")
        elif tender.extracted_requirements and isinstance(tender.extracted_requirements, dict) and tender.extracted_requirements.get("bid_bond_etb"):
            fallback_parts.append(f"Bid Bond / CPO: {tender.extracted_requirements.get('bid_bond_etb')} ETB")
            citations.append("Tender Specifications: Bid Bond")

    if any(k in q_lower for k in ["deadline", "due", "closing", "submission date"]):
        if tender.deadline:
            fallback_parts.append(f"Submission Deadline: {tender.deadline.isoformat()}")
            citations.append("Tender Specifications: Closing Date")

    if any(k in q_lower for k in ["requirement", "document", "license", "vat", "tax", "eligibility"]):
        if tender.requirements:
            fallback_parts.append("Mandatory Requirements:\n" + "\n".join(f"- {r}" for r in tender.requirements))
            citations.append("Tender Specifications: Requirements Section")

    if fallback_parts:
        return {
            "tender_id": str(tender.id),
            "question": question,
            "answer": "\n".join(fallback_parts),
            "citations": citations,
            "is_grounded": True,
        }

    return {
        "tender_id": str(tender.id),
        "question": question,
        "answer": "This information is not available in the provided tender documents.",
        "citations": [],
        "is_grounded": False,
    }

