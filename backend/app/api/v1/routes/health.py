import time

from fastapi import APIRouter

from settings import get_settings

router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()
start_time = time.time()


@router.get("", summary="Health check")
def health_check() -> dict:
    uptime_seconds = int(time.time() - start_time)
    return {
        "status": "ok",
        "version": settings.app_version,
        "uptime": uptime_seconds,
        "environment": settings.environment,
    }
