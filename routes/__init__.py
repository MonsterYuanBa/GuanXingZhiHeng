"""jb666_for_front routes."""

from __future__ import annotations

from fastapi import APIRouter

from .auth import router as auth_router
from .history_analysis_transfer import router as history_analysis_router
from .joint_report_transfer import router as joint_report_router
from .posture_transfer import router as posture_router
from .profile_transfer import router as profile_router
from .reports import router as reports_router
from .test_mod import router as test_mod_router
from .tongue_transfer import router as tongue_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(profile_router)
router.include_router(reports_router)
router.include_router(test_mod_router)
router.include_router(posture_router)
router.include_router(tongue_router)
router.include_router(joint_report_router)
router.include_router(history_analysis_router)

__all__ = [
    'router',
    'auth_router',
    'profile_router',
    'reports_router',
    'test_mod_router',
    'posture_router',
    'tongue_router',
    'joint_report_router',
    'history_analysis_router',
]
