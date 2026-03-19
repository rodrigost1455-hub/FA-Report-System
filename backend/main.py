"""
main.py — Entry point de la aplicación FastAPI
FA Report Automation System — Yazaki Electronics Durango
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config      import settings
from app.core.exceptions  import register_exception_handlers
from app.api.routes       import reports, images, test_results, pdf, catalog, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.config import ensure_template_downloaded
    await ensure_template_downloaded()   # Descarga el template si no existe (Railway)
    yield


app = FastAPI(
    title       = "FA Report API",
    description = "Automatización de reportes de análisis de fallas — Yazaki Electronics Durango",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

register_exception_handlers(app)

app.include_router(reports.router,      prefix="/api/reports",       tags=["Reports"])
app.include_router(images.router,       prefix="/api/reports",       tags=["Images"])
app.include_router(test_results.router, prefix="/api/reports",       tags=["Test Results"])
app.include_router(pdf.router,          prefix="/api/reports",       tags=["PDF"])
app.include_router(catalog.router,      prefix="/api/tests-catalog", tags=["Catalog"])
app.include_router(users.router,        prefix="/api/users",         tags=["Users"])


@app.get("/health", tags=["Health"])
def health_check():
    from pathlib import Path
    template_ok = Path(settings.TEMPLATE_PDF_PATH).exists()
    return {
        "status":       "ok",
        "service":      "FA Report API",
        "template_pdf": "found" if template_ok else "MISSING",
    }
