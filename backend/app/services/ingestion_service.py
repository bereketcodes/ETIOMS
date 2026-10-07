import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class ExtractedTenderSchema(BaseModel):
    title: str = Field(description="Official tender title")
    procuring_entity: str = Field(description="Government bureau, ministry, or enterprise floating the tender")
    sector: str = Field(description="Primary sector, e.g., Information Technology, Construction, Healthcare")
    region: str = Field(description="Operational region, e.g., Addis Ababa, Oromia, Federal")
    deadline: str = Field(description="Closing submission date in YYYY-MM-DD format if detected, or standard string")
    budget: Optional[float] = Field(default=None, description="Estimated budget or procurement ceiling if stated")
    requirements: List[str] = Field(default_factory=list, description="List of technical, financial, and eligibility requirements")
    description: str = Field(description="Comprehensive summary of the scope of work")

def parse_tender_notice_text(raw_text: str) -> dict:
    prompt = f"""
    You are an expert Ethiopian public procurement intelligence analyst specializing in FPPA standards.
    Extract structured tender parameters from the following procurement notice text:
    
    \"\"\"{raw_text}\"\"\"
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractedTenderSchema,
            temperature=0.1
        )
    )
    return json.loads(response.text)
