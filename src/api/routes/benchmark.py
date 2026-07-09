# Created by Metrum AI for Solidigm

"""Benchmark API routes — Multi-User k6 orchestration."""

# pylint: disable=too-few-public-methods

import asyncio
import json
import logging
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.routes.sse import create_sse_response
from src.services.multi_user_benchmark_service import MAX_BENCHMARK_USERS, benchmark_service

logger = logging.getLogger(__name__)
router = APIRouter()


class StartBenchmarkRequest(BaseModel):
    """Request body for starting a multi-user benchmark run."""

    num_users: int = Field(ge=1, le=MAX_BENCHMARK_USERS, description=f"Number of concurrent simulated users (max {MAX_BENCHMARK_USERS})")
    context_mode: str = Field(
        default="long_context",
        pattern="^(quick|long_context)$",
        description="Context mode: 'quick' (5-10 games, ~30k tokens) or 'long_context' (8-16 games, ~180k tokens)",
    )


@router.post("/start")
async def start_benchmark(req: StartBenchmarkRequest):
    """Start a multi-user benchmark run."""
    try:
        run_id = await benchmark_service.start_run(req.num_users, req.context_mode)
        return {"run_id": run_id, "num_users": req.num_users, "status": "running"}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/active")
async def get_active_benchmark():
    """Check if a benchmark is currently running."""
    run = benchmark_service.get_active_run()
    if not run:
        return {"active": False}
    elapsed = time.perf_counter() - run.start_time
    return {
        "active": True,
        "run_id": run.run_id,
        "num_users": run.num_users,
        "elapsed": round(elapsed, 1),
        "context_mode": run.context_mode,
    }


@router.post("/active/stop")
async def stop_active_benchmark():
    """Stop whichever benchmark is currently running."""
    run = benchmark_service.get_active_run()
    if not run:
        raise HTTPException(status_code=404, detail="No active benchmark")
    await benchmark_service.stop_run(run.run_id)
    return {"run_id": run.run_id, "status": "stopping"}


@router.get("/{run_id}/flush_status")
async def get_flush_status(run_id: str):
    """Return the post-benchmark cache flush status."""
    run = benchmark_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "flush_status": run.flush_status}


@router.get("/{run_id}/events")
async def benchmark_events(run_id: str, request: Request):
    """SSE stream of real-time benchmark metrics."""
    run = benchmark_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def generate():
        last_count = 0
        last_emit_at = 0.0
        last_keepalive = time.time()
        last_prom = None
        last_prom_refresh_at = 0.0
        while True:
            if await request.is_disconnected():
                break

            total = run.completed_requests["baseline"] + run.completed_requests["lmcache"]
            is_done = run.status != "running"

            # Send an SSE comment as keepalive every 10s so nginx doesn't
            # cut the connection during quiet periods (e.g. deep queue wait).
            # 10s gives 30× headroom under nginx's 300s proxy_read_timeout.
            now = time.time()
            if now - last_keepalive >= 10:
                yield ": keepalive\n\n"
                last_keepalive = now

            if is_done:
                # k6 has exited but metric lines may still be draining from
                # the stdout buffer in _execute_k6 → _process_k6_metric.
                # Wait for the metric counts to stabilise before emitting
                # the "complete" event so the frontend sees final numbers.
                for _ in range(10):  # up to 5 seconds
                    await asyncio.sleep(0.5)
                    new_total = run.completed_requests["baseline"] + run.completed_requests["lmcache"]
                    if new_total == total:
                        break
                    total = new_total

            now = time.time()
            # Keep UI reactive even when no new completions arrive for a while
            # (e.g., long generations after all TTFT events have already landed).
            emit_interval = 1.0
            should_emit = total > last_count or is_done or (now - last_emit_at) >= emit_interval

            if should_emit:
                metrics = run.compute_aggregates()
                # Build per-target wall-time windows for accurate GPU power averaging
                per_target_wall = {}
                for target in ("baseline", "lmcache"):
                    t_start = run.first_request_wall.get(target)
                    t_end = run.last_request_complete_wall.get(target)
                    if t_start and t_end:
                        per_target_wall[target] = {"start": t_start, "end": t_end}
                # Prometheus range queries are expensive; refresh on completion
                # changes or at a slower cadence while waiting.
                prom_refresh_interval = 5.0
                should_refresh_prom = (
                    last_prom is None
                    or total > last_count
                    or is_done
                    or (now - last_prom_refresh_at) >= prom_refresh_interval
                )
                if should_refresh_prom:
                    last_prom = await benchmark_service.query_prometheus_vllm_metrics(
                        start_unix=run.start_wall_time,
                        end_unix=run.end_wall_time,
                        per_target_wall=per_target_wall or None,
                    )
                    last_prom_refresh_at = now
                prom = last_prom or {}
                metrics["prometheus"] = prom
                # Surface gpu_power_avg at top level for frontend highlight cards
                metrics["gpu_power_avg"] = prom.get("gpu_power_avg")
                metrics["type"] = "complete" if is_done else "progress"
                yield f"data: {json.dumps(metrics)}\n\n"
                last_count = total
                last_emit_at = now
                if is_done:
                    break

            await asyncio.sleep(0.5)

    return create_sse_response(generate())


@router.post("/{run_id}/stop")
async def stop_benchmark(run_id: str):
    """Stop a running benchmark."""
    run = benchmark_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    await benchmark_service.stop_run(run_id)
    return {"run_id": run_id, "status": "stopping"}


@router.get("/{run_id}/status")
async def benchmark_status(run_id: str):
    """One-shot status check (fallback if SSE disconnects)."""
    run = benchmark_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    metrics = run.compute_aggregates()
    per_target_wall = {}
    for target in ("baseline", "lmcache"):
        t_start = run.first_request_wall.get(target)
        t_end = run.last_request_complete_wall.get(target)
        if t_start and t_end:
            per_target_wall[target] = {"start": t_start, "end": t_end}
    prom = await benchmark_service.query_prometheus_vllm_metrics(
        start_unix=run.start_wall_time,
        end_unix=run.end_wall_time,
        per_target_wall=per_target_wall or None,
    )
    metrics["prometheus"] = prom
    metrics["gpu_power_avg"] = prom.get("gpu_power_avg")
    metrics["type"] = "complete" if run.status != "running" else "progress"
    return metrics
