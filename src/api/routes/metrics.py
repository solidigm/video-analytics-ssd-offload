# Created by Metrum AI for Solidigm

"""Metrics API Routes."""

import os
import re
import time
import asyncio
import logging
import math
import subprocess

import httpx
from fastapi import APIRouter
from sqlalchemy import select, func

from src.db.database import get_db_context
from src.db.models import Telemetry

logger = logging.getLogger(__name__)
router = APIRouter()

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
# For metrics, use internal Docker URLs (without /v1 suffix)
LMCACHE_URL = os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000/v1").replace("/v1", "")
BASELINE_URL = os.getenv("LLM_BASELINE_URL", "http://vllm-baseline:8000/v1").replace("/v1", "")
VLM_URL = os.getenv("VLM_API_URL", "http://vllm-vlm:8000/v1").replace("/v1", "")

# Track previous counter snapshots to compute live token/request throughput.
_vllm_counter_snapshots: dict[str, dict[str, float]] = {}
_vllm_snapshot_lock = asyncio.Lock()

_METRIC_VALUE_PATTERN = r"([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)"
_VLLM_RATE_WINDOW = os.getenv("VLLM_PROM_RATE_WINDOW", "1m")
_VLLM_JOBS_FILTER = '{job=~"vllm-(baseline|lmcache|vlm)"}'
_SERVICE_TO_PROM_JOB = {
    "baseline": "vllm-baseline",
    "lmcache": "vllm-lmcache",
    "vlm": "vllm-vlm",
}
_PROM_JOB_TO_SERVICE = {v: k for k, v in _SERVICE_TO_PROM_JOB.items()}


def _extract_metric(text: str, metric_name: str) -> float:
    """Extract a single labeled metric value from vLLM Prometheus text."""
    pattern = rf"{re.escape(metric_name)}(?:\{{[^}}]*\}})?\s+{_METRIC_VALUE_PATTERN}"
    match = re.search(pattern, text)
    return float(match.group(1)) if match else 0.0


def _extract_metric_sum(text: str, metric_name: str) -> float:
    """Sum all matching metric values (used for counters split by labels)."""
    pattern = rf"{re.escape(metric_name)}(?:\{{[^}}]*\}})?\s+{_METRIC_VALUE_PATTERN}"
    matches = re.findall(pattern, text)
    return sum(float(value) for value in matches) if matches else 0.0


def _safe_float(value) -> float:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else 0.0
    except (TypeError, ValueError):
        return 0.0


async def _query_prometheus_vector_map(
    client: httpx.AsyncClient,
    promql: str,
) -> dict[str, float]:
    values = {name: 0.0 for name in _SERVICE_TO_PROM_JOB}
    resp = await client.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": promql},
    )
    result = resp.json().get("data", {}).get("result", [])
    for series in result:
        job = series.get("metric", {}).get("job")
        name = _PROM_JOB_TO_SERVICE.get(job)
        if not name:
            continue
        point = series.get("value")
        if point and len(point) >= 2:
            values[name] = _safe_float(point[1])
    return values


