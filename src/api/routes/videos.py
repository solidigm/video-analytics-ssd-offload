# Created by Metrum AI for Solidigm

"""Video API Routes."""

# pylint: disable=no-member,too-few-public-methods
import os
import uuid
import shutil
import logging
import json
from pathlib import Path
from typing import Optional, Literal

import cv2
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query, Form
from fastapi.responses import Response
from pydantic import BaseModel

from src.db.database import get_db_context
from src.db.models import Analysis
from src.services.video_service import VideoService

logger = logging.getLogger(__name__)
router = APIRouter()

video_service = VideoService()

DATA_PATH = os.getenv("DATA_PATH", "/data")
UPLOAD_DIR = Path(DATA_PATH) / "videos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# KV cache memory per token for MegaBeam-Mistral-7B (128 KB per token)
KV_CACHE_BYTES_PER_TOKEN = 131_072


def _estimate_tokens_from_analyses(analyses: list[Analysis]) -> int:
    """
    Estimate context tokens from persisted analysis reports.

    Count only completed analyses with a coaching_report. This endpoint powers
    context selection UI, so estimates should represent *available* context,
    not potential future output.
    """
    total_tokens = 0
    for analysis in analyses:
        if analysis.status == "completed" and analysis.coaching_report:
            words = len(analysis.coaching_report.split())
            total_tokens += int(words * 1.3)

    return total_tokens


class VideoUploadResponse(BaseModel):
    """Response returned after a video upload or registration."""

    id: str
    filename: str
    status: str
    message: str


class AnalysisRequest(BaseModel):
    """Request body for analyzing an already-registered video."""

    query: str
    analysis_type: Literal["general", "offense", "defense", "red_zone", "matchups"] = "general"


class DirectAnalysisRequest(BaseModel):
    """Request body for direct path-based analysis."""

    path: str
    query: str
    analysis_type: Literal["general", "offense", "defense", "red_zone", "matchups"] = "general"


class AnalysisResponse(BaseModel):
    """Serialized analysis record returned by API endpoints."""

    id: str
    video_id: str
    query: str
    analysis_type: str
    status: str
    coaching_report: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None


class VideoResponse(BaseModel):
    """Compact video metadata response used in list/detail endpoints."""

    id: str
    filename: str
    duration_seconds: Optional[float]
    frame_count: Optional[int]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    status: str
    created_at: str


