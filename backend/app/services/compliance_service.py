import json
import os
from typing import List, Dict, Any
from fastapi import HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from backend.app.models.tender import Tender
from backend.app.models.organization import OrganizationProfile

class MandatoryCheckItem(BaseModel):
    requirement_name: str = Field(description="Name of the compliance requirement")
    is_mandatory: bool = Field(default=True)
    status: str = Field(description="'PASS', 'FAIL', or 'WARNING'")
    evidence_or_gap: str = Field(description="Details verifying vendor compliance or citing missing criteria")

class ComplianceAuditReport(BaseModel):
    bid_decision: str = Field(description="'BID', 'NO-BID', or 'CONDITIONAL'")
    executive_justification: str = Field(description="High-level synthesis of audit outcome")
    preliminary_checklist: List[MandatoryCheckItem] = Field(description="Mandatory Ethiopian procurement criteria")
    critical_disqualification_risks: List[str] = Field(description="Blockers that trigger immediate rejection under FPPA rules")
    procurement_safeguards: List[str] = Field(description="Actions required prior to final envelope sealing")

def evaluate_compliance(profile: OrganizationProfile, tender: Tender) -> Dict[str, Any]:
    """
    Performs deterministic legal screening combined with LLM qualification auditing.
    Checks Ethiopian FPPA compliance:
    - Renewed Trade License
    - Tax Clearance Certificate
    - VAT Registration Certificate
    - Bid Security (CPO / Bank Guarantee)
    """
    # 1. Deterministic Heuristics Check against vendor profile
    certifications_lower = [c.lower() for c in (profile.certifications or [])]
    
    preliminary_checklist: List[Dict[str, Any]] = []
    has_trade_license = any("trade license" in c or "business license" in c for c in certifications_lower)
    has_tax_clearance = any("tax clearance" in c for c in certifications_lower)
    has_vat = any("vat" in c or "tin" in c for c in certifications_lower)

    preliminary_checklist.append({
        "requirement_name": "Valid Renewed Business/Trade License",
        "is_mandatory": True,
        "status": "PASS" if has_trade_license else "FAIL",
        "evidence_or_gap": "Provided in company certifications" if has_trade_license else "Missing mandatory renewed trade license"
    })
    preliminary_checklist.append({
        "requirement_name": "Tax Clearance Certificate (Ministry of Revenues)",
        "is_mandatory": True,
        "status": "PASS" if has_tax_clearance else "FAIL",
        "evidence_or_gap": "Provided in company certifications" if has_tax_clearance else "No valid tax clearance record found"
    })
    preliminary_checklist.append({
        "requirement_name": "VAT Registration & TIN",
        "is_mandatory": True,
        "status": "PASS" if has_vat else "FAIL",
        "evidence_or_gap": "Verified in company records" if has_vat else "Missing VAT/TIN documentation"
    })

    # 2. LLM Qualitative Evaluation & Risk Analysis
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY environment variable missing.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are a Lead Ethiopian Public Procurement & Compliance Auditor adhering to FDRE FPPA directives.
Audit the following tender against the vendor profile.

TENDER SPECIFICATIONS:
Title: {tender.title}
Entity: {tender.procuring_entity}
Sector: {tender.sector}
Stated Requirements: {tender.requirements}
AI Summary: {tender.ai_summary}

VENDOR PROFILE:
Company: {profile.company_name}
Experience: {profile.years_experience} years
Operating Regions: {profile.operating_regions}
Certifications: {profile.certifications}
Past Projects: {profile.past_projects_summary}

AUDIT INSTRUCTIONS:
1. Under Ethiopian Public Procurement procedures, lack of mandatory administrative certificates results in immediate disqualification at preliminary opening.
2. Determine whether the company's past projects demonstrate the technical capability needed for this specific bid.
3. Check bid bond / CPO requirements.
4. Output a definitive decision: 'BID', 'NO-BID', or 'CONDITIONAL'.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ComplianceAuditReport,
                temperature=0.1
            )
        )
        audit_data = json.loads(response.text)
        
        # Merge deterministic checklist with AI evaluation
        audit_data["preliminary_checklist"] = preliminary_checklist + audit_data.get("preliminary_checklist", [])
        return audit_data

    except Exception as exc:
        # Fallback if AI service experiences latency or quota limits
        immediate_fails = [item["requirement_name"] for item in preliminary_checklist if item["status"] == "FAIL"]
        return {
            "bid_decision": "NO-BID" if immediate_fails else "CONDITIONAL",
            "executive_justification": f"Automated evaluation completed with rule-based fallback: {str(exc)}",
            "preliminary_checklist": preliminary_checklist,
            "critical_disqualification_risks": [f"Missing: {item}" for item in immediate_fails],
            "procurement_safeguards": ["Manually review tender dossier requirements against legal certificates."]
        }