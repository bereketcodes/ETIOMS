from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

class OrganizationBase(BaseModel):
    name: str = Field(..., example="Afro Computing Solutions")
    industry: str = Field(..., example="Information Technology")
    services: List[str] = Field(default_factory=list, example=["Web Development", "Cloud Solutions"])
    areas_of_operation: Optional[str] = Field(None, example="Addis Ababa, Hawassa")
    experience_years: int = Field(default=0, ge=0, example=5)
    certifications: List[str] = Field(default_factory=list, example=["ISO 9001", "Cisco CCNA"])

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    id: UUID

    class Config:
        from_attributes = True