"""
FastAPI Main Application Entrypoint
Ox-Loadout Web Administration Backend
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from web.backend.app.config import CORS_ORIGINS, API_PREFIX
from web.backend.app.api import api_router
from core.database.database_adapter import get_database_adapter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database connection pool lifecycle"""
    db = get_database_adapter()
    # Initialize async connection pool
    try:
        if hasattr(db, "initialize"):
            await db.initialize()
        elif hasattr(db, "_pool") and hasattr(db._pool, "open"):
            await db._pool.open()
        print("✅ [Web Backend] PostgreSQL Connection Pool initialized.")
    except Exception as e:
        print(f"⚠️ [Web Backend] Note on DB pool startup: {e}")

    yield

    # Cleanup pool
    try:
        if hasattr(db, "close"):
            await db.close()
        print("🛑 [Web Backend] PostgreSQL Connection Pool closed gracefully.")
    except Exception as e:
        print(f"Error closing DB pool: {e}")


app = FastAPI(
    title="Ox-Loadout Web Admin API",
    description="RESTful Backend & WebSockets for Call of Duty Mobile Loadout Management Bot",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(api_router, prefix=API_PREFIX)


@app.get("/health", tags=["Health Check"])
async def root_health():
    return {"status": "ok", "service": "ox-loadout-web-api", "version": "2.0.0"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "خطای داخلی سرور رخ داده است",
            "error": str(exc),
        },
    )
