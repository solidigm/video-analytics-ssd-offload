# Created by Metrum AI for Solidigm

"""
Configuration for Video Analysis Deep Agent.
All agent configurations are centralized here.
"""

import os
import tempfile
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VLMConfig:
    """Vision Language Model configuration for video frame analysis."""

    model_name: str = "Qwen/Qwen3-VL-30B-A3B-Thinking"
    api_base_url: str = field(default_factory=lambda: os.getenv("VLM_API_URL", "http://vllm-vlm:8000/v1"))
    served_model_name: str = field(default_factory=lambda: os.getenv("VLM_MODEL", "Qwen/Qwen3-VL-30B-A3B-Thinking"))
    max_tokens: int = 1024  # Reduced to keep context manageable
    temperature: float = 0.3
    timeout: int = 300
    max_frames_per_request: int = 5


@dataclass
class LLMConfig:
    """Large Language Model configuration for reasoning and synthesis."""

    model_name: str = "aws-prototyping/MegaBeam-Mistral-7B-300k"
    api_base_url: str = field(default_factory=lambda: os.getenv("LLM_LMCACHE_URL", "http://vllm-lmcache:8000/v1"))
    served_model_name: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "aws-prototyping/MegaBeam-Mistral-7B-300k"))
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120


@dataclass
class SearchConfig:
    """Internet search configuration for deeper analysis."""

    tavily_api_key: Optional[str] = field(default_factory=lambda: os.getenv("TAVILY_API_KEY"))
    search_max_results: int = 5
    search_timeout: int = 30
    enable_web_search: bool = True
    enable_wikipedia: bool = True
    search_depth: str = "advanced"


@dataclass
class VideoProcessingConfig:
    """Video processing settings."""

    frame_interval_seconds: int = field(default_factory=lambda: int(os.getenv("FRAME_INTERVAL_SECONDS", "30")))
    max_frames_per_chunk: int = field(default_factory=lambda: int(os.getenv("MAX_FRAMES_PER_CHUNK", "15")))
    supported_formats: tuple = (".mp4", ".avi", ".mkv", ".mov", ".webm")
    temp_frames_dir: str = field(
        default_factory=lambda: os.getenv(
            "TEMP_FRAMES_DIR",
            os.path.join(tempfile.gettempdir(), "video_frames"),
        )
    )


@dataclass
class AgentConfig:
    """Main agent configuration combining all settings."""

    vlm: VLMConfig = field(default_factory=VLMConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    video: VideoProcessingConfig = field(default_factory=VideoProcessingConfig)
    search: SearchConfig = field(default_factory=SearchConfig)

    system_prompt: str = """You are an expert video analysis agent. Your capabilities include:

1. Video Understanding: Analyze video content frame by frame to understand scenes, actions, and context.
2. Temporal Reasoning: Track changes over time, identify patterns, and understand sequences of events.
3. Detailed Descriptions: Provide comprehensive descriptions of visual elements, movements, and interactions.
4. Question Answering: Answer specific questions about video content with accurate, grounded responses.

When analyzing videos:
- Extract key frames at regular intervals
- Analyze each frame for relevant visual information
- Synthesize findings across frames for temporal understanding
- Provide structured, actionable insights

Always base your analysis on the actual visual content. If something is unclear or not visible, state that explicitly."""

    analysis_prompts: dict = field(
        default_factory=lambda: {
            "general": """Analyze this video frame and describe:
1. Main subjects and their actions
2. Environment and setting
3. Notable objects or elements
4. Any text or signage visible
5. Overall mood or atmosphere""",
            "action": """Focus on actions and movements in this frame:
1. What actions are being performed?
2. Who is performing them?
3. What is the direction/trajectory of movement?
4. What might happen next based on current positions?""",
            "object_detection": """Identify and describe all significant objects:
1. List all visible objects
2. Describe their positions relative to each other
3. Note any interactions between objects
4. Identify any unusual or notable items""",
            "scene_understanding": """Provide comprehensive scene analysis:
1. What type of scene is this (indoor/outdoor, location type)?
2. What is the lighting condition?
3. What time of day does it appear to be?
4. What is the overall context of the scene?""",
            "temporal": """Considering this is frame {frame_num} of {total_frames}:
1. What has likely changed since the previous frame?
2. What continuity elements are visible?
3. What predictions can you make about upcoming frames?""",
        }
    )


def get_config() -> AgentConfig:
    """Get the agent configuration with environment overrides."""
    return AgentConfig()


VLLM_VLM_ARGS = {
    "model": "Qwen/Qwen3-VL-30B-A3B-Thinking",
    "served_model_name": "qwen3-vl-30b-a3b-thinking",
    "port": 8003,
    "max_model_len": 32768,
    "gpu_memory_utilization": 0.9,
    "tensor_parallel_size": 2,
    "trust_remote_code": True,
    "max_num_seqs": 8,
    "limit_mm_per_prompt": {"image": 10, "video": 1},
}

VLLM_LLM_ARGS = {
    "model": "aws-prototyping/MegaBeam-Mistral-7B-300k",
    "served_model_name": "megabeam-mistral-7b-300k",
    "port": 8004,
    "max_model_len": 32768,
    "gpu_memory_utilization": 0.9,
    "tensor_parallel_size": 2,
    "trust_remote_code": True,
    "enable_prefix_caching": True,
}
