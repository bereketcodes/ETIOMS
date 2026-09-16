import json
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

class ExtractedTenderRequirements(BaseModel):
    procuring_entity: str = Field(description="Name of organization issuing the bid")
    submission_deadline: str = Field(description="Deadline date in YYYY-MM-DD format if available, or raw text")
    bid_bond_etb: float | None = Field(description="Bid bond / CPO amount in ETB, null if not mentioned")
    eligibility_criteria: list[str] = Field(description="Mandatory qualification rules like years of experience or certifications")
    required_documents: list[str] = Field(description="Mandatory documents: VAT, TIN, Trade License, Tax Clearance, etc.")
    executive_summary: str = Field(description="Concise 2-3 sentence overview of what is being procured and key risks")

def extract_tender_intelligence(raw_text: str) -> dict:
    """Sends raw tender text to Gemini and returns structured JSON dictionary."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are a senior procurement analyst for Ethiopian tenders.
Analyze the following tender document text and extract all required fields accurately.
Ground all answers strictly in the provided text.

TENDER DOCUMENT TEXT:
{raw_text[:30000]}
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractedTenderRequirements,
            temperature=0.1,
        ),
    )

    return json.loads(response.text)