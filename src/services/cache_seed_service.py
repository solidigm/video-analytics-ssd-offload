# Created by Metrum AI for Solidigm

"""Cache Seed Service - Manages loading context.json files for KV cache seeding."""

# pylint: disable=no-member
import os
import json
import logging
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

import cv2
import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from src.db.models import Analysis, Video
from src.db.database import get_db_context
from src.services.prompt_utils import compact_context_for_model, build_football_analysis_prompt
from src.services.vllm_health import wait_for_models_endpoint_or_warn

logger = logging.getLogger(__name__)

LLM_LMCACHE_URL = os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "aws-prototyping/MegaBeam-Mistral-7B-300k")
CONFIG_PATH = os.getenv("CACHE_SEED_CONFIG", "/app/configs/cache_seed_config.yaml")
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "650000"))
LMCACHE_WARMUP_ON_STARTUP = os.getenv("LMCACHE_WARMUP_ON_STARTUP", "true").lower() == "true"
LMCACHE_READY_TIMEOUT_SECONDS = int(os.getenv("LMCACHE_READY_TIMEOUT_SECONDS", "300"))
LMCACHE_WARMUP_MAX_TOKENS = int(os.getenv("LMCACHE_WARMUP_MAX_TOKENS", "64"))

LONG_CONTEXT_WARMUP_QUERY = os.getenv(
    "LONG_CONTEXT_WARMUP_QUERY",
    "Analyze the provided season (10 games). How did offensive and defensive " "performance trend over time? Early season vs late season efficiency? " "Points per game trajectory? 512 tokens.",
)
COLD_CACHE_WARMUP_QUERY = os.getenv(
    "COLD_CACHE_WARMUP_QUERY",
    "Analyze these 5 recent 2025 games from the context. Which players "
    "performed best overall (top rushers, receivers, defenders)? What "
    "formations were most effective for each team? Summarize key trends "
    "in 512 tokens using the full context provided.",
)


@dataclass
class SeedResult:
    """Result from a seeding operation."""

    success: bool
    cache_type: str
    videos_loaded: int
    total_tokens: int
    duration_ms: float
    error: Optional[str] = None
    videos: list = field(default_factory=list)


@dataclass
class CacheStatus:  # pylint: disable=too-many-instance-attributes
    """Current cache status."""

    season_archive_loaded: bool = False
    season_archive_count: int = 0
    cold_cache_loaded: bool = False
    cold_cache_count: int = 0
    warm_cache_loaded: bool = False
    warm_cache_count: int = 0
    last_seed_time: Optional[str] = None
    total_context_tokens: int = 0


