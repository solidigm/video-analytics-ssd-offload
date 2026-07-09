# Created by Metrum AI for Solidigm

"""
Pipeline Orchestrator - Coordinates video processing, VLM analysis, and data generation.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from src.video_pipeline.video_processor import VideoProcessor, VideoChunk
from src.video_pipeline.vlm_analyzer import VLMAnalyzer, AnalysisResult
from src.video_pipeline.data_generator import DataGenerator
from src.video_pipeline.storage import AnalysisStorage

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:  # pylint: disable=too-many-instance-attributes
    """Runtime configuration for a full video-analysis pipeline run."""

    vlm_api_url: str = field(default_factory=lambda: os.getenv("VLM_API_URL", "http://vllm-vlm:8000/v1"))
    vlm_model: str = "Qwen/Qwen3-VL-30B-A3B-Thinking"
    llm_api_url: str = field(default_factory=lambda: os.getenv("LLM_BASELINE_URL", "http://vllm-baseline:8000/v1"))
    llm_model: str = "aws-prototyping/MegaBeam-Mistral-7B-300k"
    output_dir: str = "/data"
    frame_interval: int = 5
    chunk_duration_minutes: int = 5
    max_frames_per_chunk: int = 60
    parallel_frames: int = 4
    generate_followup_questions: bool = True
    followup_questions_per_analysis: int = 5
    run_deep_dive: bool = True


@dataclass
class PipelineStats:
    """Per-video pipeline execution counters and collected errors."""

    video_id: str
    total_chunks: int = 0
    total_frames: int = 0
    total_analyses: int = 0
    followup_questions_generated: int = 0
    errors: list = field(default_factory=list)


class VideoPipeline:
    """Orchestrates the complete video analysis pipeline."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self._init_components()

    def _init_components(self) -> None:
        """Initialize pipeline components."""
        self.processor = VideoProcessor(
            output_dir=self.config.output_dir,
            frame_interval=self.config.frame_interval,
            chunk_duration_minutes=self.config.chunk_duration_minutes,
            max_frames_per_chunk=self.config.max_frames_per_chunk,
        )
        self.vlm = VLMAnalyzer(
            api_url=self.config.vlm_api_url,
            model=self.config.vlm_model,
        )
        self.generator = DataGenerator(
            api_url=self.config.llm_api_url,
            model=self.config.llm_model,
        )
        self.storage = AnalysisStorage(base_path=os.path.join(self.config.output_dir, "analysis"))

    def process_video(self, video_path: str) -> PipelineStats:
        """Process a complete video through the pipeline."""
        video_id = Path(video_path).stem
        stats = PipelineStats(video_id=video_id)

        logger.info("Starting pipeline for video: %s", video_id)

        # Phase 1: Chunk video and extract frames
        chunks = self.processor.process_video(video_path)
        stats.total_chunks = len(chunks)
        logger.info("Created %s chunks", stats.total_chunks)

        # Phase 2: Process each chunk
        for chunk in chunks:
            try:
                chunk_stats = self._process_chunk(chunk, video_id)
                stats.total_frames += chunk_stats["frames"]
                stats.total_analyses += chunk_stats["analyses"]
                stats.followup_questions_generated += chunk_stats.get("followups", 0)
            except (OSError, ValueError, TypeError, RuntimeError) as e:
                logger.error("Error processing chunk %s: %s", chunk.chunk_id, e)
                stats.errors.append({"chunk": chunk.chunk_id, "error": str(e)})

        # Phase 3: Generate comparative analysis across chunks
        if stats.total_chunks > 1:
            self._generate_cross_chunk_analysis(video_id, chunks)

        # Finalize the consolidated file with word count naming
        final_path = self.storage.finalize_video_file(video_id)
        if final_path:
            logger.info("Final analysis file: %s", final_path)

        logger.info("Pipeline complete: %s analyses generated", stats.total_analyses)
        return stats

    def _process_chunk(self, chunk: VideoChunk, video_id: str) -> dict:
        """Process a single chunk through VLM analysis."""
        stats = {"frames": len(chunk.frame_paths), "analyses": 0, "followups": 0}

        logger.info("Processing chunk %s with %s frames", chunk.chunk_id, stats["frames"])

        all_analyses = []

        # Analyze each frame with all analysis types
        for idx, frame_path in enumerate(chunk.frame_paths):
            timestamp = chunk.start_time + (idx * self.config.frame_interval)
            frame_id = f"{chunk.chunk_id}_frame_{idx:04d}"

            # Run full analysis suite on frame
            analyses = self.vlm.run_full_analysis(frame_path, timestamp)

            for analysis in analyses:
                # Store each analysis
                self.storage.store_analysis(
                    video_id=video_id,
                    chunk_id=chunk.chunk_id,
                    frame_id=frame_id,
                    timestamp=timestamp,
                    analysis_type=analysis.analysis_type,
                    question=analysis.question,
                    response=analysis.response,
                    metadata=analysis.metadata,
                )
                stats["analyses"] += 1
                all_analyses.append(analysis)

            # Generate follow-up questions based on initial analysis
            if self.config.generate_followup_questions and analyses:
                followups = self._generate_and_answer_followups(analyses, frame_path, timestamp, video_id, chunk.chunk_id, frame_id)
                stats["analyses"] += followups
                stats["followups"] += followups

        # Deep dive on tactical themes if enabled
        if self.config.run_deep_dive and all_analyses:
            deep_stats = self._run_deep_dive_analysis(all_analyses, chunk, video_id)
            stats["analyses"] += deep_stats

        return stats

    def _generate_and_answer_followups(  # pylint: disable=too-many-arguments
        self,
        initial_analyses: list[AnalysisResult],
        frame_path: str,
        timestamp: float,
        video_id: str,
        chunk_id: str,
        frame_id: str,
    ) -> int:
        """Generate follow-up questions and answer them."""
        count = 0

        # Combine initial analyses for context
        combined_analysis = "\n\n".join(f"[{a.analysis_type}]: {a.response[:500]}" for a in initial_analyses)

        # Generate follow-up questions
        followups = self.generator.generate_followup_questions(
            previous_analysis=combined_analysis,
            num_questions=self.config.followup_questions_per_analysis,
        )

        # Answer each follow-up question with VLM
        for fq in followups:
            result = self.vlm.analyze_frame(
                frame_path=frame_path,
                question=fq.question,
                timestamp=timestamp,
                analysis_type=f"followup_{fq.category}",
            )

            self.storage.store_analysis(
                video_id=video_id,
                chunk_id=chunk_id,
                frame_id=frame_id,
                timestamp=timestamp,
                analysis_type=result.analysis_type,
                question=result.question,
                response=result.response,
                metadata={
                    **result.metadata,
                    "question_id": fq.question_id,
                    "priority": fq.priority,
                },
            )
            count += 1

        return count

    def _run_deep_dive_analysis(
        self,
        analyses: list[AnalysisResult],
        chunk: VideoChunk,
        video_id: str,
    ) -> int:
        """Run deep dive analysis on key tactical themes."""
        count = 0

        # Identify key topics from analyses
        topics = ["defensive shape", "attacking patterns", "transition moments"]

        # Use first frame for deep dive visualization
        if not chunk.frame_paths:
            return 0

        frame_path = chunk.frame_paths[0]
        combined_insights = "\n".join(a.response[:200] for a in analyses[:10])

        for topic in topics:
            questions = self.generator.generate_deep_dive_questions(
                topic=topic,
                existing_insights=combined_insights,
                num_questions=5,
            )

            for q in questions:
                result = self.vlm.analyze_frame(
                    frame_path=frame_path,
                    question=q.question,
                    timestamp=chunk.start_time,
                    analysis_type=f"deep_dive_{topic.replace(' ', '_')}",
                )

                self.storage.store_analysis(
                    video_id=video_id,
                    chunk_id=chunk.chunk_id,
                    frame_id=f"{chunk.chunk_id}_deepdive",
                    timestamp=chunk.start_time,
                    analysis_type=result.analysis_type,
                    question=result.question,
                    response=result.response,
                    metadata=result.metadata,
                )
                count += 1

        return count

    def _generate_cross_chunk_analysis(self, video_id: str, chunks: list[VideoChunk]) -> None:
        """Generate comparative analysis across multiple chunks."""
        logger.info("Generating cross-chunk comparative analysis")

        # Get summaries from each chunk
        frame_analyses = []
        for chunk in chunks[:10]:  # Limit to first 10 chunks
            chunk_data = self.storage.get_chunk_analyses(video_id, chunk.chunk_id)
            if chunk_data:
                frame_analyses.append(
                    {
                        "timestamp": chunk.start_time,
                        "summary": chunk_data[:500],
                    }
                )

        if len(frame_analyses) < 2:
            return

        # Generate comparative questions
        comparative_qs = self.generator.generate_comparative_questions(
            frame_analyses=frame_analyses,
            num_questions=10,
        )

        # Use middle chunk frame for visualization
        mid_chunk = chunks[len(chunks) // 2]
        if mid_chunk.frame_paths:
            frame_path = mid_chunk.frame_paths[0]

            for q in comparative_qs:
                result = self.vlm.analyze_frame(
                    frame_path=frame_path,
                    question=q.question,
                    timestamp=mid_chunk.start_time,
                    analysis_type="cross_chunk_comparative",
                )

                self.storage.store_analysis(
                    video_id=video_id,
                    chunk_id="cross_chunk",
                    frame_id="comparative",
                    timestamp=mid_chunk.start_time,
                    analysis_type=result.analysis_type,
                    question=result.question,
                    response=result.response,
                    metadata=result.metadata,
                )

    def get_video_data(self, video_id: str) -> Optional[dict]:
        """Get all analysis data for a video."""
        return self.storage.get_video_summary(video_id)

    def export_video_data(self, video_id: str, output_path: Optional[str] = None) -> str:
        """Export video analysis data to a file."""
        return self.storage.export_video_data(video_id, output_path)

    def close(self) -> None:
        """Close all resources."""
        self.vlm.close()
        self.generator.close()
