# Created by Metrum AI for Solidigm

"""
Video Processor - Frame extraction and video chunking for sports analytics.
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Generator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VideoChunk:
    """Chunk metadata and extracted frame paths for one video segment."""

    chunk_id: str
    video_path: str
    start_time: float
    end_time: float
    frame_paths: list[str]
    metadata: dict


@dataclass
class FrameData:
    """Normalized frame metadata used by downstream analyzers."""

    frame_id: str
    frame_path: str
    timestamp: float
    chunk_id: str


class VideoProcessor:
    """Processes video files for VLM analysis."""

    def __init__(
        self,
        output_dir: str,
        frame_interval: int = 5,
        chunk_duration_minutes: int = 5,
        max_frames_per_chunk: int = 60,
    ):
        self.output_dir = Path(output_dir)
        self.frame_interval = frame_interval
        self.chunk_duration = chunk_duration_minutes * 60
        self.max_frames_per_chunk = max_frames_per_chunk
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.frames_dir = self.output_dir / "frames"
        self.chunks_dir = self.output_dir / "chunks"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

    def get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds using ffprobe."""
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ValueError(f"Failed to probe video: {result.stderr}")
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])

    def get_video_metadata(self, video_path: str) -> dict:
        """Extract comprehensive video metadata."""
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format:stream",
            "-of",
            "json",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ValueError(f"Failed to get metadata: {result.stderr}")
        return json.loads(result.stdout)

    def extract_frames(  # pylint: disable=too-many-locals
        self,
        video_path: str,
        video_id: str,
        start_time: float = 0,
        end_time: float = None,
    ) -> list[FrameData]:
        """Extract frames at specified intervals."""
        duration = self.get_video_duration(video_path)
        end_time = end_time or duration

        chunk_id = f"{video_id}_{int(start_time)}_{int(end_time)}"
        chunk_frames_dir = self.frames_dir / chunk_id
        chunk_frames_dir.mkdir(parents=True, exist_ok=True)

        # Calculate frame extraction rate
        total_seconds = end_time - start_time
        estimated_frames = int(total_seconds / self.frame_interval)
        actual_frames = min(estimated_frames, self.max_frames_per_chunk)
        adjusted_interval = total_seconds / actual_frames if actual_frames > 0 else self.frame_interval

        # FFmpeg command for frame extraction
        output_pattern = str(chunk_frames_dir / "frame_%04d.jpg")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_time),
            "-to",
            str(end_time),
            "-i",
            video_path,
            "-vf",
            f"fps=1/{adjusted_interval}",
            "-q:v",
            "2",
            output_pattern,
        ]

        logger.info("Extracting frames from %ss to %ss", start_time, end_time)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error("Frame extraction failed: %s", result.stderr)
            raise RuntimeError(f"FFmpeg error: {result.stderr}")

        # Collect extracted frames
        frames = []
        for idx, frame_file in enumerate(sorted(chunk_frames_dir.glob("frame_*.jpg"))):
            timestamp = start_time + (idx * adjusted_interval)
            frames.append(
                FrameData(
                    frame_id=f"{chunk_id}_frame_{idx:04d}",
                    frame_path=str(frame_file),
                    timestamp=timestamp,
                    chunk_id=chunk_id,
                )
            )

        logger.info("Extracted %s frames for chunk %s", len(frames), chunk_id)
        return frames

    def chunk_video(self, video_path: str, video_id: str) -> Generator[VideoChunk, None, None]:
        """Split video into processable chunks with extracted frames."""
        duration = self.get_video_duration(video_path)
        metadata = self.get_video_metadata(video_path)

        chunk_count = 0
        current_time = 0.0

        while current_time < duration:
            end_time = min(current_time + self.chunk_duration, duration)
            chunk_id = f"{video_id}_chunk_{chunk_count:03d}"

            logger.info(
                "Processing chunk %s: %ss - %ss",
                chunk_id,
                current_time,
                end_time,
            )

            # Extract frames for this chunk
            frames = self.extract_frames(video_path, video_id, current_time, end_time)

            yield VideoChunk(
                chunk_id=chunk_id,
                video_path=video_path,
                start_time=current_time,
                end_time=end_time,
                frame_paths=[f.frame_path for f in frames],
                metadata={
                    "duration": end_time - current_time,
                    "frame_count": len(frames),
                    "video_metadata": metadata,
                },
            )

            current_time = end_time
            chunk_count += 1

        logger.info("Video split into %s chunks", chunk_count)

    def process_video(self, video_path: str) -> list[VideoChunk]:
        """Process entire video and return all chunks."""
        video_id = Path(video_path).stem
        return list(self.chunk_video(video_path, video_id))
