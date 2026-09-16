import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

# 1. Define the schema for structured extraction
class SampleTenderExtract(BaseModel):
    procuring_entity: str = Field(description="Organization issuing the tender")
    bid_bond_etb: float | None = Field(description="Bid bond or CPO amount in ETB, if mentioned")
    submission_deadline: str = Field(description="Deadline date in YYYY-MM-DD or descriptive text")
    required_licenses: list[str] = Field(description="List of mandatory documents or licenses")

# 2. Initialize the client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

sample_text = """
Commercial Bank of Ethiopia (CBE) invites sealed bids from eligible bidders for 
the supply of Data Center Server Racks. Bid No. CBE/24/2026.
Bids must be delivered before 2026-11-20 at 10:00 AM.
Bidders must submit an unconditional Bid Security of ETB 200,000.00 in the form of CPO.
Eligible bidders must present renewed Trade License, VAT Registration Certificate, and Tax Clearance.
"""

# 3. Request structured JSON from Gemini
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"Extract the requirements from this tender text:\n\n{sample_text}",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SampleTenderExtract,
        temperature=0.1,
    ),
)

print("\n--- Extracted JSON Result ---")
print(response.text)