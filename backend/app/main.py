from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.cards import router as cards_router
from app.api.plans import router as plans_router
from app.api.points_of_sale import router as points_of_sale_router
from app.api.pos_accounts import router as pos_accounts_router
from app.api.print_jobs import router as print_jobs_router
from app.api.routers import router as routers_router
from app.api.user_manager import router as user_manager_router
from app.api.radius import router as radius_router
from app.api.reports import router as reports_router
from app.db.session import engine

app = FastAPI(
    title="ALOSTORA-RADIUS API",
    description="Backend API for the ALOSTORA-RADIUS network management system.",
    version="0.3.0",
)

# Development origins only. Restrict this list before production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(plans_router)
app.include_router(cards_router)
app.include_router(points_of_sale_router)
app.include_router(pos_accounts_router)
app.include_router(print_jobs_router)
app.include_router(routers_router)
app.include_router(user_manager_router)
app.include_router(radius_router)
app.include_router(reports_router)


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
