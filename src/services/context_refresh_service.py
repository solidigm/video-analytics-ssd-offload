# Created by Metrum AI for Solidigm

"""Context Refresh Service - Flushes baseline GPU KV cache using book texts.

After every baseline LLM call (for Cold Cache and Season Archive scenarios),
sends a large book text to the baseline vLLM instance with max_tokens=1.
This floods the GPU KV cache with book tokens, evicting the game context,
so the next real query forces baseline to recompute from scratch while
LMCache can reload from SSD.
"""

import os
import re
import asyncio
import logging
from pathlib import Path

import httpx

from src.services.vllm_health import wait_for_models_endpoint_or_warn

logger = logging.getLogger(__name__)

LLM_BASELINE_URL = os.getenv("LLM_BASELINE_URL", "http://vllm-baseline:8000/v1")
LLM_LMCACHE_URL = os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "aws-prototyping/MegaBeam-Mistral-7B-300k")

# Load text files up to this many chars; runtime flush will shrink further if needed.
MAX_FLUSH_CHARS = int(os.getenv("MAX_FLUSH_CHARS", "780000"))
MIN_FLUSH_CHARS = int(os.getenv("MIN_FLUSH_CHARS", "120000"))
FLUSH_INPUT_TOKEN_BUDGET = int(os.getenv("FLUSH_INPUT_TOKEN_BUDGET", "190000"))
FLUSH_MAX_ATTEMPTS = int(os.getenv("FLUSH_MAX_ATTEMPTS", "6"))
BASELINE_READY_TIMEOUT_SECONDS = int(os.getenv("BASELINE_READY_TIMEOUT_SECONDS", "180"))
FLUSH_SAFE_CHARS = int(os.getenv("FLUSH_SAFE_CHARS", "680000"))

# Scenarios that require baseline flushing
FLUSH_SCENARIOS = {"cold cache", "cold-cache", "long-context", "long context"}


