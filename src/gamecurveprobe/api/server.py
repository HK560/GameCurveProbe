from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from gamecurveprobe.api.routes import router
from gamecurveprobe.context import AppContext
from gamecurveprobe.errors import DomainError


def create_app(
    context_factory: Callable[[], AppContext],
    static_dir: Path | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.context = context_factory()
        try:
            yield
        finally:
            app.state.context.close()

    app = FastAPI(title="GameCurveProbe Web API", version="2.0.0", lifespan=lifespan)

    # CORS support for localhost development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:*", "http://localhost:*", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        status_code = 400
        if exc.code == "RESOURCE_BUSY":
            status_code = 409
        elif exc.code in {"JOB_NOT_FOUND", "BACKEND_NOT_FOUND"}:
            status_code = 404
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail), "details": {}}},
        )

    app.include_router(router)

    # Static assets for Vue frontend
    if static_dir and static_dir.exists():
        index_file = static_dir / "index.html"
        if index_file.exists():
            app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

            @app.get("/{full_path:path}", include_in_schema=False)
            async def serve_spa(full_path: str):
                requested_path = static_dir / full_path
                if full_path and requested_path.is_file():
                    return FileResponse(requested_path)
                return FileResponse(index_file)

    return app
