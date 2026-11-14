from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine

app = FastAPI(
    title="ALOSTORA-RADIUS API",
    description="Backend API for the ALOSTORA-RADIUS network management system.",
    version="0.2.0",
)

# Development origins only. Restrict this list before production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Process liveness check; does not require database availability."""
    return {
        "status": "ok",
        "service": "alostora-radius-api",
        "version": app.version,
    }


@app.get("/health/ready", tags=["system"])
def readiness_check():
    """Readiness check verifies that PostgreSQL accepts a simple query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable"},
        )
    return {"status": "ready", "database": "connected"}


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"message": "ALOSTORA-RADIUS API", "docs": "/docs"}
