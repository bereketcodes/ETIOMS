from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class OrganizationBase(BaseModel):
    company_name: str = Field(..., example="AfroTech Solutions PLC")
    sectors: List[str] = Field(default_factory=list, example=["Information Technology"])
    operating_regions: List[str] = Field(default_factory=list, example=["Addis Ababa"])
    years_experience: int = Field(default=0, ge=0, example=5)
    certifications: List[str] = Field(default_factory=list, example=["ISO 27001", "Renewed Trade License"])
    past_projects_summary: Optional[str] = Field(
        default=None, 
        example="Delivered network virtualization and data center migration projects for financial institutions."
    )

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)