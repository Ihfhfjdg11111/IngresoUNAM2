"""
API Routes
"""
from fastapi import APIRouter

from .auth import router as auth_router
from .subjects import router as subjects_router
from .questions import router as questions_router
from .simulators import router as simulators_router
from .attempts import router as attempts_router
from .admin import router as admin_router
from .analytics import router as analytics_router
from .payments import router as payments_router
from .reports import router as reports_router
from .feedback import router as feedback_router


def create_api_router() -> APIRouter:
    """Create and configure the main API router"""
    api_router = APIRouter(prefix="/api")
    
    # Include all sub-routers
    api_router.include_router(auth_router)
    api_router.include_router(subjects_router)
    api_router.include_router(questions_router)
    api_router.include_router(simulators_router)
    api_router.include_router(attempts_router)
    api_router.include_router(admin_router)
    api_router.include_router(analytics_router)
    api_router.include_router(payments_router)
    api_router.include_router(reports_router)
    api_router.include_router(feedback_router)
    
    return api_router


__all__ = ["create_api_router"]
