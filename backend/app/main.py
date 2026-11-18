import ipaddress
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.context import RequestContext, reset_request_context, set_request_context
from app.core.errors import register_error_handlers
from app.core.rate_limit import limiter
from app.db.session import SessionLocal
from app.services.storage_service import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("papasana")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        get_storage().ensure_bucket(settings.bucket_profiles)
    except Exception:
        log.warning("MinIO no disponible al iniciar; los buckets se crearán al primer uso.")
    yield


app = FastAPI(
    title="PapaSana AP-01 API",
    description=(
        "API del sistema de apoyo a la decisión para la detección por síntomas del tizón tardío de la papa. "
        "Herramienta de investigación: no constituye un diagnóstico definitivo."
    ),
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.state.limiter = limiter
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def _valid_ip(value: str | None) -> str | None:
    try:
        return str(ipaddress.ip_address(value)) if value else None
    except ValueError:
        return None


@app.middleware("http")
async def request_context(request: Request, call_next):
    trace_id = uuid.uuid4().hex[:16]
    token = set_request_context(RequestContext(
        ip=_valid_ip(request.client.host if request.client else None),
        user_agent=request.headers.get("user-agent"),
        endpoint=request.url.path[:255],
        method=request.method,
        trace_id=trace_id,
    ))
    try:
        response = await call_next(request)
    finally:
        reset_request_context(token)
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


app.include_router(api_router)


@app.get("/api/health", tags=["Sistema"], summary="Estado del servicio")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "app": settings.app_name}
