"""SaaSShadow.ai — SaaS-to-SaaS integration risk monitoring.

Lightweight open-source tool that detects OAuth over-permission,
API token misuse, credential exposure, and cross-platform data flow
risks in SaaS integration configurations.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings

from app.api.connectors import router as connectors_router
from app.api.dashboard import router as dashboard_router
from app.api.ispm import router as ispm_router
from app.api.routes import router as core_router
from app.api.scan import router as scan_router
from app.api.scans import router as scans_router
from app.core.limiter import limiter
from app.core.exceptions import AppException
from app.core.logging import get_logger, log_request, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("SaaSShadow Community Edition starting up")
    try:
        from app.plugins.plugin_loader import load_plugins
        load_plugins()
        logger.info("Plugins loaded")
    except Exception:
        logger.warning("Plugin loading skipped", exc_info=True)
    yield
    logger.info("SaaSShadow Community Edition shutting down")


app = FastAPI(
    title="SaaSShadow Community Edition",
    description=(
        "Open-source SaaS-to-SaaS monitoring API — detects integration risk, "
        "over-permissioned OAuth scopes, API token misuse, credential exposure, "
        "and cross-platform data flow risks. Produces composite 0-100 risk scores "
        "and executive-ready JSON + PDF reports."
    ),
    version="0.1.0-community",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow frontend (dev and production) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production to your frontend origin(s), e.g. ["https://app.yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(core_router)
app.include_router(scan_router)
app.include_router(scans_router)
app.include_router(connectors_router)
app.include_router(ispm_router)
app.include_router(dashboard_router)


@app.get("/meta/edition", tags=["Meta"], summary="Report the running edition")
def get_edition() -> dict:
    """Return the edition identifier and enabled connectors for this build."""
    return {
        "edition": settings.edition,
        "connectors": ["entra", "slack"],
    }


@app.middleware("http")
async def log_requests(request: Request, call_next):
    log_request(logger, request.method, request.url.path)
    response = await call_next(request)
    return response


def _app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning(
        "Application error: %s (status=%d)",
        exc.message,
        exc.status_code,
        extra={"detail": exc.detail},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.__class__.__name__,
                "message": exc.message,
                "detail": exc.detail,
            }
        },
    )


def _generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "InternalServerError",
                "message": "An unexpected error occurred",
                "detail": {},
            }
        },
    )


app.add_exception_handler(AppException, _app_exception_handler)
app.add_exception_handler(Exception, _generic_exception_handler)
