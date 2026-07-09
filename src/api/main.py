# Created by Metrum AI for Solidigm

"""
FastAPI Application - Sports Analytics Platform API.

Provides endpoints for:
- Video upload and processing
- American Football analytics agent execution
- Chat with LLM routing (LMCache vs Baseline)
- GPU and vLLM metrics
- Cache seeding for Season Archive and Cold Cache
"""

import os
import asyncio
import logging
import json
import uuid as _uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from src.api.routes import router
from src.db.database import init_db, close_db
from src.services.cache_seed_service import cache_seed_service
from src.services.context_refresh_service import context_refresh_service

# --- Structured JSON Logging ---
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get("-"),
        }
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.root.setLevel(logging.INFO)
logging.root.handlers = [_handler]
# Silence noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# vLLM server URLs for health monitoring
LMCACHE_URL = os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000/v1")
BASELINE_URL = os.getenv("LLM_BASELINE_URL", "http://vllm-baseline:8000/v1")
VLLM_HEALTH_POLL_INTERVAL = int(os.getenv("VLLM_HEALTH_POLL_INTERVAL", "30"))


async def seed_all_videos_background():
    """Background task to seed ALL videos at startup."""
    try:
        # Wait a bit for DB to be fully ready
        await asyncio.sleep(2)
        logger.info("Starting ALL videos background seeding...")
        results = await cache_seed_service.seed_all()
        total = results.get("total", {})
        logger.info(
            "ALL videos seeded: %s videos, %s tokens",
            total.get("videos_loaded", 0),
            total.get("total_tokens", 0),
        )
        logger.info(
            "  - Season Archive: %s videos",
            results.get("season_archive", {}).get("videos_loaded", 0),
        )
        logger.info(
            "  - Cold Cache: %s videos",
            results.get("cold_cache", {}).get("videos_loaded", 0),
        )
        logger.info(
            "  - Warm Cache: %s videos",
            results.get("warm_cache", {}).get("videos_loaded", 0),
        )
        warmup = results.get("lmcache_warmup", {})
        if warmup:
            logger.info(
                "LMCache startup warmup (Season Archive only): success=%s long_context=%s",
                warmup.get("success"),
                warmup.get("long_context", {}).get("success"),
            )

        # Flush baseline and LMCache KV caches with book text after seeding
        context_refresh_service.load_books()
        logger.info("Flushing baseline and LMCache caches after seeding...")
        baseline_ok, lmcache_ok = await context_refresh_service.flush_baseline_and_lmcache(wait_for_server=True)
        if not baseline_ok:
            logger.warning("Startup baseline cache flush did not complete successfully")
        if not lmcache_ok:
            logger.warning("Startup LMCache cache flush did not complete successfully")
    except (RuntimeError, OSError, httpx.HTTPError, ValueError, TypeError) as e:
        logger.error("Background seeding error: %s", e)


async def _check_vllm_health(url: str) -> bool:
    """Check if a vLLM server is reachable."""
    base = url.rstrip("/")
    models_url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(models_url)
            return resp.status_code == 200
    except (httpx.HTTPError, OSError, ValueError, TypeError):
        return False


async def vllm_health_monitor():
    """Background task that detects vLLM server restarts and re-triggers warmup.

    Polls both LMCache and Baseline vLLM servers periodically. When a server
    transitions from unhealthy → healthy (indicating a restart), re-runs the
    LMCache warmup and/or baseline flush so the first user query is fast.
    """
    # Wait for initial seeding to finish before starting the monitor
    await asyncio.sleep(60)
    logger.info("vLLM health monitor started (poll every %ss)", VLLM_HEALTH_POLL_INTERVAL)

    lmcache_was_healthy = True  # Assume healthy after startup seeding
    baseline_was_healthy = True

    while True:
        try:
            await asyncio.sleep(VLLM_HEALTH_POLL_INTERVAL)

            lmcache_healthy = await _check_vllm_health(LMCACHE_URL)
            baseline_healthy = await _check_vllm_health(BASELINE_URL)

            # Detect LMCache restart: was down, now up
            if lmcache_healthy and not lmcache_was_healthy:
                logger.warning("LMCache vLLM server restart detected! Re-running warmup...")
                try:
                    result = await cache_seed_service.warmup_startup_scenarios()
                    logger.info(
                        "Post-restart LMCache warmup: success=%s",
                        result.get("success"),
                    )
                except (RuntimeError, OSError, httpx.HTTPError, ValueError, TypeError) as e:
                    logger.error("Post-restart LMCache warmup failed: %s", e)

            # Detect Baseline restart: was down, now up
            if baseline_healthy and not baseline_was_healthy:
                logger.warning("Baseline vLLM server restart detected! Re-flushing baseline and LMCache caches...")
                try:
                    context_refresh_service.ensure_books_loaded()
                    baseline_ok, lmcache_ok = await context_refresh_service.flush_baseline_and_lmcache()
                    logger.info(
                        "Post-restart flush: baseline=%s lmcache=%s",
                        baseline_ok,
                        lmcache_ok,
                    )
                except (RuntimeError, OSError, httpx.HTTPError, ValueError, TypeError) as e:
                    logger.error("Post-restart cache flush failed: %s", e)

            # Log state transitions for debugging
            if not lmcache_healthy and lmcache_was_healthy:
                logger.warning("LMCache vLLM server went DOWN")
            if not baseline_healthy and baseline_was_healthy:
                logger.warning("Baseline vLLM server went DOWN")

            lmcache_was_healthy = lmcache_healthy
            baseline_was_healthy = baseline_healthy

        except asyncio.CancelledError:
            logger.info("vLLM health monitor cancelled")
            break
        except (RuntimeError, OSError, httpx.HTTPError, ValueError, TypeError) as e:
            logger.error("vLLM health monitor error: %s", e)
            await asyncio.sleep(VLLM_HEALTH_POLL_INTERVAL)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting Sports Analytics API")

    base_path = os.getenv("DATA_PATH", "/data")
    data_dirs = [
        f"{base_path}/videos",
        f"{base_path}/frames",
        f"{base_path}/analysis",
        os.getenv("LOGS_PATH", "/logs"),
    ]
    for d in data_dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

    await init_db()

    # Load cache seed config
    cache_seed_service.load_config()

    # Start ALL videos seeding in background
    auto_seed = os.getenv("AUTO_SEED_ON_STARTUP", "true").lower() == "true"
    if auto_seed:
        asyncio.create_task(seed_all_videos_background())

    # Start vLLM health monitor to detect restarts and re-warmup
    monitor_task = asyncio.create_task(vllm_health_monitor())

    yield

    monitor_task.cancel()
    await close_db()
    logger.info("Shutting down Sports Analytics API")


class RequestIDMiddleware(BaseHTTPMiddleware):  # pylint: disable=too-few-public-methods
    """Inject/propagate X-Request-ID header and set it in the request_id context var."""

    async def dispatch(self, request: StarletteRequest, call_next):
        """Set a per-request correlation id on logs and response headers."""
        req_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        token = request_id_var.set(req_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_var.reset(token)


app = FastAPI(
    title="Sports Analytics API",
    description="AI-powered sports video analysis with KV cache offload comparison",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "sports-analytics-api",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Sports Analytics API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "videos": "/api/v1/videos",
            "chat": "/api/v1/chat",
            "metrics": "/api/v1/metrics",
            "cache": "/api/v1/cache",
        },
    }
