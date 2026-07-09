# Created by Metrum AI for Solidigm

"""Chat API Routes."""

# pylint: disable=too-few-public-methods

import os
import uuid
import logging
import asyncio
from typing import Optional, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.api.routes.sse import create_sse_response
from src.services.chat_service import ChatService, ChatResponse, ComparisonResponse

LLM_LMCACHE_URL = os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000")
LLM_BASELINE_URL = os.getenv("LLM_BASELINE_URL", "http://vllm-baseline:8000")

logger = logging.getLogger(__name__)
router = APIRouter()

chat_service = ChatService()


class ChatRequest(BaseModel):
    """Incoming chat request for a single target or comparison run."""

    query: str
    llm_target: Literal["lmcache", "baseline", "both"] = "lmcache"
    analysis_id: Optional[str] = None
    video_id: Optional[str] = None
    context: Optional[str] = None


class LLMStatsResponse(BaseModel):
    """Aggregated usage stats for LMCache and baseline backends."""

    lmcache: Optional[dict] = None
    baseline: Optional[dict] = None


@router.post("", response_model=ChatResponse | ComparisonResponse)
async def chat(request: ChatRequest):
    """
    Send a chat query to the LLM.

    - **llm_target**: "lmcache" (with KV cache offload), "baseline" (no offload), or "both" (compare)
    - **analysis_id**: Optional analysis UUID to use as context
    - **video_id**: Optional video UUID to associate with this chat
    - **context**: Optional additional context string
    """
    analysis_uuid = uuid.UUID(request.analysis_id) if request.analysis_id else None
    video_uuid = uuid.UUID(request.video_id) if request.video_id else None

    try:
        if request.llm_target == "both":
            result = await chat_service.compare(
                query=request.query,
                analysis_id=analysis_uuid,
                video_id=video_uuid,
                context=request.context,
            )
            return result
        result = await chat_service.chat(
            query=request.query,
            llm_target=request.llm_target,
            analysis_id=analysis_uuid,
            video_id=video_uuid,
            context=request.context,
        )
        return result
    except Exception as e:
        logger.error("Chat failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/history")
async def get_chat_history(
    video_id: Optional[str] = Query(None),
    analysis_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
):
    """Get chat history, optionally filtered by video or analysis."""
    video_uuid = uuid.UUID(video_id) if video_id else None
    analysis_uuid = uuid.UUID(analysis_id) if analysis_id else None

    sessions = await chat_service.get_chat_history(
        video_id=video_uuid,
        analysis_id=analysis_uuid,
        limit=limit,
    )

    return {
        "sessions": [s.to_dict() for s in sessions],
        "count": len(sessions),
    }


@router.get("/stats", response_model=LLMStatsResponse)
async def get_llm_stats():
    """Get LLM usage statistics for comparison."""
    stats = await chat_service.get_llm_stats()

    return LLMStatsResponse(
        lmcache=stats.get("lmcache"),
        baseline=stats.get("baseline"),
    )


class StreamChatRequest(BaseModel):
    """Streaming proxy request body for forwarding to vLLM backends."""

    messages: list[dict]
    model: str = "aws-prototyping/MegaBeam-Mistral-7B-300k"
    max_tokens: int = 1024
    temperature: float = 0.3
    stream: bool = True


@router.post("/stream/{target}")
async def stream_chat(
    target: Literal["lmcache", "baseline"],
    request: StreamChatRequest,
    raw_request: Request,
):
    """
    Proxy streaming chat requests to vLLM servers.

    This endpoint allows the frontend to stream responses through the backend,
    avoiding browser CORS issues with direct vLLM server connections.

    When the client disconnects (e.g. AbortController.abort()), the upstream
    httpx connection is closed immediately so the vLLM server can free the
    request slot.
    """
    if target == "lmcache":
        base_url = LLM_LMCACHE_URL.rstrip("/")
    else:
        base_url = LLM_BASELINE_URL.rstrip("/")

    # Handle URLs that already end with /v1
    if base_url.endswith("/v1"):
        url = f"{base_url}/chat/completions"
    else:
        url = f"{base_url}/v1/chat/completions"
    logger.info("Proxying stream request to %s -> %s", target, url)

    async def generate():
        client = httpx.AsyncClient(timeout=300.0)
        try:
            async with client.stream(
                "POST",
                url,
                json={
                    "model": request.model,
                    "messages": request.messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                    "stream": True,
                },
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    logger.error("vLLM error: %s - %s", response.status_code, error_body)
                    yield f'data: {{"error": "vLLM returned {response.status_code}"}}\n\n'
                    return

                async for chunk in response.aiter_bytes():
                    # Check if the downstream client has disconnected
                    if await raw_request.is_disconnected():
                        logger.info(
                            "Client disconnected, closing upstream %s stream",
                            target,
                        )
                        break
                    yield chunk
        except asyncio.CancelledError:
            logger.info("Stream to %s cancelled (client disconnect)", target)
        except (httpx.HTTPError, ValueError, TypeError, RuntimeError) as e:
            logger.error("Stream error (%s): %s", target, e)
            yield f'data: {{"error": "{str(e)}"}}\n\n'
        finally:
            await client.aclose()

    return create_sse_response(generate())
