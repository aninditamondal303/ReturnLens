"""
ShopSphere | Return Intelligence Lab — FastAPI application.

Run from the backend/ folder:
    uvicorn app.main:app --reload
API docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import analytics, data, system
from .core import settings
from .services.common import BadRequestError, NotFoundError
from .services.datastore import DataStore, DataUnavailableError

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s level=%(levelname)s logger=%(name)s %(message)s",
)
log = logging.getLogger("shopsphere.api")


def _error(status: int, code: str, message: str, detail=None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "detail": detail}})


def create_app(data_dir: Path | None = None) -> FastAPI:
    store = DataStore(data_dir or settings.DATA_DIR)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            store.load()
        except Exception:  # the API still starts; endpoints answer 503 with the reason
            log.exception("Initial data load failed")
        yield

    app = FastAPI(
        title="ShopSphere | Return Intelligence Lab API",
        version=settings.APP_VERSION,
        description=("E-commerce return risk and profit leakage analytics on SYNTHETIC data for a fictional company. "
                     "All monetary values are INR."),
        lifespan=lifespan,
    )
    app.state.store = store

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Row-Count"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        log.info("request method=%s path=%s status=%s duration_ms=%.1f", request.method, request.url.path,
                 response.status_code, (time.perf_counter() - start) * 1000)
        return response

    @app.exception_handler(BadRequestError)
    async def bad_request(_: Request, exc: BadRequestError):
        return _error(400, "bad_request", str(exc))

    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError):
        return _error(404, "not_found", str(exc).strip("'\""))

    @app.exception_handler(DataUnavailableError)
    async def unavailable(_: Request, exc: DataUnavailableError):
        return _error(503, "data_unavailable",
                      "Dataset is not loaded. Run `python scripts/generate_data.py` from the repository root, "
                      "then reload.", str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation(_: Request, exc: RequestValidationError):
        detail = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return _error(422, "invalid_parameters", "One or more request parameters are invalid.", detail)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return _error(500, "internal_error", "An unexpected error occurred. See the server log for details.")

    app.include_router(system.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(data.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"app": "ShopSphere | Return Intelligence Lab API", "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