async def _attach_prometheus_rates(  # pylint: disable=too-many-locals
    metrics_by_name: dict[str, dict],
) -> bool:
    """Attach PromQL-backed live rates and latency means.

    Returns True if Prometheus queries succeeded for at least one metric.
    """
    for metrics in metrics_by_name.values():
        metrics.setdefault("prompt_tps", 0.0)
        metrics.setdefault("generation_tps", 0.0)
        metrics.setdefault("requests_per_s", 0.0)
        metrics.setdefault("ttft_seconds", 0.0)
        metrics.setdefault("tpot_ms", 0.0)

    w = _VLLM_RATE_WINDOW
    f = _VLLM_JOBS_FILTER
    queries = {
        "prompt_tps": f"sum by(job) (rate(vllm:prompt_tokens_total{f}[{w}]))",
        "generation_tps": f"sum by(job) (rate(vllm:generation_tokens_total{f}[{w}]))",
        "requests_per_s": f"sum by(job) (rate(vllm:request_success_total{f}[{w}]))",
        "ttft_seconds": f"sum by(job) (rate(vllm:time_to_first_token_seconds_sum{f}[{w}])) " f"/ clamp_min(sum by(job) (rate(vllm:time_to_first_token_seconds_count{f}[{w}])), 1e-9)",
        "tpot_ms": f"1000 * sum by(job) (rate(vllm:request_time_per_output_token_seconds_sum{f}[{w}])) "
        f"/ clamp_min(sum by(job) (rate(vllm:request_time_per_output_token_seconds_count{f}[{w}])), 1e-9)",
        "prefix_hits_per_s": f"sum by(job) (rate(vllm:prefix_cache_hits_total{f}[{w}]))",
        "prefix_queries_per_s": f"sum by(job) (rate(vllm:prefix_cache_queries_total{f}[{w}]))",
        "external_hits_per_s": f"sum by(job) (rate(vllm:external_prefix_cache_hits_total{f}[{w}]))",
        "external_queries_per_s": f"sum by(job) (rate(vllm:external_prefix_cache_queries_total{f}[{w}]))",
        "mm_hits_per_s": f"sum by(job) (rate(vllm:mm_cache_hits_total{f}[{w}]))",
        "mm_queries_per_s": f"sum by(job) (rate(vllm:mm_cache_queries_total{f}[{w}]))",
    }

    results: dict[str, dict[str, float]] = {}
    success_count = 0

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            for metric_name, promql in queries.items():
                try:
                    results[metric_name] = await _query_prometheus_vector_map(client, promql)
                    success_count += 1
                except (httpx.HTTPError, ValueError, TypeError, KeyError) as e:
                    logger.debug("Prometheus metric query failed (%s): %s", metric_name, e)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as e:
        logger.debug("Prometheus query batch failed: %s", e)
        return False

    if success_count == 0:
        return False

    for name, metrics in metrics_by_name.items():
        metrics["prompt_tps"] = round(results.get("prompt_tps", {}).get(name, 0.0), 2)
        metrics["generation_tps"] = round(results.get("generation_tps", {}).get(name, 0.0), 2)
        metrics["requests_per_s"] = round(results.get("requests_per_s", {}).get(name, 0.0), 3)
        metrics["ttft_seconds"] = round(results.get("ttft_seconds", {}).get(name, 0.0), 4)
        metrics["tpot_ms"] = round(results.get("tpot_ms", {}).get(name, 0.0), 2)

        prefix_qps = results.get("prefix_queries_per_s", {}).get(name, 0.0)
        prefix_hps = results.get("prefix_hits_per_s", {}).get(name, 0.0)
        external_qps = results.get("external_queries_per_s", {}).get(name, 0.0)
        external_hps = results.get("external_hits_per_s", {}).get(name, 0.0)
        mm_qps = results.get("mm_queries_per_s", {}).get(name, 0.0)
        mm_hps = results.get("mm_hits_per_s", {}).get(name, 0.0)

        if prefix_qps > 0:
            metrics["prefix_cache_hit_rate_pct"] = round((prefix_hps / prefix_qps) * 100, 2)
        if external_qps > 0:
            metrics["external_cache_hit_rate_pct"] = round((external_hps / external_qps) * 100, 2)
        if mm_qps > 0:
            metrics["mm_cache_hit_rate_pct"] = round((mm_hps / mm_qps) * 100, 2)

        total_qps = prefix_qps + external_qps + mm_qps
        if total_qps > 0:
            total_hps = prefix_hps + external_hps + mm_hps
            cache_hit_rate = round((total_hps / total_qps) * 100, 2)
            metrics["cache_hit_rate_pct"] = cache_hit_rate
            metrics["cache_hit_rate"] = cache_hit_rate

    return True