class ContextRefreshService:
    """Manages book-based GPU cache flushing for the baseline vLLM instance."""

    def __init__(self):
        self._books: list[tuple[str, str]] = []  # [(filename, truncated_text), ...]
        self._rotation_index: int = 0

    def ensure_books_loaded(self) -> bool:
        """Ensure flush books are loaded and return True when available."""
        if not self._books:
            self.load_books()
        return bool(self._books)

    @staticmethod
    def _normalize_scenario_id(scenario_id: str | None) -> str:
        """Normalize scenario ids for robust matching."""
        if not scenario_id:
            return ""
        return scenario_id.strip().lower()

    @staticmethod
    def _parse_context_limit_error(error_text: str) -> tuple[int, int] | None:
        """Parse vLLM context-length errors as (input_tokens, max_tokens)."""
        input_match = re.search(r"request has (\d+) input tokens", error_text)
        max_match = re.search(r"maximum context length is (\d+) tokens", error_text)
        if not input_match or not max_match:
            return None
        return int(input_match.group(1)), int(max_match.group(1))

    def _get_baseline_base_url(self) -> str:
        """Get baseline base URL ending with /v1."""
        baseline_url = LLM_BASELINE_URL.rstrip("/")
        if not baseline_url.endswith("/v1"):
            baseline_url = f"{baseline_url}/v1"
        return baseline_url

    def _get_lmcache_base_url(self) -> str:
        """Get LMCache base URL ending with /v1."""
        lmcache_url = LLM_LMCACHE_URL.rstrip("/")
        if not lmcache_url.endswith("/v1"):
            lmcache_url = f"{lmcache_url}/v1"
        return lmcache_url

    async def _wait_for_baseline_ready(self, timeout_seconds: int) -> bool:
        """Wait until baseline vLLM server is reachable."""
        baseline_url = self._get_baseline_base_url()
        models_url = f"{baseline_url}/models"
        return await wait_for_models_endpoint_or_warn(
            models_url=models_url,
            timeout_seconds=timeout_seconds,
            logger=logger,
            service_name="Baseline",
        )

    def load_books(self):
        """Load all book files from the data/context/ directory."""
        data_path = os.getenv("DATA_PATH", "/data")
        context_dir = Path(data_path) / "context"

        if not context_dir.exists():
            # Fallback for local development
            context_dir = Path(__file__).parent.parent.parent / "data" / "context"

        if not context_dir.exists():
            logger.warning("Context directory not found: %s", context_dir)
            return

        self._books = []
        for txt_file in sorted(context_dir.glob("*.txt")):
            try:
                text = txt_file.read_text(encoding="utf-8")
                truncated = text[:MAX_FLUSH_CHARS]
                self._books.append((txt_file.name, truncated))
                est_tokens = len(truncated) // 4
                logger.info(
                    "Loaded flush book: %s (%s chars, ~%s tokens)",
                    txt_file.name,
                    f"{len(truncated):,}",
                    f"{est_tokens:,}",
                )
            except (OSError, UnicodeDecodeError, ValueError, TypeError) as e:
                logger.error("Failed to load %s: %s", txt_file.name, e)

        logger.info("Loaded %s books for baseline cache flushing", len(self._books))

    def _get_next_book(self) -> tuple[str, str] | None:
        """Get the next book in rotation. Returns (filename, text) or None."""
        if not self._books:
            return None
        book = self._books[self._rotation_index % len(self._books)]
        self._rotation_index += 1
        return book

    async def flush_baseline(  # pylint: disable=too-many-locals,too-many-return-statements
        self,
        wait_for_server: bool = False,
        ready_timeout_seconds: int = BASELINE_READY_TIMEOUT_SECONDS,
    ) -> bool:
        """Send a book to baseline vLLM to evict game context from GPU KV cache."""
        book = self._get_next_book()
        if not book:
            logger.warning("No books loaded, cannot flush baseline cache")
            return False

        filename, text = book

        if wait_for_server:
            ready = await self._wait_for_baseline_ready(ready_timeout_seconds)
            if not ready:
                return False

        baseline_url = self._get_baseline_base_url()
        url = f"{baseline_url}/chat/completions"
        candidate_chars = min(len(text), MAX_FLUSH_CHARS, FLUSH_SAFE_CHARS)

        for attempt in range(1, FLUSH_MAX_ATTEMPTS + 1):
            payload_text = text[:candidate_chars]
            logger.info(
                "Flushing baseline GPU cache with %s (attempt=%s/%s, chars=%s, ~%s tokens)",
                filename,
                attempt,
                FLUSH_MAX_ATTEMPTS,
                f"{candidate_chars:,}",
                f"{candidate_chars // 4:,}",
            )
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    response = await client.post(
                        url,
                        json={
                            "model": LLM_MODEL,
                            "messages": [{"role": "user", "content": payload_text}],
                            "max_tokens": 1,
                            "temperature": 0,
                            "stream": False,
                        },
                    )

                if response.status_code == 200:
                    logger.info(
                        "Baseline cache flush completed with %s (chars=%s)",
                        filename,
                        f"{candidate_chars:,}",
                    )
                    return True

                body = response.text[:500]
                logger.warning("Baseline flush returned %s: %s", response.status_code, body)

                # If over context limit, shrink and retry.
                if response.status_code == 400 and "maximum context length" in body.lower():
                    parsed = self._parse_context_limit_error(body)
                    if parsed:
                        input_tokens, max_tokens = parsed
                        target_tokens = min(FLUSH_INPUT_TOKEN_BUDGET, max_tokens - 3000)
                        if target_tokens <= 0:
                            logger.error("Invalid target token budget for flush: %s", target_tokens)
                            return False
                        scale = target_tokens / max(input_tokens, 1)
                        next_chars = int(candidate_chars * scale * 0.98)
                    else:
                        next_chars = int(candidate_chars * 0.85)

                    next_chars = max(MIN_FLUSH_CHARS, next_chars)
                    if next_chars >= candidate_chars:
                        logger.error("Cannot reduce flush payload further (chars=%s)", candidate_chars)
                        return False

                    logger.warning(
                        "Retrying baseline flush with smaller payload: %s -> %s chars",
                        f"{candidate_chars:,}",
                        f"{next_chars:,}",
                    )
                    candidate_chars = next_chars
                    continue

                return False
            except (httpx.HTTPError, OSError, ValueError, TypeError) as e:
                logger.error("Baseline cache flush failed: %s", e)
                return False

        logger.error("Baseline cache flush failed after %s attempts", FLUSH_MAX_ATTEMPTS)
        return False

    async def flush_lmcache(self) -> bool:  # pylint: disable=too-many-locals
        """Send a book to LMCache vLLM to evict game context from KV cache (GPU + SSD offload)."""
        book = self._get_next_book()
        if not book:
            logger.warning("No books loaded, cannot flush LMCache")
            return False

        _filename, text = book
        lmcache_url = self._get_lmcache_base_url()
        url = f"{lmcache_url}/chat/completions"
        candidate_chars = min(len(text), MAX_FLUSH_CHARS, FLUSH_SAFE_CHARS)

        for attempt in range(1, FLUSH_MAX_ATTEMPTS + 1):
            payload_text = text[:candidate_chars]
            logger.info(
                "Flushing LMCache KV cache (attempt=%s/%s, chars=%s)",
                attempt,
                FLUSH_MAX_ATTEMPTS,
                f"{candidate_chars:,}",
            )
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    response = await client.post(
                        url,
                        json={
                            "model": LLM_MODEL,
                            "messages": [{"role": "user", "content": payload_text}],
                            "max_tokens": 1,
                            "temperature": 0,
                            "stream": False,
                        },
                    )

                if response.status_code == 200:
                    logger.info("LMCache flush completed (chars=%s)", f"{candidate_chars:,}")
                    return True

                body = response.text[:500]
                logger.warning("LMCache flush returned %s: %s", response.status_code, body)
                if response.status_code == 400 and "maximum context length" in body.lower():
                    parsed = self._parse_context_limit_error(body)
                    if parsed:
                        input_tokens, max_tokens = parsed
                        target_tokens = min(FLUSH_INPUT_TOKEN_BUDGET, max_tokens - 3000)
                        if target_tokens > 0:
                            scale = target_tokens / max(input_tokens, 1)
                            candidate_chars = int(candidate_chars * scale * 0.98)
                    else:
                        candidate_chars = int(candidate_chars * 0.85)
                    candidate_chars = max(MIN_FLUSH_CHARS, candidate_chars)
                    continue
                return False
            except (httpx.HTTPError, OSError, ValueError, TypeError) as e:
                logger.error("LMCache flush failed: %s", e)
                return False

        logger.error("LMCache flush failed after %s attempts", FLUSH_MAX_ATTEMPTS)
        return False

    async def flush_baseline_and_lmcache(
        self,
        wait_for_server: bool = False,
        ready_timeout_seconds: int = BASELINE_READY_TIMEOUT_SECONDS,
    ) -> tuple[bool, bool]:
        """Flush both baseline and LMCache in parallel. Returns (baseline_ok, lmcache_ok)."""
        baseline_coro = self.flush_baseline(
            wait_for_server=wait_for_server,
            ready_timeout_seconds=ready_timeout_seconds,
        )
        lmcache_coro = self.flush_lmcache()
        baseline_ok, lmcache_ok = await asyncio.gather(baseline_coro, lmcache_coro)
        return baseline_ok, lmcache_ok

    def should_flush(self, scenario_id: str | None) -> bool:
        """Check if this scenario requires baseline cache flushing."""
        return self._normalize_scenario_id(scenario_id) in FLUSH_SCENARIOS


# Module-level singleton
context_refresh_service = ContextRefreshService()
