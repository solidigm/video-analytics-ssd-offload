# Created by Metrum AI for Solidigm

"""
Storage - Persist analysis data to structured text files.
Naming convention: videofilename_no_of_words_xxx.txt
All queries for a single video are written to one consolidated file.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AnalysisRecord:  # pylint: disable=too-many-instance-attributes
    """Single persisted unit of analysis output for one frame/question pair."""

    video_id: str
    chunk_id: str
    frame_id: str
    timestamp: float
    analysis_type: str
    question: str
    response: str
    metadata: dict
    created_at: str


class AnalysisStorage:  # pylint: disable=too-many-instance-attributes
    """
    Store and retrieve analysis data from structured text files.

    File naming: {video_filename}_no_of_words_{word_count}.txt
    All analyses for a single video consolidated into one file.
    """

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._word_counts = {}
        self._init_index()

    def _init_index(self) -> None:
        """Initialize or load the analysis index."""
        self.index_path = self.base_path / "index.json"
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                self.index = json.load(f)
        else:
            self.index = {
                "videos": {},
                "total_analyses": 0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            self._save_index()

    def _save_index(self) -> None:
        """Persist the index to disk."""
        self.index["updated_at"] = datetime.now().isoformat()
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2)

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())

    def _get_video_file_path(self, video_id: str) -> Path:
        """
        Get the consolidated file path for a video.
        Updates word count in filename as content grows.
        """
        return self.base_path / video_id

    def _get_current_word_count(self, video_id: str) -> int:
        """Get current total word count for video."""
        return self._word_counts.get(video_id, 0)

    def _generate_filename(self, video_id: str, word_count: int) -> str:
        """Generate filename with word count: videofilename_no_of_words_xxx.txt"""
        return f"{video_id}_no_of_words_{word_count}.txt"

    def _update_file_with_word_count(self, video_id: str) -> Path:
        """Update filename to reflect current word count."""
        video_dir = self._get_video_file_path(video_id)
        video_dir.mkdir(parents=True, exist_ok=True)

        word_count = self._get_current_word_count(video_id)
        filename = self._generate_filename(video_id, word_count)

        return video_dir / filename

    def store_analysis(  # pylint: disable=too-many-arguments
        self,
        video_id: str,
        chunk_id: str,
        frame_id: str,
        timestamp: float,
        analysis_type: str,
        question: str,
        response: str,
        metadata: Optional[dict] = None,
    ) -> AnalysisRecord:
        """Store a single analysis record to consolidated video file."""
        record = AnalysisRecord(
            video_id=video_id,
            chunk_id=chunk_id,
            frame_id=frame_id,
            timestamp=timestamp,
            analysis_type=analysis_type,
            question=question,
            response=response,
            metadata=metadata or {},
            created_at=datetime.now().isoformat(),
        )

        # Format the record content
        record_content = self._format_record(record)
        record_words = self._count_words(record_content)

        # Update word count
        if video_id not in self._word_counts:
            self._word_counts[video_id] = 0
        self._word_counts[video_id] += record_words

        # Ensure word-count-specific output path is tracked.
        self._update_file_with_word_count(video_id)
        video_dir = self._get_video_file_path(video_id)

        # Append to the consolidated file (or create new)
        consolidated_file = video_dir / f"{video_id}_consolidated.txt"

        with open(consolidated_file, "a", encoding="utf-8") as f:
            f.write(record_content)
            f.write("\n" + "=" * 80 + "\n\n")

        # Update index
        if video_id not in self.index["videos"]:
            self.index["videos"][video_id] = {
                "chunks": [],
                "analysis_count": 0,
                "word_count": 0,
                "created_at": datetime.now().isoformat(),
            }
        if chunk_id not in self.index["videos"][video_id]["chunks"]:
            self.index["videos"][video_id]["chunks"].append(chunk_id)

        self.index["videos"][video_id]["analysis_count"] += 1
        self.index["videos"][video_id]["word_count"] = self._word_counts[video_id]
        self.index["total_analyses"] += 1
        self._save_index()

        logger.info(
            "Stored analysis: %s/%s (total words: %s)",
            video_id,
            analysis_type,
            self._word_counts[video_id],
        )
        return record

    def _format_record(self, record: AnalysisRecord) -> str:
        """Format record as human-readable text."""
        lines = [
            "ANALYSIS RECORD",
            "---------------",
            f"Video ID: {record.video_id}",
            f"Chunk ID: {record.chunk_id}",
            f"Frame ID: {record.frame_id}",
            f"Timestamp: {record.timestamp:.2f}s",
            f"Analysis Type: {record.analysis_type}",
            f"Created At: {record.created_at}",
            "",
            "QUESTION:",
            f"{record.question}",
            "",
            "RESPONSE:",
            f"{record.response}",
            "",
            "METADATA:",
            f"{json.dumps(record.metadata, indent=2)}",
        ]
        return "\n".join(lines)

    def store_batch(
        self,
        video_id: str,
        analyses: list[dict],
    ) -> list[AnalysisRecord]:
        """Store multiple analysis records to consolidated file."""
        records = []
        for analysis in analyses:
            record = self.store_analysis(
                video_id=video_id,
                chunk_id=analysis.get("chunk_id", "unknown"),
                frame_id=analysis.get("frame_id", "unknown"),
                timestamp=analysis.get("timestamp", 0.0),
                analysis_type=analysis.get("analysis_type", "unknown"),
                question=analysis.get("question", ""),
                response=analysis.get("response", ""),
                metadata=analysis.get("metadata"),
            )
            records.append(record)
        return records

    def finalize_video_file(self, video_id: str) -> str:
        """
        Finalize the video analysis file with proper naming.
        Creates: videofilename_no_of_words_xxx.txt
        """
        video_dir = self._get_video_file_path(video_id)
        consolidated_file = video_dir / f"{video_id}_consolidated.txt"

        if not consolidated_file.exists():
            return None

        word_count = self._word_counts.get(video_id, 0)
        final_filename = self._generate_filename(video_id, word_count)
        final_path = video_dir / final_filename

        # Rename consolidated to final filename
        if consolidated_file.exists():
            # Remove old word count files
            for old_file in video_dir.glob(f"{video_id}_no_of_words_*.txt"):
                old_file.unlink()

            # Rename to new filename
            consolidated_file.rename(final_path)
            logger.info("Finalized video file: %s", final_path)

        return str(final_path)

    def get_video_summary(self, video_id: str) -> Optional[dict]:
        """Get summary of all analyses for a video."""
        if video_id not in self.index["videos"]:
            return None

        video_info = self.index["videos"][video_id]
        return {
            "video_id": video_id,
            "chunk_count": len(video_info["chunks"]),
            "analysis_count": video_info["analysis_count"],
            "word_count": video_info.get("word_count", 0),
            "created_at": video_info["created_at"],
            "chunks": video_info["chunks"],
        }

    def get_chunk_analyses(self, video_id: str, chunk_id: str) -> Optional[str]:
        """Get all analyses for a specific chunk from consolidated file."""
        video_dir = self._get_video_file_path(video_id)

        # Try consolidated file first
        consolidated_file = video_dir / f"{video_id}_consolidated.txt"
        if consolidated_file.exists():
            with open(consolidated_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Filter for chunk_id
                sections = content.split("=" * 80)
                chunk_sections = [s for s in sections if f"Chunk ID: {chunk_id}" in s]
                return "\n".join(chunk_sections)

        # Try final named file
        for file_path in video_dir.glob(f"{video_id}_no_of_words_*.txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                sections = content.split("=" * 80)
                chunk_sections = [s for s in sections if f"Chunk ID: {chunk_id}" in s]
                return "\n".join(chunk_sections)

        return None

    def get_all_video_data(self, video_id: str) -> Optional[str]:
        """Get all analysis data for a video from consolidated file."""
        video_dir = self._get_video_file_path(video_id)

        # Try consolidated file first
        consolidated_file = video_dir / f"{video_id}_consolidated.txt"
        if consolidated_file.exists():
            with open(consolidated_file, "r", encoding="utf-8") as f:
                return f.read()

        # Try final named file
        for file_path in video_dir.glob(f"{video_id}_no_of_words_*.txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        return None

    def export_video_data(self, video_id: str, output_path: Optional[str] = None) -> str:
        """Export all analysis data for a video to a single file."""
        if video_id not in self.index["videos"]:
            raise ValueError(f"Video {video_id} not found in index")

        video_info = self.index["videos"][video_id]
        word_count = video_info.get("word_count", self._word_counts.get(video_id, 0))

        if output_path is None:
            output_path = str(self.base_path / self._generate_filename(video_id, word_count))

        # Get all data from consolidated file
        all_data = self.get_all_video_data(video_id)

        with open(output_path, "w", encoding="utf-8") as out:
            out.write("VIDEO ANALYSIS EXPORT\n")
            out.write(f"{'=' * 80}\n")
            out.write(f"Video ID: {video_id}\n")
            out.write(f"Export Date: {datetime.now().isoformat()}\n")
            out.write(f"Total Chunks: {len(video_info['chunks'])}\n")
            out.write(f"Total Analyses: {video_info['analysis_count']}\n")
            out.write(f"Total Words: {word_count}\n")
            out.write(f"{'=' * 80}\n\n")

            if all_data:
                out.write(all_data)

        logger.info("Exported video %s to %s", video_id, output_path)
        return output_path

    def search_analyses(self, video_id: str, keyword: str) -> list[str]:
        """Search for keyword in video analyses."""
        results = []
        all_data = self.get_all_video_data(video_id)

        if all_data and keyword.lower() in all_data.lower():
            results.append(video_id)

        return results

    def get_all_videos(self) -> list[dict]:
        """Get list of all processed videos."""
        return [
            {
                "video_id": vid,
                "analysis_count": info["analysis_count"],
                "chunk_count": len(info["chunks"]),
                "word_count": info.get("word_count", 0),
            }
            for vid, info in self.index["videos"].items()
        ]