@router.post("", response_model=VideoUploadResponse)
async def upload_video(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches,too-many-statements
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    context: Optional[UploadFile] = File(None),
    video_path: Optional[str] = Form(None),
    context_path: Optional[str] = Form(None),
    query: Optional[str] = Query(
        "Provide a comprehensive game summary and analysis.",
        description="Analysis query if context is missing",
    ),
):
    """Upload a video file or provide a local path for processing."""

    final_video_path = None
    filename = "unknown"
    file_size = 0

    # 1. Handle Video Source
    if file:
        allowed_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        ext = Path(file.filename).suffix.lower()

        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {allowed_extensions}",
            )

        video_id = str(uuid.uuid4())
        filename = f"{video_id}{ext}"
        final_video_path = UPLOAD_DIR / filename

        with open(final_video_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        file_size = final_video_path.stat().st_size
        filename = file.filename  # Use original filename for specific display

    elif video_path:
        # Handle local path (assume mapped volume)
        # Map /home/fgpu -> /host/home/fgpu if needed
        p = video_path
        if p.startswith("/home/fgpu") and not p.startswith("/host"):
            p = "/host" + p

        final_video_path = Path(p)
        if not final_video_path.exists():
            raise HTTPException(status_code=404, detail=f"Video path not found: {video_path}")

        filename = final_video_path.name
        file_size = final_video_path.stat().st_size
    else:
        raise HTTPException(status_code=400, detail="Either 'file' or 'video_path' must be provided")

    try:
        # Create Video Record
        video = await video_service.create_video(
            filename=filename,
            file_path=str(final_video_path),
            file_size=file_size,
        )

        message = "Video uploaded successfully"

        # 2. Handle Context Source
        context_content = None

        if context:
            context_content = await context.read()
        elif context_path:
            # Resolve context path
            cp = context_path
            if cp.startswith("/home/fgpu") and not cp.startswith("/host"):
                cp = "/host" + cp
            cp_path = Path(cp)
            if cp_path.exists():
                with open(cp_path, "rb") as f:
                    context_content = f.read()
            else:
                logger.warning("Context path not found: %s", context_path)

        if context_content:
            try:
                context_data = json.loads(context_content)

                # Extract narrative/report
                narrative = context_data.get("chronological_narrative", "")
                if not narrative and "coaching_report" in context_data:
                    narrative = context_data["coaching_report"]

                if not narrative:
                    narrative = json.dumps(context_data, indent=2)

                async with get_db_context() as session:
                    analysis = Analysis(
                        video_id=video.id,
                        query="Uploaded Context",
                        analysis_type="uploaded_context",
                        status="completed",
                        coaching_report=narrative,
                        llm_model="user-uploaded",
                        vlm_model="user-uploaded",
                    )
                    session.add(analysis)
                    await session.commit()
                    message += " and context processed."
            except (OSError, ValueError, TypeError, RuntimeError) as e:
                logger.error("Failed to process context content: %s", e)
                message += f" but context processing failed: {e}"

        # 3. Trigger Auto-Analysis if no context
        if not context_content:
            background_tasks.add_task(video_service.analyze_video, video_id=video.id, query=query, analysis_type="general")
            message += ". Analysis started in background."

        return VideoUploadResponse(
            id=str(video.id),
            filename=video.filename,
            status=video.status,
            message=message,
        )
    except Exception as e:
        if file and final_video_path:  # Only cleanup if we uploaded it
            final_video_path.unlink(missing_ok=True)
        # If it was a path, don't delete it!
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload-path", response_model=VideoUploadResponse)
async def upload_video_from_path(path: str = Query(..., description="Path to video file")):
    """Process video from a file system path."""
    video_path = Path(path)

    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        video = await video_service.create_video(
            filename=video_path.name,
            file_path=str(video_path),
            file_size=video_path.stat().st_size,
        )

        return VideoUploadResponse(
            id=str(video.id),
            filename=video.filename,
            status=video.status,
            message="Video registered successfully",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("", response_model=list[VideoResponse])
async def list_videos(limit: int = Query(50, ge=1, le=100)):
    """List all uploaded videos."""
    videos = await video_service.list_videos(limit=limit)
    return [
        VideoResponse(
            id=str(v.id),
            filename=v.filename,
            duration_seconds=v.duration_seconds,
            frame_count=v.frame_count,
            width=v.width,
            height=v.height,
            fps=v.fps,
            status=v.status,
            created_at=v.created_at.isoformat() if v.created_at else "",
        )
        for v in videos
    ]


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: uuid.UUID):
    """Get video details by ID."""
    video = await video_service.get_video(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return VideoResponse(
        id=str(video.id),
        filename=video.filename,
        duration_seconds=video.duration_seconds,
        frame_count=video.frame_count,
        width=video.width,
        height=video.height,
        fps=video.fps,
        status=video.status,
        created_at=video.created_at.isoformat() if video.created_at else "",
    )


@router.post("/{video_id}/analyze", response_model=AnalysisResponse)
async def analyze_video(
    video_id: uuid.UUID,
    request: AnalysisRequest,
    _background_tasks: BackgroundTasks,
):
    """Run American Football analytics agent on video."""
    video = await video_service.get_video(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    analysis = await video_service.analyze_video(
        video_id=video_id,
        query=request.query,
        analysis_type=request.analysis_type,
    )

    return AnalysisResponse(
        id=str(analysis.id),
        video_id=str(analysis.video_id),
        query=analysis.query,
        analysis_type=analysis.analysis_type,
        status=analysis.status,
        coaching_report=analysis.coaching_report,
        duration_seconds=analysis.duration_seconds,
        error_message=analysis.error_message,
    )


@router.get("/{video_id}/analyses", response_model=list[AnalysisResponse])
async def list_video_analyses(
    video_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
):
    """List all analyses for a video."""
    analyses = await video_service.list_analyses(video_id=video_id, limit=limit)

    return [
        AnalysisResponse(
            id=str(a.id),
            video_id=str(a.video_id),
            query=a.query,
            analysis_type=a.analysis_type,
            status=a.status,
            coaching_report=a.coaching_report,
            duration_seconds=a.duration_seconds,
            error_message=a.error_message,
        )
        for a in analyses
    ]


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(analysis_id: uuid.UUID):
    """Get analysis by ID."""
    analysis = await video_service.get_analysis(analysis_id)

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return AnalysisResponse(
        id=str(analysis.id),
        video_id=str(analysis.video_id),
        query=analysis.query,
        analysis_type=analysis.analysis_type,
        status=analysis.status,
        coaching_report=analysis.coaching_report,
        duration_seconds=analysis.duration_seconds,
        error_message=analysis.error_message,
    )


@router.post("/analyze-path", response_model=AnalysisResponse)
async def analyze_video_by_path(request: DirectAnalysisRequest):
    """
    Analyze a video directly by file path (without uploading first).

    This is a convenience endpoint that combines upload and analysis in one step.
    """
    video_path = Path(request.path)

    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

    if not video_path.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {request.path}")

    allowed_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    if video_path.suffix.lower() not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {allowed_extensions}",
        )

    try:
        # Create video record
        video = await video_service.create_video(
            filename=video_path.name,
            file_path=str(video_path),
            file_size=video_path.stat().st_size,
        )

        # Run analysis
        analysis = await video_service.analyze_video(
            video_id=video.id,
            query=request.query,
            analysis_type=request.analysis_type,
        )

        return AnalysisResponse(
            id=str(analysis.id),
            video_id=str(analysis.video_id),
            query=analysis.query,
            analysis_type=analysis.analysis_type,
            status=analysis.status,
            coaching_report=analysis.coaching_report,
            duration_seconds=analysis.duration_seconds,
            error_message=analysis.error_message,
        )
    except Exception as e:
        logger.error("Direct analysis failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


class FolderAnalysisRequest(BaseModel):
    """Request to analyze all supported videos inside a folder."""

    folder_path: str
    query: str
    analysis_type: Literal["general", "offense", "defense", "red_zone", "matchups"] = "general"


class FolderAnalysisResponse(BaseModel):
    """Summary response for folder-wide analysis jobs."""

    total_videos: int
    processed: int
    failed: int
    results: list[AnalysisResponse]


@router.post("/analyze-folder", response_model=FolderAnalysisResponse)
async def analyze_videos_in_folder(request: FolderAnalysisRequest):
    """
    Analyze all videos in a folder.

    Processes all supported video files (.mp4, .mov, .avi, .mkv, .webm) in the specified folder.
    """
    folder_path = Path(request.folder_path)

    if not folder_path.exists():
        raise HTTPException(status_code=404, detail=f"Folder not found: {request.folder_path}")

    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a folder: {request.folder_path}")

    allowed_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    video_files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in allowed_extensions]

    if not video_files:
        raise HTTPException(status_code=404, detail=f"No video files found in folder: {request.folder_path}")

    results = []
    processed = 0
    failed = 0

    for video_path in video_files:
        try:
            # Create video record
            video = await video_service.create_video(
                filename=video_path.name,
                file_path=str(video_path),
                file_size=video_path.stat().st_size,
            )

            # Run analysis
            analysis = await video_service.analyze_video(
                video_id=video.id,
                query=request.query,
                analysis_type=request.analysis_type,
            )

            results.append(
                AnalysisResponse(
                    id=str(analysis.id),
                    video_id=str(analysis.video_id),
                    query=analysis.query,
                    analysis_type=analysis.analysis_type,
                    status=analysis.status,
                    coaching_report=analysis.coaching_report,
                    duration_seconds=analysis.duration_seconds,
                    error_message=analysis.error_message,
                )
            )

            if analysis.status == "completed":
                processed += 1
            else:
                failed += 1

        except (OSError, ValueError, TypeError, RuntimeError) as e:
            logger.error("Failed to analyze %s: %s", video_path, e)
            failed += 1

    return FolderAnalysisResponse(
        total_videos=len(video_files),
        processed=processed,
        failed=failed,
        results=results,
    )


class VideoDetailResponse(BaseModel):
    """Extended video metadata including analysis and cache estimates."""

    id: str
    filename: str
    original_path: str
    duration_seconds: Optional[float]
    frame_count: Optional[int]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    file_size_bytes: int
    status: str
    created_at: str
    thumbnail_url: Optional[str]
    token_estimate: int
    kv_cache_mb: float
    analyses: list[AnalysisResponse]


@router.get("/{video_id}/detail", response_model=VideoDetailResponse)
async def get_video_detail(video_id: uuid.UUID):
    """Get detailed video info including analyses and computed metrics."""
    video = await video_service.get_video(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get analyses
    analyses = await video_service.list_analyses(video_id=video_id, limit=10)

    # Calculate token estimate from analyses
    total_tokens = _estimate_tokens_from_analyses(analyses)

    # Calculate KV cache size (128 KB per token for Mistral-7B)
    kv_cache_bytes = total_tokens * KV_CACHE_BYTES_PER_TOKEN
    kv_cache_mb = kv_cache_bytes / (1024 * 1024)

    # Get file size
    file_size = 0
    if video.original_path:
        try:
            video_path = Path(video.original_path)
            if video_path.exists():
                file_size = video_path.stat().st_size
        except OSError:
            pass

    return VideoDetailResponse(
        id=str(video.id),
        filename=video.filename,
        original_path=video.original_path or "",
        duration_seconds=video.duration_seconds,
        frame_count=video.frame_count,
        width=video.width,
        height=video.height,
        fps=video.fps,
        file_size_bytes=file_size,
        status=video.status,
        created_at=video.created_at.isoformat() if video.created_at else "",
        thumbnail_url=f"/api/v1/videos/{video_id}/thumbnail",
        token_estimate=total_tokens,
        kv_cache_mb=round(kv_cache_mb, 2),
        analyses=[
            AnalysisResponse(
                id=str(a.id),
                video_id=str(a.video_id),
                query=a.query,
                analysis_type=a.analysis_type,
                status=a.status,
                coaching_report=a.coaching_report,
                duration_seconds=a.duration_seconds,
                error_message=a.error_message,
            )
            for a in analyses
        ],
    )


@router.get("/{video_id}/thumbnail")
async def get_video_thumbnail(video_id: uuid.UUID):  # pylint: disable=too-many-locals
    """Get or generate a thumbnail for the video."""

    video = await video_service.get_video(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.original_path:
        raise HTTPException(status_code=404, detail="Video path not available")

    # Check for existing thumbnail
    thumbnail_dir = Path(DATA_PATH) / "thumbnails"
    thumbnail_dir.mkdir(parents=True, exist_ok=True)
    thumbnail_path = thumbnail_dir / f"{video_id}.jpg"

    if not thumbnail_path.exists():
        # Generate thumbnail from video
        try:
            video_path = Path(video.original_path)
            if not video_path.exists():
                raise HTTPException(status_code=404, detail="Video file not found")

            cap = cv2.VideoCapture(str(video_path))

            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # Seek to 10% into the video for a good frame
            target_frame = max(1, int(total_frames * 0.1))
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

            ret, frame = cap.read()
            cap.release()

            if not ret:
                raise HTTPException(status_code=500, detail="Could not extract frame")

            # Resize to thumbnail size (320px width, maintain aspect ratio)
            height, width = frame.shape[:2]
            new_width = 320
            new_height = int(height * (new_width / width))
            thumbnail = cv2.resize(frame, (new_width, new_height))

            # Save thumbnail
            cv2.imwrite(str(thumbnail_path), thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 85])

        except Exception as e:
            logger.error("Failed to generate thumbnail: %s", e)
            raise HTTPException(
                status_code=500,
                detail=f"Thumbnail generation failed: {str(e)}",
            ) from e

    # Return thumbnail
    with open(thumbnail_path, "rb") as f:
        image_data = f.read()

    return Response(content=image_data, media_type="image/jpeg")


class VideoListDetailResponse(BaseModel):
    """Detailed list response with aggregate token and KV cache estimates."""

    videos: list[VideoDetailResponse]
    total_tokens: int
    total_kv_cache_mb: float


@router.get("/list/detailed", response_model=VideoListDetailResponse)
async def list_videos_detailed(limit: int = Query(20, ge=1, le=100)):
    """List all videos with detailed information including token estimates and KV cache sizes."""
    videos = await video_service.list_videos_with_analyses(limit=limit)

    detailed_videos = []
    total_tokens = 0

    for video in videos:
        # Use eagerly loaded analyses (already fetched in single query)
        analyses = video.analyses[:5]

        # Calculate tokens
        video_tokens = _estimate_tokens_from_analyses(analyses)

        total_tokens += video_tokens
        kv_cache_mb = (video_tokens * KV_CACHE_BYTES_PER_TOKEN) / (1024 * 1024)

        # Get file size
        file_size = 0
        if video.original_path:
            try:
                video_path = Path(video.original_path)
                if video_path.exists():
                    file_size = video_path.stat().st_size
            except OSError:
                pass

        detailed_videos.append(
            VideoDetailResponse(
                id=str(video.id),
                filename=video.filename,
                original_path=video.original_path or "",
                duration_seconds=video.duration_seconds,
                frame_count=video.frame_count,
                width=video.width,
                height=video.height,
                fps=video.fps,
                file_size_bytes=file_size,
                status=video.status,
                created_at=video.created_at.isoformat() if video.created_at else "",
                thumbnail_url=f"/api/v1/videos/{video.id}/thumbnail",
                token_estimate=video_tokens,
                kv_cache_mb=round(kv_cache_mb, 2),
                analyses=[
                    AnalysisResponse(
                        id=str(a.id),
                        video_id=str(a.video_id),
                        query=a.query,
                        analysis_type=a.analysis_type,
                        status=a.status,
                        coaching_report=a.coaching_report,
                        duration_seconds=a.duration_seconds,
                        error_message=a.error_message,
                    )
                    for a in analyses
                ],
            )
        )

    total_kv_cache_mb = (total_tokens * KV_CACHE_BYTES_PER_TOKEN) / (1024 * 1024)

    return VideoListDetailResponse(
        videos=detailed_videos,
        total_tokens=total_tokens,
        total_kv_cache_mb=round(total_kv_cache_mb, 2),
    )
