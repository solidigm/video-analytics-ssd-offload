# Created by Metrum AI for Solidigm

"""Chat Service - Handles LLM routing and chat interactions."""

import os
import uuid
import time
import logging
import asyncio
from typing import Optional, Literal
from dataclasses import dataclass

import httpx
from sqlalchemy import select, func

from src.db.models import ChatSession, Analysis, Telemetry
from src.db.database import get_db_context
from src.services.prompt_utils import compact_context_for_model, build_football_analysis_prompt

logger = logging.getLogger(__name__)

LLM_LMCACHE_URL = os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000/v1")
LLM_BASELINE_URL = os.getenv("LLM_BASELINE_URL", "http://vllm-baseline:8000/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "aws-prototyping/MegaBeam-Mistral-7B-300k")
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "650000"))
LLM_REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "300"))


@dataclass
class ChatResponse:  # pylint: disable=too-many-instance-attributes
    """Response from chat service."""

    session_id: str
    query: str
    response: str
    llm_target: str
    latency_ms: float
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    cache_hit: bool


@dataclass
class ComparisonResponse:
    """Response comparing both LLMs."""

    query: str
    lmcache: ChatResponse
    baseline: ChatResponse
    speedup_percent: float


class ChatService:  # pylint: disable=too-many-instance-attributes
    """Service for chat interactions with LLM routing."""

    def __init__(self):
        self.lmcache_url = LLM_LMCACHE_URL
        self.baseline_url = LLM_BASELINE_URL
        self.model = LLM_MODEL

    def _get_llm_url(self, target: str) -> str:
        """Get LLM URL based on target."""
        if target == "lmcache":
            return self.lmcache_url
        if target == "baseline":
            return self.baseline_url
        raise ValueError(f"Unknown LLM target: {target}")

    def _compact_context_for_model(self, context_text: str, max_chars: int = MAX_CONTEXT_CHARS) -> tuple[str, bool]:
        """Compact oversized context while preserving all game sections when possible."""
        return compact_context_for_model(context_text, max_chars)

    async def _call_llm(
        self,
        url: str,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> dict:
        """Call LLM API."""
        async with httpx.AsyncClient(timeout=LLM_REQUEST_TIMEOUT_SECONDS) as client:
            start_time = time.time()
            response = await client.post(
                f"{url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            latency_ms = (time.time() - start_time) * 1000
            result = response.json()

            return {
                "content": result["choices"][0]["message"]["content"],
                "latency_ms": latency_ms,
                "tokens_prompt": result.get("usage", {}).get("prompt_tokens", 0),
                "tokens_completion": result.get("usage", {}).get("completion_tokens", 0),
                "tokens_total": result.get("usage", {}).get("total_tokens", 0),
            }

    async def chat(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        query: str,
        llm_target: Literal["lmcache", "baseline"] = "lmcache",
        analysis_id: Optional[uuid.UUID] = None,
        video_id: Optional[uuid.UUID] = None,
        context: Optional[str] = None,
    ) -> ChatResponse:
        """
        Send chat query to specified LLM.

        Args:
            query: User query
            llm_target: Which LLM to use ("lmcache" or "baseline")
            analysis_id: Optional analysis ID for context
            video_id: Optional video ID for context
            context: Optional additional context
        """
        context_text = context or ""

        if analysis_id:
            async with get_db_context() as session:
                result = await session.execute(select(Analysis).where(Analysis.id == analysis_id))
                analysis = result.scalar_one_or_none()
                if analysis and analysis.coaching_report:
                    context_text = f"Previous Analysis:\n{analysis.coaching_report[:8000]}\n\n{context_text}"

        context_text, was_truncated = self._compact_context_for_model(context_text)
        if was_truncated:
            logger.warning(
                "Context truncated for chat request (target=%s): original > %s chars",
                llm_target,
                MAX_CONTEXT_CHARS,
            )

        # MegaBeam doesn't support system messages, include context in user message
        if context_text:
            user_content = build_football_analysis_prompt(context_text, query)
        else:
            user_content = "You are an expert American football analyst and coaching strategist.\n\n" f"Question: {query}"

        messages = [{"role": "user", "content": user_content}]

        url = self._get_llm_url(llm_target)
        llm_result = await self._call_llm(url, messages)

        async with get_db_context() as session:
            chat_session = ChatSession(
                analysis_id=analysis_id,
                video_id=video_id,
                query=query,
                response=llm_result["content"],
                llm_target=llm_target,
                latency_ms=llm_result["latency_ms"],
                tokens_prompt=llm_result["tokens_prompt"],
                tokens_completion=llm_result["tokens_completion"],
                tokens_total=llm_result["tokens_total"],
                cache_hit=(llm_target == "lmcache"),
            )
            session.add(chat_session)
            await session.commit()
            await session.refresh(chat_session)

            telemetry = Telemetry(
                operation_name="chat_query",
                operation_type="llm",
                video_id=video_id,
                analysis_id=analysis_id,
                chat_session_id=chat_session.id,
                duration_ms=llm_result["latency_ms"],
                status="completed",
                attributes={
                    "llm_target": llm_target,
                    "tokens_total": llm_result["tokens_total"],
                    "model": self.model,
                },
            )
            session.add(telemetry)
            await session.commit()

            return ChatResponse(
                session_id=str(chat_session.id),
                query=query,
                response=llm_result["content"],
                llm_target=llm_target,
                latency_ms=llm_result["latency_ms"],
                tokens_prompt=llm_result["tokens_prompt"],
                tokens_completion=llm_result["tokens_completion"],
                tokens_total=llm_result["tokens_total"],
                cache_hit=(llm_target == "lmcache"),
            )

    async def compare(
        self,
        query: str,
        analysis_id: Optional[uuid.UUID] = None,
        video_id: Optional[uuid.UUID] = None,
        context: Optional[str] = None,
    ) -> ComparisonResponse:
        """
        Compare response from both LLMs.

        Runs query against both LMCache and baseline LLM for A/B comparison.
        """
        lmcache_task = self.chat(
            query=query,
            llm_target="lmcache",
            analysis_id=analysis_id,
            video_id=video_id,
            context=context,
        )
        baseline_task = self.chat(
            query=query,
            llm_target="baseline",
            analysis_id=analysis_id,
            video_id=video_id,
            context=context,
        )

        lmcache_result, baseline_result = await asyncio.gather(
            lmcache_task,
            baseline_task,
        )

        speedup = 0.0
        if baseline_result.latency_ms > 0:
            speedup = ((baseline_result.latency_ms - lmcache_result.latency_ms) / baseline_result.latency_ms) * 100

        return ComparisonResponse(
            query=query,
            lmcache=lmcache_result,
            baseline=baseline_result,
            speedup_percent=round(speedup, 2),
        )

    async def get_chat_history(
        self,
        video_id: Optional[uuid.UUID] = None,
        analysis_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> list[ChatSession]:
        """Get chat history."""
        async with get_db_context() as session:
            query = select(ChatSession).order_by(ChatSession.created_at.desc()).limit(limit)
            if video_id:
                query = query.where(ChatSession.video_id == video_id)
            if analysis_id:
                query = query.where(ChatSession.analysis_id == analysis_id)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_llm_stats(self, llm_target: Optional[str] = None) -> dict:
        """Get LLM usage statistics."""
        async with get_db_context() as session:
            query = select(
                ChatSession.llm_target,
                func.count(ChatSession.id).label("total_queries"),
                func.avg(ChatSession.latency_ms).label("avg_latency_ms"),
                func.sum(ChatSession.tokens_total).label("total_tokens"),
            ).group_by(ChatSession.llm_target)

            if llm_target:
                query = query.where(ChatSession.llm_target == llm_target)

            result = await session.execute(query)
            rows = result.all()

            stats = {}
            for row in rows:
                stats[row.llm_target] = {
                    "total_queries": row.total_queries,
                    "avg_latency_ms": round(float(row.avg_latency_ms or 0), 2),
                    "total_tokens": row.total_tokens or 0,
                }

            return stats
