from fastapi import APIRouter
from .auth_router import router as auth_router
from .dashboard_router import router as dashboard_router
from .weapons_router import router as weapons_router
from .attachments_router import router as attachments_router
from .submissions_router import router as submissions_router
from .tickets_router import router as tickets_router
from .cms_router import router as cms_router
from .broadcast_router import router as broadcast_router
from .system_router import router as system_router
from .ws_router import router as ws_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(weapons_router)
api_router.include_router(attachments_router)
api_router.include_router(submissions_router)
api_router.include_router(tickets_router)
api_router.include_router(cms_router)
api_router.include_router(broadcast_router)
api_router.include_router(system_router)
api_router.include_router(ws_router)
