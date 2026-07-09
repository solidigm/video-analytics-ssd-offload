# Created by Metrum AI for Solidigm

"""Cache API Routes - Endpoints for cache seeding operations."""

# pylint: disable=too-few-public-methods

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from src.services.cache_seed_service import cache_seed_service, SeedResult
from src.services.context_refresh_service import context_refresh_service

logger = logging.getLogger(__name__)
router = APIRouter()


class SeedRequest(BaseModel):
    """Request to seed specific games."""

    game_ids: Optional[List[str]] = None


class CacheStatusResponse(BaseModel):
    """Cache status response."""

    season_archive_loaded: bool
    season_archive_count: int
    cold_cache_loaded: bool
    cold_cache_count: int
    warm_cache_loaded: bool
    warm_cache_count: int
    last_seed_time: Optional[str]
    total_context_tokens: int
    available_videos: list


@router.post("/seed/season-archive", response_model=SeedResult)
async def seed_season_archive(_background_tasks: BackgroundTasks):
    """
    Seed Season Archive (2024 games) into cache.

    This loads the 2024 season games from context.json files into memory
    and creates video records in the database for them.
    """
    try:
        logger.info("Starting Season Archive seeding")
        result = await cache_seed_service.seed_season_archive()

        return result
    except Exception as e:
        logger.error("Season Archive seeding failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/seed/cold-cache", response_model=SeedResult)
async def seed_cold_cache(request: Optional[SeedRequest] = None):
    """
    Seed Cold Cache (2025 Recent Games) into cache.

    This loads the recent games from context.json files when user clicks
    on "Recent Games" scenario.
    """
    try:
        game_ids = request.game_ids if request else None
        logger.info("Starting Cold Cache seeding: %s", game_ids or "all")
        result = await cache_seed_service.seed_cold_cache(game_ids)

        return result
    except Exception as e:
        logger.error("Cold Cache seeding failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/seed/warm-cache", response_model=SeedResult)
async def seed_warm_cache():
    """
    Seed Warm Cache (small context videos) into cache.

    This loads the 2 warm cache videos from context.json files.
    """
    try:
        logger.info("Starting Warm Cache seeding")
        result = await cache_seed_service.seed_warm_cache()

        return result
    except Exception as e:
        logger.error("Warm Cache seeding failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/seed/all")
async def seed_all_videos():
    """
    Seed ALL videos (season_archive + cold_cache + warm_cache) into cache.

    This is what runs at startup automatically.
    """
    try:
        logger.info("Starting ALL videos seeding")
        results = await cache_seed_service.seed_all()
        return results
    except Exception as e:
        logger.error("ALL videos seeding failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/status", response_model=CacheStatusResponse)
async def get_cache_status():
    """Get current cache seeding status."""
    try:
        status = cache_seed_service.get_cache_status()
        available_videos = cache_seed_service.get_available_videos()

        return CacheStatusResponse(
            season_archive_loaded=status.season_archive_loaded,
            season_archive_count=status.season_archive_count,
            cold_cache_loaded=status.cold_cache_loaded,
            cold_cache_count=status.cold_cache_count,
            warm_cache_loaded=status.warm_cache_loaded,
            warm_cache_count=status.warm_cache_count,
            last_seed_time=status.last_seed_time,
            total_context_tokens=status.total_context_tokens,
            available_videos=available_videos,
        )
    except Exception as e:
        logger.error("Failed to get cache status: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/videos")
async def list_cached_videos():
    """List all available videos from cache config."""
    try:
        videos = cache_seed_service.get_available_videos()
        return {
            "videos": videos,
            "count": len(videos),
        }
    except Exception as e:
        logger.error("Failed to list cached videos: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/context/{video_id}")
async def get_video_context(video_id: str):
    """Get loaded context for a specific video."""
    try:
        context = cache_seed_service.get_context(video_id)
        if not context:
            raise HTTPException(status_code=404, detail=f"Context not found for video: {video_id}")

        return {
            "video_id": video_id,
            "context_length": len(context),
            "context_preview": context[:500] + "..." if len(context) > 500 else context,
            "estimated_tokens": len(context) // 4,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get context: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/flush-baseline")
async def flush_baseline_cache():
    """
    Flush baseline and LMCache KV caches by sending a large book text to each.

    Sends a book to both baseline and LMCache vLLM instances to evict cached
    game context so the next queries compute from scratch (baseline) or reload
    from SSD (LMCache).
    """
    logger.info("Flush requested (baseline + LMCache)")
    try:
        if not context_refresh_service.ensure_books_loaded():
            logger.error("No flush books loaded. Ensure DATA_PATH/context contains .txt files.")
            raise HTTPException(
                status_code=503,
                detail="No flush books loaded. Ensure DATA_PATH/context contains .txt files.",
            )
        logger.info("Flushing baseline and LMCache caches...")
        baseline_ok, lmcache_ok = await context_refresh_service.flush_baseline_and_lmcache()
        logger.info("Flush complete: baseline=%s lmcache=%s", baseline_ok, lmcache_ok)
        if not baseline_ok:
            raise HTTPException(status_code=503, detail="Baseline cache flush failed")
        if not lmcache_ok:
            logger.warning("LMCache cache flush failed (baseline flushed successfully)")
        return {
            "success": True,
            "message": "Baseline and LMCache caches flushed",
            "baseline_flushed": baseline_ok,
            "lmcache_flushed": lmcache_ok,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cache flush failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
