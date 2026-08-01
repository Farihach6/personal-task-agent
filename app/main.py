"""FastAPI application entrypoint.

Creates the app, configures logging, initializes the database, registers
exception handlers and routers, and serves the static frontend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.health_router import router as health_router
from app.api.notes_router import router as notes_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import configure_logging, get_logger
from app.database.base import init_db

settings = get_settings()

configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Application factory: builds and configures the FastAPI instance."""
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    # CORS is permissive here since the frontend is served by this same app
    # and there is no external client yet; tighten if a separate origin is added.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(notes_router, prefix="/api/v1")

    # Serve the static frontend dashboard.
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

    @app.on_event("startup")
    def on_startup() -> None:
        logger.info("Starting %s (env=%s)", settings.app_name, settings.app_env)
        init_db()

    return app


app = create_app()