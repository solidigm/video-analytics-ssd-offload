# Created by Metrum AI for Solidigm

"""API Routes module."""

from fastapi import APIRouter

from src.api.routes.videos import router as videos_router
from src.api.routes.chat import router as chat_router
from src.api.routes.metrics import router as metrics_router
from src.api.routes.cache import router as cache_router
from src.api.routes.benchmark import router as benchmark_router

router = APIRouter()

router.include_router(videos_router, prefix="/videos", tags=["videos"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
router.include_router(cache_router, prefix="/cache", tags=["cache"])
router.include_router(benchmark_router, prefix="/benchmark", tags=["benchmark"])

__all__ = ["router"]
