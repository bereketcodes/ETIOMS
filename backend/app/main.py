from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.database import Base, engine
from backend.app.routers import tenders, profile
from backend.app.models.organization import OrganizationProfile
from backend.app.models.tender import Tender

# Importing both models before this call registers both tables with SQLAlchemy.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ETIOMS Backend",
    version="1.0.0",
    description="AI-Powered Ethiopian Tender Intelligence System"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect modular routers
app.include_router(tenders.router)
app.include_router(profile.router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ETIOMS API"}
