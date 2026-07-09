# Created by Metrum AI for Solidigm

"""
Video extraction and metadata tools for American Football game analysis.
"""

# pylint: disable=no-member

import os
from pathlib import Path

import cv2

from src.agents.config import get_config
from src.agents.telemetry import trace_tool


def extract_game_frames(  # pylint: disable=too-many-locals
    video_path: str,
    interval_seconds: float = 60.0,
    max_frames: int = 8,
    focus_on_plays: bool = True,
) -> dict:
    """
    Extract frames from an American Football game video optimized for play analysis.

    Args:
        video_path: Path to the American Football game video file
        interval_seconds: Seconds between frame extractions (default: 60.0)
        max_frames: Maximum number of frames to extract (default: 8)
        focus_on_plays: If True, attempts to capture play snapshots

    Returns:
        Dictionary with extracted frames for tactical analysis
    """
    with trace_tool(
        "extract_game_frames",
        video_path=video_path,
        max_frames=max_frames,
        focus_on_plays=focus_on_plays,
    ):
        config = get_config()
        temp_dir = Path(config.video.temp_frames_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        video_path = Path(video_path)
        if not video_path.exists():
            return {"error": f"Game video not found: {video_path}"}

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {"error": f"Failed to open game video: {video_path}"}

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames_count / fps if fps > 0 else 0
        frame_interval = int(fps * interval_seconds)

        frames = []
        frame_idx = 0
        extracted_count = 0

        session_dir = temp_dir / f"american_football_session_{os.getpid()}"
        session_dir.mkdir(parents=True, exist_ok=True)

        while cap.isOpened() and extracted_count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / fps
                frame_path = session_dir / f"play_frame_{extracted_count:04d}.jpg"
                cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

                frames.append(
                    {
                        "path": str(frame_path),
                        "timestamp": round(timestamp, 2),
                        "frame_number": extracted_count + 1,
                        "game_time_approx": f"{int(timestamp//60)}:{int(timestamp%60):02d}",
                    }
                )
                extracted_count += 1

            frame_idx += 1

        cap.release()

        return {
            "success": True,
            "video_path": str(video_path),
            "duration_seconds": round(duration, 2),
            "duration_formatted": f"{int(duration//60)}:{int(duration%60):02d}",
            "total_frames_extracted": len(frames),
            "frames": frames,
        }


def get_game_video_info(video_path: str) -> dict:
    """
    Get metadata about an American Football game video file.

    Args:
        video_path: Path to the game video

    Returns:
        Video metadata optimized for game analysis
    """
    video_path = Path(video_path)
    if not video_path.exists():
        return {"error": f"Game video not found: {video_path}"}

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"error": f"Failed to open game video: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    cap.release()

    return {
        "video_path": str(video_path),
        "duration_seconds": round(duration, 2),
        "duration_formatted": f"{int(duration//60)}:{int(duration%60):02d}",
        "fps": round(fps, 2),
        "resolution": {"width": width, "height": height},
        "quality": "HD" if height >= 720 else "SD",
        "total_frames": total_frames,
        "estimated_plays": int(duration / 40),
        "file_size_mb": round(video_path.stat().st_size / (1024 * 1024), 2),
    }


def cleanup_analysis_frames(frame_paths: list[str]) -> dict:
    """Clean up extracted frame files after analysis."""
    deleted = 0
    for path in frame_paths:
        try:
            Path(path).unlink(missing_ok=True)
            deleted += 1
        except OSError:
            pass
    return {"deleted_count": deleted}
