from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from fastapi.middleware.cors import CORSMiddleware  # Added missing import

app = FastAPI(
    title="Trust Pass API",
    description="Backend API service",
    version="1.0.0"
)

# Allow requests from your Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/status", tags=["Health Check"])
async def status_get(db: Session = Depends(get_db)):
  """
  Health check endpoint to verify API and PostgreSQL database status.
  """
  try:
    db.execute(text("SELECT 1"))
    db_status = "connected"
  except Exception as e:
    raise HTTPException(
      status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
      detail=f"Database connectivity failed: {str(e)}"
    )

  return {
    "Backend": "online",
    "Database": db_status,
  }
