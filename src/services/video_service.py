# Created by Metrum AI for Solidigm

"""Video Service - Handles video processing and agent analysis."""

# pylint: disable=no-member
import os
import uuid
import logging
import asyncio
import base64
import binascii
import time
from pathlib import Path
from typing import Optional, Literal

import cv2
import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.agents.american_football import analyze_game_film
from src.db.models import Video, Analysis, Telemetry
from src.db.database import get_db_context

logger = logging.getLogger(__name__)

VLM_API_URL = os.getenv("VLM_API_URL", "http://vllm-vlm:8000/v1")
LLM_LMCACHE_URL = os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000/v1")
VLM_MODEL = os.getenv("VLM_MODEL", "Qwen/Qwen3-VL-30B-A3B-Thinking")
LLM_MODEL = os.getenv("LLM_MODEL", "aws-prototyping/MegaBeam-Mistral-7B-300k")
DATA_PATH = os.getenv("DATA_PATH", "/data")


class VideoService:
    """Service for video processing and American Football analysis."""

    def __init__(self):
        self.data_path = Path(DATA_PATH)
        self.videos_path = self.data_path / "videos"
        self.frames_path = self.data_path / "frames"
        self.videos_path.mkdir(parents=True, exist_ok=True)
        self.frames_path.mkdir(parents=True, exist_ok=True)

    def _extract_video_metadata(self, video_path: str) -> dict:
        """Extract metadata from video file."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        metadata = {
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "duration_seconds": (int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 0),
        }
        cap.release()
        return metadata

    async def create_video(
        self,
        filename: str,
        file_path: str,
        file_size: int,
    ) -> Video:
        """Create video record in database."""
        metadata = self._extract_video_metadata(file_path)

        async with get_db_context() as session:
            video = Video(
                filename=filename,
                original_path=file_path,
                file_size_bytes=file_size,
                duration_seconds=metadata["duration_seconds"],
                frame_count=metadata["frame_count"],
                width=metadata["width"],
                height=metadata["height"],
                fps=metadata["fps"],
                status="uploaded",
            )
            session.add(video)
            await session.commit()
            await session.refresh(video)
            return video

    async def get_video(self, video_id: uuid.UUID) -> Optional[Video]:
        """Get video by ID."""
        async with get_db_context() as session:
            result = await session.execute(select(Video).where(Video.id == video_id))
            return result.scalar_one_or_none()

    async def list_videos(self, limit: int = 50) -> list[Video]:
        """List all videos."""
        async with get_db_context() as session:
            result = await session.execute(select(Video).order_by(Video.created_at.desc()).limit(limit))
            return list(result.scalars().all())

    async def list_videos_with_analyses(self, limit: int = 50) -> list[Video]:
        """List videos with analyses eagerly loaded to avoid N+1 queries."""
        async with get_db_context() as session:
            result = await session.execute(select(Video).options(selectinload(Video.analyses)).order_by(Video.created_at.desc()).limit(limit))
            return list(result.scalars().all())

    async def analyze_video(
        self,
        video_id: uuid.UUID,
        query: str,
        analysis_type: Literal["general", "offense", "defense", "red_zone", "matchups"] = "general",
    ) -> Analysis:
        """Run American Football agent analysis on video."""
        async with get_db_context() as session:
            result = await session.execute(select(Video).where(Video.id == video_id))
            video = result.scalar_one_or_none()
            if not video:
                raise ValueError(f"Video not found: {video_id}")

            analysis = Analysis(
                video_id=video_id,
                query=query,
                analysis_type=analysis_type,
                status="processing",
                llm_model=LLM_MODEL,
                vlm_model=VLM_MODEL,
            )
            session.add(analysis)
            await session.commit()
            await session.refresh(analysis)
            analysis_id = analysis.id

        try:
            agent_result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._run_agent_sync,
                video.original_path,
                query,
                analysis_type,
            )

            async with get_db_context() as session:
                result = await session.execute(select(Analysis).where(Analysis.id == analysis_id))
                analysis = result.scalar_one()
                analysis.coaching_report = agent_result.get("coaching_report", "")
                analysis.duration_seconds = agent_result.get("duration_seconds", 0)
                analysis.status = "completed" if agent_result.get("success") else "failed"
                analysis.error_message = agent_result.get("error") if not agent_result.get("success") else None
                await session.commit()
                await session.refresh(analysis)

                telemetry = Telemetry(
                    operation_name="video_analysis",
                    operation_type="agent",
                    video_id=video_id,
                    analysis_id=analysis_id,
                    duration_ms=agent_result.get("duration_seconds", 0) * 1000,
                    status=analysis.status,
                    attributes={
                        "analysis_type": analysis_type,
                        "query": query[:200],
                        "llm_model": LLM_MODEL,
                        "vlm_model": VLM_MODEL,
                    },
                )
                session.add(telemetry)
                await session.commit()

                return analysis

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Analysis failed: %s", e)
            async with get_db_context() as session:
                result = await session.execute(select(Analysis).where(Analysis.id == analysis_id))
                analysis = result.scalar_one()
                analysis.status = "failed"
                analysis.error_message = str(e)
                await session.commit()
                await session.refresh(analysis)
                return analysis

    def _run_agent_sync(
        self,
        video_path: str,
        query: str,
        analysis_type: str,
    ) -> dict:
        """Run American Football agent synchronously (called from executor)."""
        try:
            result = analyze_game_film(
                video_path=video_path,
                query=query,
                analysis_type=analysis_type,
            )
            if not result.get("success"):
                logger.warning(
                    "American Football agent failed: %s, using fallback",
                    result.get("error", "unknown"),
                )
                return self._fallback_analysis(video_path, query)
            return result
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("American Football agent error: %s, using fallback", e)
            return self._fallback_analysis(video_path, query)

    def _fallback_analysis(self, video_path: str, query: str) -> dict:
        """Fallback analysis when agent is not available."""
        start_time = time.time()

        try:
            # Use VLM to analyze video frames first, then LLM for synthesis
            vlm_analysis = self._analyze_video_frames(video_path)

            with httpx.Client(timeout=120) as client:
                # MegaBeam doesn't support system messages, include context in user message
                user_prompt = f"""You are a sports tactical analyst.