async def _attach_live_rates(metrics: dict) -> None:
    """Attach live per-second rates derived from cumulative counters."""
    if not metrics.get("available"):
        metrics["prompt_tps"] = 0.0
        metrics["generation_tps"] = 0.0
        metrics["requests_per_s"] = 0.0
        return

    name = metrics["name"]
    now = time.time()

    async with _vllm_snapshot_lock:
        prev = _vllm_counter_snapshots.get(name)

        prompt_tps = 0.0
        generation_tps = 0.0
        requests_per_s = 0.0

        if prev:
            elapsed = now - prev.get("timestamp", now)
            if elapsed > 0:
                prompt_delta = metrics["prompt_tokens"] - prev.get("prompt_tokens", 0.0)
                generation_delta = metrics["generation_tokens"] - prev.get("generation_tokens", 0.0)
                requests_delta = metrics["requests_completed"] - prev.get("requests_completed", 0.0)

                # Handle counter resets after server restarts.
                prompt_tps = max(prompt_delta, 0.0) / elapsed
                generation_tps = max(generation_delta, 0.0) / elapsed
                requests_per_s = max(requests_delta, 0.0) / elapsed

        metrics["prompt_tps"] = round(prompt_tps, 2)
        metrics["generation_tps"] = round(generation_tps, 2)
        metrics["requests_per_s"] = round(requests_per_s, 3)

        _vllm_counter_snapshots[name] = {
            "timestamp": now,
            "prompt_tokens": metrics["prompt_tokens"],
            "generation_tokens": metrics["generation_tokens"],
            "requests_completed": metrics["requests_completed"],
        }


@router.get("/gpu")
async def get_gpu_metrics():  # pylint: disable=too-many-locals,too-many-branches
    """Get GPU metrics from DCGM exporter via Prometheus, with nvidia-smi fallback."""
    queries = {
        "power": "DCGM_FI_DEV_POWER_USAGE",
        "temp": "DCGM_FI_DEV_GPU_TEMP",
        "mem_used": "DCGM_FI_DEV_FB_USED",
        "util": "DCGM_FI_DEV_GPU_UTIL",
    }

    gpu_names = [
        "GPU 0 - LMCache LLM",
        "GPU 1 - Baseline LLM",
        "GPU 2 - VLM",
        "GPU 3 - Unused",
    ]

    gpu_metrics = []
    source = "dcgm-exporter"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            results = {}
            for key, query in queries.items():
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                results[key] = resp.json().get("data", {}).get("result", [])

            for i in range(4):
                gpu = {
                    "index": i,
                    "name": gpu_names[i] if i < len(gpu_names) else f"GPU {i}",
                    "power": 0,
                    "temp": 0,
                    "mem_used_gb": 0,
                    "mem_total_gb": 98,
                    "util": 0,
                }

                for item in results.get("power", []):
                    if item.get("metric", {}).get("gpu", "") == str(i):
                        gpu["power"] = round(float(item["value"][1]), 1)
                        break

                for item in results.get("temp", []):
                    if item.get("metric", {}).get("gpu", "") == str(i):
                        gpu["temp"] = round(float(item["value"][1]), 1)
                        break

                for item in results.get("mem_used", []):
                    if item.get("metric", {}).get("gpu", "") == str(i):
                        gpu["mem_used_gb"] = round(float(item["value"][1]) / 1024, 2)
                        break

                for item in results.get("util", []):
                    if item.get("metric", {}).get("gpu", "") == str(i):
                        gpu["util"] = round(float(item["value"][1]), 1)
                        break

                gpu_metrics.append(gpu)

    except (httpx.HTTPError, ValueError, TypeError, KeyError) as e:
        logger.warning("Failed to fetch GPU metrics from Prometheus: %s", e)
        source = "nvidia-smi"

    # If utilization is all zeros, try nvidia-smi fallback
    if all(g["util"] == 0 for g in gpu_metrics) or not gpu_metrics:
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,power.draw,temperature.gpu,memory.used,memory.total,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                nvidia_metrics = []
                for line in lines:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 7:
                        idx = int(parts[0])
                        nvidia_metrics.append(
                            {
                                "index": idx,
                                "name": gpu_names[idx] if idx < len(gpu_names) else parts[1],
                                "power": round(float(parts[2]), 1) if parts[2] != "[N/A]" else 0,
                                "temp": round(float(parts[3]), 1) if parts[3] != "[N/A]" else 0,
                                "mem_used_gb": (round(float(parts[4]) / 1024, 2) if parts[4] != "[N/A]" else 0),
                                "mem_total_gb": (round(float(parts[5]) / 1024, 2) if parts[5] != "[N/A]" else 98),
                                "util": round(float(parts[6]), 1) if parts[6] != "[N/A]" else 0,
                            }
                        )
                if nvidia_metrics:
                    gpu_metrics = nvidia_metrics
                    source = "nvidia-smi"
        except (OSError, ValueError, IndexError, subprocess.SubprocessError) as e2:
            logger.warning("Failed to fetch GPU metrics from nvidia-smi: %s", e2)

    if not gpu_metrics:
        gpu_metrics = [
            {
                "index": 0,
                "name": "GPU 0 - LMCache LLM",
                "power": 0,
                "temp": 0,
                "mem_used_gb": 0,
                "mem_total_gb": 98,
                "util": 0,
            },
            {
                "index": 1,
                "name": "GPU 1 - Baseline LLM",
                "power": 0,
                "temp": 0,
                "mem_used_gb": 0,
                "mem_total_gb": 98,
                "util": 0,
            },
            {
                "index": 2,
                "name": "GPU 2 - VLM",
                "power": 0,
                "temp": 0,
                "mem_used_gb": 0,
                "mem_total_gb": 98,
                "util": 0,
            },
            {
                "index": 3,
                "name": "GPU 3 - Unused",
                "power": 0,
                "temp": 0,
                "mem_used_gb": 0,
                "mem_total_gb": 98,
                "util": 0,
            },
        ]
        source = "fallback"

    return {"gpus": gpu_metrics, "source": source}


