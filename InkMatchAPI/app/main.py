import time

import json

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal
from sqlalchemy import select, func
from app.services.audit_service import log_audit_event, resolve_source, should_skip_path
from app.models.user import User
from app.models.sketches import Sketch, Collection
from app.scripts.seed_app_demo import main as seed_app_demo
import app.models  # noqa: F401

UPLOADS_DIR = Path(__file__).resolve().parents[1] / 'uploads'


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    @app.middleware('http')
    async def audit_middleware(request: Request, call_next):
        path = request.url.path
        if should_skip_path(path):
            return await call_next(request)

        if not path.startswith(settings.api_v1_prefix):
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500
        response = None
        error = None
        body_params = None

        if 'application/json' in request.headers.get('content-type', ''):
            try:
                raw_body = await request.body()
                if raw_body:
                    parsed = json.loads(raw_body.decode('utf-8'))
                    if isinstance(parsed, (dict, list)):
                        body_params = parsed
            except Exception:
                body_params = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:  # noqa: BLE001
            error = exc
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            db = SessionLocal()
            try:
                endpoint = request.scope.get('endpoint')
                endpoint_name = endpoint.__name__ if endpoint is not None else None
                path_params = request.path_params if hasattr(request, 'path_params') else {}
                query_params = dict(request.query_params.items())
                log_audit_event(
                    db,
                    method=request.method,
                    path=path,
                    endpoint_name=endpoint_name,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    source=resolve_source(request.headers),
                    auth_header=request.headers.get('authorization'),
                    client_ip=request.client.host if request.client else None,
                    path_params=path_params,
                    query_params=query_params,
                    body_params=body_params,
                )
            except Exception:
                db.rollback()
            finally:
                db.close()

            if error is not None:
                # keep original stack/response behavior
                pass

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    
    # Mount uploads directory for local file serving
    if UPLOADS_DIR.exists():
        app.mount('/uploads', StaticFiles(directory=str(UPLOADS_DIR)), name='uploads')
    
    return app


app = create_app()


@app.on_event('startup')
def on_startup():
    if not settings.auto_seed_demo:
        return

    db = SessionLocal()
    try:
        users_count = db.scalar(select(func.count()).select_from(User)) or 0
        sketches_count = db.scalar(select(func.count()).select_from(Sketch)) or 0
        collections_count = db.scalar(select(func.count()).select_from(Collection)) or 0
    finally:
        db.close()

    if users_count >= 11 and sketches_count >= 20 and collections_count >= 20:
        return

    seed_app_demo()
