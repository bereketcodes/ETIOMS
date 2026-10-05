from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database import Base, engine
from backend.app.models.tender import Tender
from backend.app.models.organization import OrganizationProfile
from backend.app.routers import tenders, profile, intelligence

# Initialize database schema
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ETIOMS API",
    version="1.0.0",
    description="Ethiopian Tender Intelligence & Automated Compliance System"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect modular endpoints
app.include_router(tenders.router)
app.include_router(profile.router)
app.include_router(intelligence.router)

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy", "engine": "ETIOMS Production Core"}