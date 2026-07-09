# Created by Metrum AI for Solidigm

"""Shared readiness helpers for vLLM endpoints."""

import asyncio
from logging import Logger
from typing import Tuple

import httpx


async def wait_for_models_endpoint(
    models_url: str,
    timeout_seconds: int,
    poll_interval_seconds: float = 2.0,
    request_timeout_seconds: float = 5.0,
) -> Tuple[bool, str]:
    """Poll a vLLM `/models` endpoint until it returns HTTP 200 or times out."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    last_error = ""

    while loop.time() < deadline:
        try:
            async with httpx.AsyncClient(timeout=request_timeout_seconds) as client:
                response = await client.get(models_url)
                if response.status_code == 200:
                    return True, last_error
                last_error = f"HTTP {response.status_code}"
        except (httpx.HTTPError, OSError, ValueError, TypeError) as error:
            last_error = str(error)

        await asyncio.sleep(poll_interval_seconds)

    return False, last_error


async def wait_for_models_endpoint_or_warn(
    models_url: str,
    timeout_seconds: int,
    logger: Logger,
    service_name: str,
) -> bool:
    """Wait for readiness and emit a consistent timeout warning when unavailable."""
    is_ready, last_error = await wait_for_models_endpoint(
        models_url=models_url,
        timeout_seconds=timeout_seconds,
    )
    if is_ready:
        return True

    logger.warning(
        "%s server not ready after %ss (last error: %s)",
        service_name,
        timeout_seconds,
        last_error or "unknown",
    )
    return False
