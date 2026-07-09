# Created by Metrum AI for Solidigm

"""
VLM Analyzer - Vision Language Model integration for sports video analysis.
"""

import base64
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Standardized response container for single-frame VLM inference."""

    frame_path: str
    timestamp: float
    analysis_type: str
    question: str
    response: str
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)


class VLMAnalyzer:
    """Analyze video frames using Vision Language Models via OpenAI-compatible API."""

    # Comprehensive analysis prompts for sports video
    ANALYSIS_PROMPTS = {
        "scene_overview": """Analyze this sports video frame and provide a comprehensive scene description:
1. What sport is being played?
2. What is the current game situation (attack, defense, transition)?
3. Describe the visible players' positions on the field/court
4. What tactical formation appears to be in use?
5. Describe any notable visual elements (scoreboard, crowd, weather)""",
        "player_positions": """Analyze player positions in this frame:
1. Identify the approximate number of players visible
2. Describe their spatial distribution (clustered, spread, formation)
3. Which players appear to be in offensive vs defensive positions?
4. Are there any isolated players or numerical advantages visible?
5. Describe the positioning relative to the goal/basket/objective""",
        "tactical_analysis": """Provide tactical analysis of this frame:
1. What tactical pattern or play appears to be developing?
2. Identify potential passing lanes or movement options
3. What defensive structure is visible?
4. Are there any tactical vulnerabilities or opportunities?
5. What would be the optimal next action for the attacking team?""",
        "movement_analysis": """Analyze player movement patterns:
1. Which direction are players generally moving?
2. Are there coordinated movement patterns visible?
3. Identify any pressing or counter-pressing movements
4. Describe off-the-ball movement of key players
5. What running patterns suggest about the team's strategy?""",
        "ball_analysis": """Analyze ball position and possession:
1. Where is the ball located in the frame?
2. Which team appears to have possession?
3. What phase of play is indicated (build-up, attack, transition)?
4. Describe the immediate passing options available
5. What is the likely next action with the ball?""",
        "formation_detection": """Detect and analyze team formations:
1. What formation does the home/attacking team appear to use?
2. What formation does the away/defending team appear to use?
3. How are the formations interacting?
4. Are there any formation shifts or adjustments visible?
5. What tactical matchups are created by these formations?""",
        "key_moment": """Identify if this is a key moment in the game:
1. Is this a goal-scoring opportunity?
2. Is this a defensive crisis or counter-attack?
3. Rate the danger level (1-10) for the attacking team
4. What makes this moment tactically significant?
5. What decision needs to be made by the player on the ball?""",
        "space_analysis": """Analyze spatial dynamics:
1. Where are the largest open spaces on the field?
2. Which zones are congested with players?
3. Are there exploitable gaps in the defensive line?
4. Describe the width and depth of the attacking shape
5. How compact or stretched is the defensive block?""",
    }

    def __init__(
        self,
        api_url: str = os.getenv("VLM_API_URL", "http://vllm-vlm:8000/v1"),
        model: str = "Qwen/Qwen3-VL-30B-A3B-Thinking",
        timeout: int = 120,
    ):
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _get_image_mime_type(self, image_path: str) -> str:
        """Get MIME type from image extension."""
        ext = Path(image_path).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_types.get(ext, "image/jpeg")

    def analyze_frame(
        self,
        frame_path: str,
        question: str,
        timestamp: float = 0.0,
        analysis_type: str = "custom",
    ) -> AnalysisResult:
        """Analyze a single frame with a specific question."""
        logger.info(
            "Analyzing frame: %s with question type: %s",
            frame_path,
            analysis_type,
        )

        image_data = self._encode_image(frame_path)
        mime_type = self._get_image_mime_type(frame_path)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                        },
                        {
                            "type": "text",
                            "text": question,
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.3,
        }

        try:
            response = self.client.post(
                f"{self.api_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            content = result["choices"][0]["message"]["content"]
            # Strip Qwen3 thinking blocks before storing
            content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL).strip()
            usage = result.get("usage", {})

            return AnalysisResult(
                frame_path=frame_path,
                timestamp=timestamp,
                analysis_type=analysis_type,
                question=question,
                response=content,
                confidence=0.9,
                metadata={
                    "model": self.model,
                    "tokens_used": usage.get("total_tokens", 0),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                },
            )
        except httpx.HTTPError as e:
            logger.error("VLM API error: %s", e)
            return AnalysisResult(
                frame_path=frame_path,
                timestamp=timestamp,
                analysis_type=analysis_type,
                question=question,
                response=f"Error: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e)},
            )

    def run_full_analysis(self, frame_path: str, timestamp: float = 0.0) -> list[AnalysisResult]:
        """Run all analysis types on a single frame."""
        results = []
        for analysis_type, prompt in self.ANALYSIS_PROMPTS.items():
            result = self.analyze_frame(
                frame_path=frame_path,
                question=prompt,
                timestamp=timestamp,
                analysis_type=analysis_type,
            )
            results.append(result)
            logger.info("Completed %s analysis for %s", analysis_type, frame_path)
        return results

    def analyze_frame_batch(
        self,
        frames: list[dict],
        analysis_types: Optional[list[str]] = None,
    ) -> list[AnalysisResult]:
        """Analyze multiple frames with specified analysis types."""
        if analysis_types is None:
            analysis_types = list(self.ANALYSIS_PROMPTS.keys())

        results = []
        for frame in frames:
            frame_path = frame["path"]
            timestamp = frame.get("timestamp", 0.0)

            for analysis_type in analysis_types:
                prompt = self.ANALYSIS_PROMPTS.get(analysis_type)
                if prompt:
                    result = self.analyze_frame(
                        frame_path=frame_path,
                        question=prompt,
                        timestamp=timestamp,
                        analysis_type=analysis_type,
                    )
                    results.append(result)

        return results

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