class CacheSeedService:  # pylint: disable=too-many-instance-attributes
    """Service for managing cache seeding with context.json files."""

    def __init__(self):
        self.config: dict = {}
        self._status = CacheStatus()
        self._loaded_contexts: dict[str, str] = {}  # id -> context text
        self._seeding_in_progress = False

    def load_config(self) -> dict:
        """Load configuration from YAML file."""
        config_path = Path(CONFIG_PATH)
        if not config_path.exists():
            logger.warning("Config file not found: %s", CONFIG_PATH)
            return {}

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        logger.info("Loaded cache seed config from %s", CONFIG_PATH)
        return self.config

    def _get_context_path(self, context_folder: str) -> Path:
        """Get full path to context.json file."""
        context_dir = self.config.get("context_source_dir", "/data/seeding")
        return Path(context_dir) / context_folder / "context.json"

    def _load_context_json(self, context_path: Path) -> Optional[dict]:
        """Load and parse context.json file."""
        if not context_path.exists():
            logger.warning("Context file not found: %s", context_path)
            return None

        try:
            with open(context_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error("Failed to load context.json: %s", e)
            return None

    def _extract_narrative(self, context_data: dict) -> str:  # pylint: disable=too-many-locals,too-many-nested-blocks,too-many-branches,too-many-statements
        """Extract narrative from context data, handling multiple JSON formats."""
        if not context_data:
            return ""

        narrative = ""

        # Try 'chronological_narrative' first (older format)
        raw = context_data.get("chronological_narrative", "")

        # If empty/missing, try 'narrative' key (format used by actual game context files)
        if not raw:
            raw = context_data.get("narrative", "")

        # Handle list of segment dicts (extract 'narrative' field from each)
        if isinstance(raw, list):
            narrative_parts = []
            for item in raw:
                if item:
                    if isinstance(item, dict):
                        seg_narrative = item.get("narrative", "")
                        if seg_narrative:
                            narrative_parts.append(seg_narrative)
                    else:
                        narrative_parts.append(str(item))
            narrative = "\n\n".join(narrative_parts)
        elif isinstance(raw, str):
            narrative = raw

        # If still empty, try segment_analyses as last resort
        if not narrative:
            segments = context_data.get("segment_analyses", [])
            if segments:
                narrative_parts = []
                for seg in segments:
                    if isinstance(seg, dict):
                        analysis = seg.get("analysis", "")
                        if analysis:
                            if isinstance(analysis, list):
                                narrative_parts.extend(str(a) for a in analysis if a)
                            else:
                                narrative_parts.append(str(analysis))
                narrative = "\n\n".join(narrative_parts)

        # Add game header from game_info or game_details
        game_info = context_data.get("game_info") or context_data.get("game_details")
        if game_info and isinstance(game_info, dict):
            home = game_info.get("home_team", "")
            away = game_info.get("away_team", "")
            score_home = game_info.get("final_score_home", game_info.get("final_score", ""))
            score_away = game_info.get("final_score_away", "")
            season = game_info.get("season", "")
            game_num = game_info.get("game_number", "")
            title = game_info.get("title", "")

            header_parts = []
            if title:
                header_parts.append(f"Game: {title}")
            elif home and away:
                header_parts.append(f"Game: {home} vs {away}")
            if score_home and score_away:
                header_parts.append(f"Final Score: {home} {score_home} - {away} {score_away}")
            elif score_home:
                header_parts.append(f"Score: {score_home}")
            if season:
                header_parts.append(f"Season: {season}")
            if game_num:
                header_parts.append(f"Game Number: {game_num}")

            date = game_info.get("date", "")
            if date and date != "unknown":
                header_parts.append(f"Date: {date}")

            if header_parts:
                header = "\n".join(header_parts) + "\n\n"
                narrative = header + narrative

        return narrative

    async def _create_video_record(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        video_id: str,
        display_name: str,
        context_folder: str,
        context_text: str,
        video_filename: str,
        cache_type: str,
    ) -> Optional[Video]:
        """Create or update video record in DB with context."""
        try:
            logger.debug(
                "Creating video record for %s (context_folder=%s, cache_type=%s)",
                display_name,
                context_folder,
                cache_type,
            )

            # Construct real video path
            video_files_dir = self.config.get("video_files_dir", "/host/home/fgpu/rohith/phase3/soln/data/videos")
            video_path = Path(video_files_dir) / video_filename

            # Default metadata
            duration = 0.0
            width = 0
            height = 0
            fps = 0.0
            frame_count = 0
            file_size = 0

            # Extract metadata if file exists
            if video_path.exists():
                try:
                    cap = cv2.VideoCapture(str(video_path))
                    if cap.isOpened():
                        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        if fps > 0:
                            duration = frame_count / fps
                        cap.release()
                    file_size = video_path.stat().st_size
                except (OSError, ValueError, TypeError, cv2.error) as e:
                    logger.warning("Failed to extract metadata for %s: %s", video_filename, e)
            else:
                logger.warning("Video file not found: %s", video_path)

            async with get_db_context() as session:
                # Check if video with this filename already exists
                result = await session.execute(select(Video).where(Video.filename == display_name))
                existing_video = result.scalar_one_or_none()

                video = existing_video
                if not video:
                    # Create new video record
                    video = Video(
                        id=video_id,  # EXPLICITLY set ID to match config/frontend
                        filename=display_name,
                        original_path=str(video_path),  # Point to REAL video file
                        file_size_bytes=file_size,
                        duration_seconds=duration,
                        frame_count=frame_count,
                        width=width,
                        height=height,
                        fps=fps,
                        status="seeded",
                    )
                    session.add(video)
                    await session.flush()  # Get ID
                    logger.info("Created video record: %s (id: %s)", display_name, video.id)

                # Check for existing analysis
                result = await session.execute(select(Analysis).where(Analysis.video_id == video.id, Analysis.analysis_type == "seeded_context"))
                existing_analysis = result.scalar_one_or_none()

                if not existing_analysis:
                    analysis = Analysis(
                        video_id=video.id,
                        query="Seeded Context",
                        analysis_type="seeded_context",
                        status="completed",
                        coaching_report=context_text,
                        duration_seconds=0,
                    )
                    session.add(analysis)
                    logger.info("Created analysis record for %s", display_name)

                await session.commit()
                await session.refresh(video)

                return video

        except (SQLAlchemyError, OSError, ValueError, TypeError, cv2.error) as e:
            logger.error("Failed to create video/analysis record: %s", e)
            return None

    async def _warmup_cache(self, context_text: str, video_name: str) -> dict:
        """Send warmup query to LLM to populate KV cache."""
        warmup_query = self.config.get("warmup_query", "Summarize the key plays from this game.")

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                start_time = time.time()

                # Build message with context
                user_content = f"""You are a sports tactical analyst.

Context from {video_name}:
{context_text[:50000]}

Question: {warmup_query}"""

                response = await client.post(
                    f"{LLM_LMCACHE_URL}/chat/completions",
                    json={
                        "model": LLM_MODEL,
                        "messages": [{"role": "user", "content": user_content}],
                        "max_tokens": 512,
                        "temperature": 0.3,
                    },
                )

                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    result = response.json()
                    tokens = result.get("usage", {}).get("total_tokens", 0)
                    return {
                        "success": True,
                        "latency_ms": latency_ms,
                        "tokens": tokens,
                    }
                logger.warning("Warmup request failed: %s", response.status_code)
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except (httpx.HTTPError, ValueError, TypeError) as e:
            logger.error("Warmup failed: %s", e)
            return {"success": False, "error": str(e)}

    @staticmethod
    def _compact_context_for_model(context_text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
        """Match frontend/backend context compaction behavior for warmup prompts."""
        compacted, _ = compact_context_for_model(context_text, max_chars)
        return compacted

    def _compose_scenario_context(self, videos: list[dict]) -> str:
        """Build combined context in the same format used by the frontend."""
        combined_parts: list[str] = []
        for video_cfg in videos:
            video_id = video_cfg.get("id")
            display_name = video_cfg.get("display_name", video_id)
            narrative = self._loaded_contexts.get(video_id, "")
            if not narrative:
                continue

            combined_parts.append(f"\n\n=== GAME ANALYSIS: {display_name} ===\n" "The following is a detailed play-by-play breakdown from game footage analysis.\n\n" f"{narrative}")

        return "".join(combined_parts).strip()

    def _build_warmup_prompt(self, context_text: str, query: str) -> str:
        """Construct a warmup prompt aligned with the streaming chat prompt template."""
        return build_football_analysis_prompt(context_text, query)

    def _get_lmcache_chat_url(self) -> str:
        """Get LMCache chat completion URL."""
        base = LLM_LMCACHE_URL.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    async def _wait_for_lmcache_ready(self, timeout_seconds: int = LMCACHE_READY_TIMEOUT_SECONDS) -> bool:
        """Wait until LMCache vLLM server is ready."""
        base = LLM_LMCACHE_URL.rstrip("/")
        models_url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
        return await wait_for_models_endpoint_or_warn(
            models_url=models_url,
            timeout_seconds=timeout_seconds,
            logger=logger,
            service_name="LMCache",
        )

    async def _warmup_scenario(
        self,
        scenario_name: str,
        videos: list[dict],
        query: str,
    ) -> dict:
        """Warm up LMCache with a combined scenario prompt."""
        context = self._compose_scenario_context(videos)
        if not context:
            return {
                "success": False,
                "scenario": scenario_name,
                "error": "No context available for scenario warmup",
            }

        compacted_context = self._compact_context_for_model(context)
        prompt = self._build_warmup_prompt(compacted_context, query)
        prompt_tokens_est = len(prompt) // 4
        chat_url = self._get_lmcache_chat_url()

        logger.info(
            "LMCache warmup starting for %s (~%s prompt tokens, %s videos)",
            scenario_name,
            f"{prompt_tokens_est:,}",
            len(videos),
        )

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    chat_url,
                    json={
                        "model": LLM_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": LMCACHE_WARMUP_MAX_TOKENS,
                        "temperature": 0.0,
                    },
                )

            duration_ms = (time.time() - start) * 1000
            if response.status_code != 200:
                return {
                    "success": False,
                    "scenario": scenario_name,
                    "duration_ms": duration_ms,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }

            usage = response.json().get("usage", {})
            return {
                "success": True,
                "scenario": scenario_name,
                "duration_ms": duration_ms,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        except (httpx.HTTPError, ValueError, TypeError) as e:
            return {
                "success": False,
                "scenario": scenario_name,
                "error": str(e),
                "duration_ms": (time.time() - start) * 1000,
            }

    async def warmup_startup_scenarios(self) -> dict:
        """Warmup LMCache at startup with Season Archive (long-context) ONLY.

        Only the Season Archive scenario is warmed at startup so that the KV
        cache on the Solidigm SSD is pre-populated with the long context.
        When the user later selects Season Archive, LMCache reads from SSD
        (fast) while Baseline must compute from scratch (slow), demonstrating
        the KV offload advantage.
        """
        if not LMCACHE_WARMUP_ON_STARTUP:
            logger.info("LMCache startup warmup disabled (LMCACHE_WARMUP_ON_STARTUP=false)")
            return {"enabled": False, "success": False, "error": "disabled"}

        if not self.config:
            self.load_config()

        ready = await self._wait_for_lmcache_ready()
        if not ready:
            return {"enabled": True, "success": False, "error": "LMCache not ready"}

        # Only warm Season Archive (long-context) so KV cache is on SSD
        season_videos = self.config.get("season_archive", {}).get("videos", [])

        long_result = await self._warmup_scenario("long-context", season_videos, LONG_CONTEXT_WARMUP_QUERY)

        success = bool(long_result.get("success"))
        if success:
            logger.info("LMCache startup warmup completed for Season Archive (long-context only)")
        else:
            logger.warning(
                "LMCache startup warmup incomplete: long-context=%s",
                long_result.get("success"),
            )

        return {
            "enabled": True,
            "success": success,
            "long_context": long_result,
        }

    async def seed_season_archive(self) -> SeedResult:  # pylint: disable=too-many-locals
        """Load Season Archive (2024 games) into cache."""
        if self._seeding_in_progress:
            return SeedResult(
                success=False,
                cache_type="season_archive",
                videos_loaded=0,
                total_tokens=0,
                duration_ms=0,
                error="Seeding already in progress",
            )

        self._seeding_in_progress = True
        start_time = time.time()

        try:
            if not self.config:
                self.load_config()

            season_config = self.config.get("season_archive", {})
            videos = season_config.get("videos", [])

            if not videos:
                logger.warning("No Season Archive videos configured")
                return SeedResult(
                    success=False,
                    cache_type="season_archive",
                    videos_loaded=0,
                    total_tokens=0,
                    duration_ms=0,
                    error="No videos configured",
                )

            loaded_videos = []
            total_tokens = 0

            for video_config in videos:
                video_id = video_config.get("id")
                display_name = video_config.get("display_name")
                context_folder = video_config.get("context_folder")

                logger.info("Loading Season Archive: %s", display_name)

                # Load context.json
                context_path = self._get_context_path(context_folder)
                context_data = self._load_context_json(context_path)

                if not context_data:
                    logger.warning("Skipping %s - no context data", display_name)
                    continue

                # Extract narrative
                narrative = self._extract_narrative(context_data)
                if not narrative:
                    logger.warning("Skipping %s - no narrative", display_name)
                    continue

                # Store context
                self._loaded_contexts[video_id] = narrative

                # Create video record
                video_filename = video_config.get("filename")
                video = await self._create_video_record(
                    video_id,
                    display_name,
                    context_folder,
                    narrative,
                    video_filename,
                    "season_archive",
                )

                # Warmup cache (optional, can be slow)
                # warmup_result = await self._warmup_cache(narrative, display_name)
                # if warmup_result.get('success'):
                #     total_tokens += warmup_result.get('tokens', 0)

                # Estimate tokens (roughly 4 chars per token)
                est_tokens = len(narrative) // 4
                total_tokens += est_tokens

                loaded_videos.append(
                    {
                        "id": video_id,
                        "name": display_name,
                        "tokens": est_tokens,
                        "db_id": str(video.id) if video else None,
                    }
                )

            duration_ms = (time.time() - start_time) * 1000

            self._status.season_archive_loaded = True
            self._status.season_archive_count = len(loaded_videos)
            self._status.total_context_tokens = total_tokens
            self._status.last_seed_time = datetime.utcnow().isoformat()

            logger.info(
                "Season Archive seeded: %s videos, %s tokens",
                len(loaded_videos),
                total_tokens,
            )

            return SeedResult(
                success=True,
                cache_type="season_archive",
                videos_loaded=len(loaded_videos),
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                videos=loaded_videos,
            )

        except (SQLAlchemyError, OSError, ValueError, TypeError, RuntimeError) as e:
            logger.error("Season Archive seeding failed: %s", e)
            return SeedResult(
                success=False,
                cache_type="season_archive",
                videos_loaded=0,
                total_tokens=0,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )
        finally:
            self._seeding_in_progress = False

    async def seed_cold_cache(self, game_ids: Optional[list[str]] = None) -> SeedResult:  # pylint: disable=too-many-locals
        """Load Cold Cache (2025 Recent Games) into cache."""
        start_time = time.time()

        try:
            if not self.config:
                self.load_config()

            cold_config = self.config.get("cold_cache", {})
            videos = cold_config.get("videos", [])

            # Filter by game_ids if provided
            if game_ids:
                videos = [v for v in videos if v.get("id") in game_ids]

            if not videos:
                return SeedResult(
                    success=False,
                    cache_type="cold_cache",
                    videos_loaded=0,
                    total_tokens=0,
                    duration_ms=0,
                    error="No videos to load",
                )

            loaded_videos = []
            total_tokens = 0

            for video_config in videos:
                video_id = video_config.get("id")
                display_name = video_config.get("display_name")
                context_folder = video_config.get("context_folder")

                logger.info("Loading Cold Cache: %s", display_name)

                # Load context.json
                context_path = self._get_context_path(context_folder)
                context_data = self._load_context_json(context_path)

                if not context_data:
                    continue

                # Extract narrative
                narrative = self._extract_narrative(context_data)
                if not narrative:
                    continue

                # Store context
                self._loaded_contexts[video_id] = narrative

                # Create video record
                video_filename = video_config.get("filename")
                video = await self._create_video_record(video_id, display_name, context_folder, narrative, video_filename, "cold_cache")

                # Estimate tokens
                est_tokens = len(narrative) // 4
                total_tokens += est_tokens

                loaded_videos.append(
                    {
                        "id": video_id,
                        "name": display_name,
                        "tokens": est_tokens,
                        "db_id": str(video.id) if video else None,
                    }
                )

            duration_ms = (time.time() - start_time) * 1000

            self._status.cold_cache_loaded = True
            self._status.cold_cache_count = len(loaded_videos)
            self._status.total_context_tokens += total_tokens
            self._status.last_seed_time = datetime.utcnow().isoformat()

            logger.info(
                "Cold Cache seeded: %s videos, %s tokens",
                len(loaded_videos),
                total_tokens,
            )

            return SeedResult(
                success=True,
                cache_type="cold_cache",
                videos_loaded=len(loaded_videos),
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                videos=loaded_videos,
            )

        except (SQLAlchemyError, OSError, ValueError, TypeError, RuntimeError) as e:
            logger.error("Cold Cache seeding failed: %s", e)
            return SeedResult(
                success=False,
                cache_type="cold_cache",
                videos_loaded=0,
                total_tokens=0,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    async def seed_warm_cache(self) -> SeedResult:  # pylint: disable=too-many-locals
        """Load Warm Cache (small context videos) into cache."""
        start_time = time.time()

        try:
            if not self.config:
                self.load_config()

            warm_config = self.config.get("warm_cache", {})
            videos = warm_config.get("videos", [])

            if not videos:
                logger.warning("No Warm Cache videos configured")
                return SeedResult(
                    success=False,
                    cache_type="warm_cache",
                    videos_loaded=0,
                    total_tokens=0,
                    duration_ms=0,
                    error="No videos configured",
                )

            loaded_videos = []
            total_tokens = 0

            for video_config in videos:
                video_id = video_config.get("id")
                display_name = video_config.get("display_name")
                context_folder = video_config.get("context_folder")

                logger.info("Loading Warm Cache: %s", display_name)

                # Load context.json
                context_path = self._get_context_path(context_folder)
                context_data = self._load_context_json(context_path)

                if not context_data:
                    logger.warning("Skipping %s - no context data", display_name)
                    continue

                # Extract narrative
                narrative = self._extract_narrative(context_data)
                if not narrative:
                    logger.warning("Skipping %s - no narrative", display_name)
                    continue

                # Store context
                self._loaded_contexts[video_id] = narrative

                # Create video record
                video_filename = video_config.get("filename")
                video = await self._create_video_record(video_id, display_name, context_folder, narrative, video_filename, "warm_cache")

                # Estimate tokens
                est_tokens = len(narrative) // 4
                total_tokens += est_tokens

                loaded_videos.append(
                    {
                        "id": video_id,
                        "name": display_name,
                        "tokens": est_tokens,
                        "db_id": str(video.id) if video else None,
                    }
                )

            duration_ms = (time.time() - start_time) * 1000

            self._status.warm_cache_loaded = True
            self._status.warm_cache_count = len(loaded_videos)
            self._status.total_context_tokens += total_tokens
            self._status.last_seed_time = datetime.utcnow().isoformat()

            logger.info(
                "Warm Cache seeded: %s videos, %s tokens",
                len(loaded_videos),
                total_tokens,
            )

            return SeedResult(
                success=True,
                cache_type="warm_cache",
                videos_loaded=len(loaded_videos),
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                videos=loaded_videos,
            )

        except (SQLAlchemyError, OSError, ValueError, TypeError, RuntimeError) as e:
            logger.error("Warm Cache seeding failed: %s", e)
            return SeedResult(
                success=False,
                cache_type="warm_cache",
                videos_loaded=0,
                total_tokens=0,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    async def seed_all(self) -> dict:
        """Load ALL videos from all categories at startup."""
        results = {}

        logger.info("Starting to seed ALL videos...")

        # Seed season archive (10 videos)
        season_result = await self.seed_season_archive()
        results["season_archive"] = {
            "success": season_result.success,
            "videos_loaded": season_result.videos_loaded,
            "total_tokens": season_result.total_tokens,
        }

        # Seed cold cache (5 videos)
        cold_result = await self.seed_cold_cache()
        results["cold_cache"] = {
            "success": cold_result.success,
            "videos_loaded": cold_result.videos_loaded,
            "total_tokens": cold_result.total_tokens,
        }

        # Seed warm cache (2 videos)
        warm_result = await self.seed_warm_cache()
        results["warm_cache"] = {
            "success": warm_result.success,
            "videos_loaded": warm_result.videos_loaded,
            "total_tokens": warm_result.total_tokens,
        }

        # Warmup LMCache with Season Archive (long-context) only so KV cache is on SSD.
        warmup_result = await self.warmup_startup_scenarios()
        results["lmcache_warmup"] = warmup_result

        total_videos = season_result.videos_loaded + cold_result.videos_loaded + warm_result.videos_loaded
        total_tokens = season_result.total_tokens + cold_result.total_tokens + warm_result.total_tokens

        logger.info(
            "ALL videos seeded: %s total videos, %s total tokens",
            total_videos,
            total_tokens,
        )

        results["total"] = {
            "videos_loaded": total_videos,
            "total_tokens": total_tokens,
        }

        return results

    def get_context(self, video_id: str) -> Optional[str]:
        """Get loaded context for a video."""
        return self._loaded_contexts.get(video_id)

    def get_all_contexts(self) -> dict[str, str]:
        """Get all loaded contexts."""
        return self._loaded_contexts.copy()

    def get_cache_status(self) -> CacheStatus:
        """Get current cache status."""
        return self._status

    def get_available_videos(self) -> list[dict]:
        """Get list of available videos from config."""
        if not self.config:
            self.load_config()

        videos = []

        # Season archive videos
        season = self.config.get("season_archive", {})
        for v in season.get("videos", []):
            videos.append(
                {
                    "id": v.get("id"),
                    "name": v.get("display_name"),
                    "type": "season_archive",
                    "loaded": v.get("id") in self._loaded_contexts,
                }
            )

        # Cold cache videos
        cold = self.config.get("cold_cache", {})
        for v in cold.get("videos", []):
            videos.append(
                {
                    "id": v.get("id"),
                    "name": v.get("display_name"),
                    "type": "cold_cache",
                    "loaded": v.get("id") in self._loaded_contexts,
                }
            )

        # Warm cache videos
        warm = self.config.get("warm_cache", {})
        for v in warm.get("videos", []):
            videos.append(
                {
                    "id": v.get("id"),
                    "name": v.get("display_name"),
                    "type": "warm_cache",
                    "loaded": v.get("id") in self._loaded_contexts,
                }
            )

        return videos


# Global instance
cache_seed_service = CacheSeedService()
