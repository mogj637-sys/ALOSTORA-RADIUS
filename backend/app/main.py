from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ALOSTORA-RADIUS API",
    description="Backend API for the ALOSTORA-RADIUS network management system.",
    version="0.1.0",
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
    """Lightweight process health check; database readiness is added with migrations."""
    return {
        "status": "ok",
        "service": "alostora-radius-api",
        "version": app.version,
    }


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"message": "ALOSTORA-RADIUS API", "docs": "/docs"}
