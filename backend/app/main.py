from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.routers import tenders

app = FastAPI(
    title="ETIOMS Backend",
    version="1.0.0",
    description="AI-Powered Ethiopian Tender Intelligence and Opportunity Management System"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect our tenders router
app.include_router(tenders.router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ETIOMS API"}