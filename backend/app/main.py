from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.database import Base, engine
from backend.app.routers import tenders

# Automatically creates tables in etioms.db if they don't exist yet
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

app.include_router(tenders.router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ETIOMS API"}