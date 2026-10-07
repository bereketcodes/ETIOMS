import json
import os
from datetime import date, datetime
from typing import List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()


class ExtractedTenderSchema(BaseModel):
    title: str = Field(description="Official tender title")
    procuring_entity: str = Field(description="Government bureau, ministry, or enterprise floating the tender")
    sector: str = Field(description="Primary sector, e.g., Information Technology, Construction, Healthcare")
    region: str = Field(description="Operational region, e.g., Addis Ababa, Oromia, Federal")
    deadline: str = Field(description="Closing submission date in YYYY-MM-DD format if detected, or standard string")
    budget: Optional[float] = Field(default=None, description="Estimated budget or procurement ceiling if stated")
    requirements: List[str] = Field(default_factory=list, description="List of technical, financial, and eligibility requirements")
    description: str = Field(description="Comprehensive summary of the scope of work")


def parse_deadline(deadline_str: Optional[str]) -> date:
    """Convert Gemini deadline text to a date; fall back to today if it is not YYYY-MM-DD."""
    if not deadline_str:
        return date.today()
    try:
        return datetime.strptime(deadline_str.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def parse_tender_notice_text(raw_text: str) -> dict:
    """Send procurement notice text to Gemini and return structured tender fields."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)
    prompt = f"""
You are an expert Ethiopian public procurement intelligence analyst specializing in FPPA standards.
Extract structured tender parameters from the following procurement notice text.
Ground all answers strictly in the provided text.

PROCUREMENT NOTICE TEXT:
\"\"\"{raw_text[:30000]}\"\"\"
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractedTenderSchema,
            temperature=0.1,
        ),
    )
    if not response.text:
        raise ValueError("Gemini returned an empty ingestion response.")
    return json.loads(response.text)
