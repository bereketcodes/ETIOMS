import json
import os
from typing import Dict, Any, List
from fastapi import HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from backend.app.models.tender import Tender
from backend.app.models.organization import OrganizationProfile

class BidDocumentChecklist(BaseModel):
    envelope_type: str = Field(description="'Technical Envelope' or 'Financial Envelope'")
    document_title: str = Field(description="Name of item to include")
    copies_required: int = Field(default=2, description="Standard Ethiopian requirement: 1 Original + 2 Copies")

class BidProposalDossier(BaseModel):
    formal_submission_letter: str = Field(description="Formal letter addressed to the procuring entity")
    executive_technical_approach: str = Field(description="Methodology and execution strategy")
    personnel_qualification_matrix: List[str] = Field(description="Key proposed technical roles and qualifications")
    quality_assurance_and_sla: str = Field(description="QA procedures, warranty, and support terms")
    mandatory_envelope_checklist: List[BidDocumentChecklist] = Field(description="Two-envelope checklist")

def generate_bid_proposal(profile: OrganizationProfile, tender: Tender) -> Dict[str, Any]:
    """Generates an FPPA-standard compliant technical proposal draft."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are a Senior Bidding & Tender Proposal Architect specializing in Ethiopian National Competitive Bidding (NCB).
Generate a tailored Technical Proposal Draft for this vendor applying to the specified tender.

TENDER:
Title: {tender.title}
Client: {tender.procuring_entity}
Requirements: {tender.requirements}
Summary: {tender.ai_summary}

VENDOR:
Name: {profile.company_name}
Experience: {profile.years_experience} years
Track Record: {profile.past_projects_summary}
Certifications: {profile.certifications}

STRUCTURE REQUIREMENTS:
1. Formal Submission Letter: Following standard PPA Bid Submission templates, addressed to {tender.procuring_entity}.
2. Executive Technical Approach: Detailed methodology addressing the scope.
3. Personnel Matrix: Proposed team staffing.
4. QA & SLA: Warranties, risk mitigation, and compliance.
5. Two-Envelope Submission Checklist: Explicitly separating Technical vs. Financial envelopes (1 Original + 2 Copies).
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BidProposalDossier,
                temperature=0.2
            )
        )
        return json.loads(response.text)

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Proposal generation engine unavailable: {str(exc)}"
        )