Video Analysis Context:
{vlm_analysis}

User Question: {query}

Please provide a detailed analysis based on the video content."""

                response = client.post(
                    f"{LLM_LMCACHE_URL}/chat/completions",
                    json={
                        "model": LLM_MODEL,
                        "messages": [
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 2048,
                        "temperature": 0.3,
                    },
                )
                response.raise_for_status()
                result = response.json()

                return {
                    "success": True,
                    "coaching_report": result["choices"][0]["message"]["content"],
                    "duration_seconds": time.time() - start_time,
                }
        except (httpx.HTTPError, ValueError, TypeError, RuntimeError) as e:
            logger.error("Fallback analysis failed: %s", e)
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": time.time() - start_time,
            }

    def _analyze_video_frames(self, video_path: str) -> str:  # pylint: disable=too-many-locals
        """Extract and analyze key frames from video using VLM."""
        try:
            # Open video and extract a few key frames
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return "Could not open video file."

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            # Extract 3 frames: beginning, middle, end
            frame_positions = [
                int(total_frames * 0.1),
                int(total_frames * 0.5),
                int(total_frames * 0.9),
            ]

            frame_analyses = []

            for i, pos in enumerate(frame_positions):
                cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
                ret, frame = cap.read()
                if not ret:
                    continue

                # Encode frame as base64
                _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                b64_image = base64.b64encode(buffer).decode("utf-8")

                # Send to VLM for analysis
                with httpx.Client(timeout=60) as client:
                    response = client.post(
                        f"{VLM_API_URL}/chat/completions",
                        json={
                            "model": VLM_MODEL,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "Describe what you see in this frame from a video. Focus on people, actions, settings, and any notable visual elements.",
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                                        },
                                    ],
                                },
                            ],
                            "max_tokens": 512,
                            "temperature": 0.2,
                        },
                    )
                    response.raise_for_status()
                    result = response.json()
                    description = result["choices"][0]["message"]["content"]
                    frame_analyses.append(f"Frame {i+1} (at {pos/fps:.1f}s): {description}")

            cap.release()

            if frame_analyses:
                return "\n\n".join(frame_analyses)
            return "Could not analyze video frames."

        except (
            cv2.error,
            httpx.HTTPError,
            ValueError,
            TypeError,
            RuntimeError,
            binascii.Error,
        ) as e:
            logger.error("Frame analysis failed: %s", e)
            return f"Video frame analysis unavailable: {str(e)}"

    async def get_analysis(self, analysis_id: uuid.UUID) -> Optional[Analysis]:
        """Get analysis by ID."""
        async with get_db_context() as session:
            result = await session.execute(select(Analysis).where(Analysis.id == analysis_id))
            return result.scalar_one_or_none()

    async def list_analyses(self, video_id: Optional[uuid.UUID] = None, limit: int = 50) -> list[Analysis]:
        """List analyses, optionally filtered by video."""
        async with get_db_context() as session:
            query = select(Analysis).order_by(Analysis.created_at.desc()).limit(limit)
            if video_id:
                query = query.where(Analysis.video_id == video_id)
            result = await session.execute(query)
            return list(result.scalars().all())
