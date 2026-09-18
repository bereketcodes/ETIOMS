import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from backend.app.models.tender import Tender
from backend.app.models.organization import OrganizationProfile

class SemanticEvaluation(BaseModel):
    semantic_score: float = Field(..., ge=0, le=30, description="Technical capability match score between 0 and 30")
    justification: str = Field(..., description="Brief explanation of strengths, gaps, or missing criteria")

def calculate_match_score(profile: OrganizationProfile, tender: Tender) -> dict:
    """Calculates a 0-100 compatibility score between a company profile and a tender."""
    
    # --- 1. Deterministic Heuristics (Max: 70 pts) ---
    det_score = 0.0
    breakdown = {}

    # Sector Match (25 pts)
    company_sectors = [s.lower() for s in (profile.sectors or [])]
    tender_sector = (tender.sector or "").lower()
    if any(s in tender_sector or tender_sector in s for s in company_sectors):
        det_score += 25.0
        breakdown["sector_match"] = 25.0
    else:
        breakdown["sector_match"] = 0.0

    # Region Match (20 pts)
    company_regions = [r.lower() for r in (profile.operating_regions or [])]
    tender_region = (tender.region or "").lower()
    if "ethiopia" in company_regions or any(r in tender_region for r in company_regions):
        det_score += 20.0
        breakdown["region_match"] = 20.0
    else:
        breakdown["region_match"] = 0.0

    # Experience Match (25 pts)
    # Default rule: award full 25 pts if company has >= 3 years experience, scaled otherwise
    exp_points = min(25.0, (profile.years_experience / 3.0) * 25.0)
    det_score += exp_points
    breakdown["experience_score"] = round(exp_points, 1)

   # --- 2. AI Semantic Match (Max: 30 pts) ---
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)

        ai_prompt = f"""
You are evaluating vendor compatibility for an Ethiopian procurement tender.
Score the vendor's technical capability from 0 to 30 based on their past projects and certifications.

TENDER REQUIREMENTS & SUMMARY:
Title: {tender.title}
Requirements: {tender.requirements}
AI Summary: {tender.ai_summary}

VENDOR QUALIFICATIONS:
Certifications: {profile.certifications}
Past Projects: {profile.past_projects_summary}
Years in Business: {profile.years_experience}
"""

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=ai_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SemanticEvaluation,
                temperature=0.1
            )
        )

        ai_result = json.loads(response.text)
        semantic_pts = float(ai_result.get("semantic_score", 0.0))
        breakdown["ai_semantic_score"] = semantic_pts
        breakdown["ai_justification"] = ai_result.get("justification", "")

    except Exception as e:
        # Graceful degradation: do not crash if Google has a temporary outage
        semantic_pts = 0.0
        breakdown["ai_semantic_score"] = 0.0
        breakdown["ai_justification"] = f"AI service temporarily unavailable (spikes in demand). Deterministic score preserved. Error: {str(e)}"

    total_score = round(min(100.0, det_score + semantic_pts), 1)

    return {
        "tender_id": str(tender.id),
        "total_score": total_score,
        "is_qualified": total_score >= 60.0,
        "breakdown": breakdown
    }