# Created by Metrum AI for Solidigm

"""Shared helpers for Server-Sent Events responses."""

from collections.abc import AsyncGenerator

from fastapi.responses import StreamingResponse


def create_sse_response(stream: AsyncGenerator[str, None]) -> StreamingResponse:
    """Create a standard SSE response with no-buffer headers."""
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