@router.get("/vllm")
async def get_vllm_metrics():
    """Get vLLM metrics including cache hit rates."""

    async def parse_metrics(url: str, name: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{url}/metrics")
                text = resp.text

                metrics = {"name": name, "available": True}

                metrics["prefix_cache_queries"] = _extract_metric_sum(text, "vllm:prefix_cache_queries_total")
                metrics["prefix_cache_hits"] = _extract_metric_sum(text, "vllm:prefix_cache_hits_total")
                metrics["external_cache_queries"] = _extract_metric_sum(text, "vllm:external_prefix_cache_queries_total")
                metrics["external_cache_hits"] = _extract_metric_sum(text, "vllm:external_prefix_cache_hits_total")
                metrics["mm_cache_queries"] = _extract_metric_sum(text, "vllm:mm_cache_queries_total")
                metrics["mm_cache_hits"] = _extract_metric_sum(text, "vllm:mm_cache_hits_total")

                kv_cache_usage = _extract_metric(text, "vllm:kv_cache_usage_perc")
                metrics["kv_cache_usage"] = kv_cache_usage  # 0-1 ratio (backward compatible)
                metrics["kv_cache_usage_pct"] = round(kv_cache_usage * 100, 2)

                metrics["prompt_tokens"] = _extract_metric_sum(text, "vllm:prompt_tokens_total")
                metrics["generation_tokens"] = _extract_metric_sum(text, "vllm:generation_tokens_total")
                metrics["requests_completed"] = _extract_metric_sum(text, "vllm:request_success_total")
                metrics["num_requests_running"] = _extract_metric_sum(text, "vllm:num_requests_running")
                metrics["num_requests_waiting"] = _extract_metric_sum(text, "vllm:num_requests_waiting")

                total_queries = metrics["prefix_cache_queries"] + metrics["external_cache_queries"] + metrics["mm_cache_queries"]
                total_hits = metrics["prefix_cache_hits"] + metrics["external_cache_hits"] + metrics["mm_cache_hits"]
                cache_hit_rate = round((total_hits / total_queries * 100), 2) if total_queries > 0 else 0.0
                metrics["cache_hit_rate_pct"] = cache_hit_rate
                metrics["cache_hit_rate"] = cache_hit_rate  # backward compatible alias

                # Per-cache-type hit rates for more meaningful per-service display
                pq = metrics["prefix_cache_queries"]
                metrics["prefix_cache_hit_rate_pct"] = round((metrics["prefix_cache_hits"] / pq * 100), 2) if pq > 0 else 0.0
                eq = metrics["external_cache_queries"]
                metrics["external_cache_hit_rate_pct"] = round((metrics["external_cache_hits"] / eq * 100), 2) if eq > 0 else 0.0
                mq = metrics["mm_cache_queries"]
                metrics["mm_cache_hit_rate_pct"] = round((metrics["mm_cache_hits"] / mq * 100), 2) if mq > 0 else 0.0

                return metrics

        except (httpx.HTTPError, ValueError, TypeError, KeyError) as e:
            logger.warning("Failed to fetch vLLM metrics from %s: %s", url, e)
            return {"name": name, "available": False, "error": str(e)}

    lmcache_metrics, baseline_metrics, vlm_metrics = await asyncio.gather(
        parse_metrics(LMCACHE_URL, "lmcache"),
        parse_metrics(BASELINE_URL, "baseline"),
        parse_metrics(VLM_URL, "vlm"),
    )

    metrics_by_name = {
        "lmcache": lmcache_metrics,
        "baseline": baseline_metrics,
        "vlm": vlm_metrics,
    }
    prom_rates_ok = await _attach_prometheus_rates(metrics_by_name)
    if not prom_rates_ok:
        await asyncio.gather(
            _attach_live_rates(lmcache_metrics),
            _attach_live_rates(baseline_metrics),
            _attach_live_rates(vlm_metrics),
        )

    return {
        "lmcache": lmcache_metrics,
        "baseline": baseline_metrics,
        "vlm": vlm_metrics,
    }


@router.get("/telemetry")
async def get_telemetry_summary():
    """Get telemetry summary from database."""
    async with get_db_context() as session:
        result = await session.execute(
            select(
                Telemetry.operation_type,
                func.count(Telemetry.id).label("count"),
                func.avg(Telemetry.duration_ms).label("avg_duration_ms"),
                func.sum(Telemetry.duration_ms).label("total_duration_ms"),
            ).group_by(Telemetry.operation_type)
        )
        rows = result.all()

        summary = {}
        for row in rows:
            summary[row.operation_type or "unknown"] = {
                "count": row.count,
                "avg_duration_ms": round(float(row.avg_duration_ms or 0), 2),
                "total_duration_ms": round(float(row.total_duration_ms or 0), 2),
            }

        return {"telemetry": summary}


@router.get("/ssd")
async def get_ssd_metrics():
    """
    Get SSD metrics for the LMCache KV cache drive from Prometheus/node-exporter.
    Uses rate() queries for live throughput.
    """
    # LMCache KV cache drive - TLC NVMe (mounted at /mnt/ssd)
    lmcache_device = os.getenv("LMCACHE_SSD_DEVICE", "nvme0n1")

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            # Prometheus queries for disk metrics
            queries = {
                # Rate queries for live throughput (bytes/sec)
                "read_bytes_rate": f'rate(node_disk_read_bytes_total{{device="{lmcache_device}"}}[1m])',
                "write_bytes_rate": f'rate(node_disk_written_bytes_total{{device="{lmcache_device}"}}[1m])',
                # Rate queries for IOPS
                "read_iops": f'rate(node_disk_reads_completed_total{{device="{lmcache_device}"}}[1m])',
                "write_iops": f'rate(node_disk_writes_completed_total{{device="{lmcache_device}"}}[1m])',
                # Cumulative totals
                "read_bytes_total": f'node_disk_read_bytes_total{{device="{lmcache_device}"}}',
                "write_bytes_total": f'node_disk_written_bytes_total{{device="{lmcache_device}"}}',
                # Latency - use rate() for recent performance (time rate / ops rate = avg latency)
                "read_time_rate": f'rate(node_disk_read_time_seconds_total{{device="{lmcache_device}"}}[1m])',
                "write_time_rate": f'rate(node_disk_write_time_seconds_total{{device="{lmcache_device}"}}[1m])',
                # IO in progress
                "io_now": f'node_disk_io_now{{device="{lmcache_device}"}}',
            }

            results = {}
            for key, query in queries.items():
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json().get("data", {}).get("result", [])
                results[key] = float(data[0]["value"][1]) if data else 0

            # Convert bytes/sec to MB/s
            read_mbps = results["read_bytes_rate"] / (1024 * 1024)
            write_mbps = results["write_bytes_rate"] / (1024 * 1024)

            # Cumulative totals in GB
            total_read_gb = results["read_bytes_total"] / (1024**3)
            total_write_gb = results["write_bytes_total"] / (1024**3)

            # Average latency over last 1 minute (rate of time / rate of ops) in ms
            # This gives current performance rather than lifetime average
            read_latency = (results["read_time_rate"] / results["read_iops"] * 1000) if results["read_iops"] > 0 else 0
            write_latency = (results["write_time_rate"] / results["write_iops"] * 1000) if results["write_iops"] > 0 else 0

            return {
                "device": lmcache_device,
                # Live rates
                "readMBps": round(read_mbps, 2),
                "writeMBps": round(write_mbps, 2),
                "readIOPS": round(results["read_iops"], 1),
                "writeIOPS": round(results["write_iops"], 1),
                # Latency
                "readLatencyMs": round(read_latency, 3),
                "writeLatencyMs": round(write_latency, 3),
                # Cumulative totals
                "totalReadGB": round(total_read_gb, 2),
                "totalWriteGB": round(total_write_gb, 2),
                # Current state
                "activeIO": int(results["io_now"]),
                "source": "prometheus",
            }

    except (httpx.HTTPError, ValueError, TypeError, KeyError) as e:
        logger.warning("Failed to fetch SSD metrics from Prometheus: %s", e)

    # Return zeros if unavailable
    return {
        "device": lmcache_device,
        "readMBps": 0,
        "writeMBps": 0,
        "readIOPS": 0,
        "writeIOPS": 0,
        "readLatencyMs": 0,
        "writeLatencyMs": 0,
        "totalReadGB": 0,
        "totalWriteGB": 0,
        "activeIO": 0,
        "source": "unavailable",
    }


@router.get("/cpu")
async def get_cpu_metrics():
    """Get CPU metrics from node_exporter via Prometheus."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            queries = {
                "cpu_usage": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)',
                "memory_used": "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes",
                "memory_total": "node_memory_MemTotal_bytes",
            }

            results = {}
            for key, query in queries.items():
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json().get("data", {}).get("result", [])
                results[key] = float(data[0]["value"][1]) if data else 0

            memory_used_gb = results["memory_used"] / (1024**3)
            memory_total_gb = results["memory_total"] / (1024**3)

            # Estimate CPU power based on usage (rough approximation)
            cpu_power = 50 + (results["cpu_usage"] / 100) * 200  # 50W idle to 250W max

            return {
                "usage": round(results["cpu_usage"], 2),
                "power": round(cpu_power, 1),
                "memoryUsed": round(memory_used_gb, 2),
                "memoryTotal": round(memory_total_gb, 2),
                "source": "node-exporter",
            }

    except (httpx.HTTPError, ValueError, TypeError, KeyError) as e:
        logger.warning("Failed to fetch CPU metrics: %s", e)
        return {
            "usage": 0,
            "power": 0,
            "memoryUsed": 0,
            "memoryTotal": 0,
            "source": "unavailable",
        }


@router.get("/kv-cache-size")
async def calculate_kv_cache_size(tokens: int, model: str = "MegaBeam-Mistral-7B"):
    """
    Calculate estimated KV cache size based on token count and model.

    KV cache size formula (approximate):
    size = 2 * num_layers * num_heads * head_dim * sequence_length * dtype_size

    For Mistral-7B:
    - 32 layers, 8 KV heads, 128 head dim, bf16 (2 bytes)
    - Per token: 2 * 32 * 8 * 128 * 2 = 131,072 bytes = 128 KB
    """
    # Model configurations (KV cache bytes per token)
    model_configs = {
        "MegaBeam-Mistral-7B": {
            "layers": 32,
            "kv_heads": 8,
            "head_dim": 128,
            "dtype_bytes": 2,  # bf16
            "bytes_per_token": 131072,  # 128 KB
        },
        "Qwen3-VL-30B-A3B-Thinking": {
            "layers": 28,
            "kv_heads": 4,
            "head_dim": 128,
            "dtype_bytes": 2,
            "bytes_per_token": 57344,  # ~56 KB
        },
    }

    config = model_configs.get(model, model_configs["MegaBeam-Mistral-7B"])

    # Calculate sizes
    total_bytes = tokens * config["bytes_per_token"]
    total_mb = total_bytes / (1024 * 1024)
    total_gb = total_bytes / (1024 * 1024 * 1024)

    return {
        "tokens": tokens,
        "model": model,
        "kv_cache_bytes": total_bytes,
        "kv_cache_mb": round(total_mb, 2),
        "kv_cache_gb": round(total_gb, 3),
        "bytes_per_token": config["bytes_per_token"],
        "config": {
            "layers": config["layers"],
            "kv_heads": config["kv_heads"],
            "head_dim": config["head_dim"],
        },
    }
