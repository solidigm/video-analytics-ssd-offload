# Created by Metrum AI for Solidigm

"""
Data Generator - LLM-driven question generation for maximizing data extraction.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GeneratedQuestion:
    """Structured representation of a generated analysis question."""

    question_id: str
    question: str
    category: str
    priority: int
    context_required: str
    expected_detail_level: str


class DataGenerator:
    """Generate tactical questions using LLM to maximize data extraction from video analysis."""

    # Base question templates for different sports contexts
    QUESTION_CATEGORIES = {
        "tactical": [
            "What tactical adjustments should the {team} make based on this situation?",
            "How is the {team} exploiting or defending against the opponent's formation?",
            "What set piece or play pattern is being executed here?",
            "Analyze the pressing trigger points visible in this frame.",
            "What defensive transition patterns are evident?",
        ],
        "player_specific": [
            "What role is the {position} player performing in this tactical setup?",
            "Analyze the decision-making of the player on the ball.",
            "What off-the-ball movements are most impactful in this situation?",
            "Rate the positioning of the defensive line players.",
            "What anticipatory movements indicate next actions?",
        ],
        "spatial": [
            "Map the heat zones of player density in this frame.",
            "Where are the most dangerous attacking spaces?",
            "Analyze the compactness of the defensive block.",
            "What channels are available for through balls?",
            "Describe the width utilization by the attacking team.",
        ],
        "temporal": [
            "What happened in the moments leading to this frame?",
            "What is the likely sequence of events in the next 5 seconds?",
            "How has the tactical shape evolved from the previous situation?",
            "What counter-attacking opportunities are developing?",
            "Predict the outcome of the current attacking move.",
        ],
        "comparative": [
            "Compare the formations of both teams visible in this frame.",
            "How does the current setup differ from typical patterns for this team?",
            "What numerical advantages or disadvantages exist in key zones?",
            "Compare offensive and defensive transition speeds.",
            "Analyze the pressing intensity versus the opponent's build-up style.",
        ],
        "statistical": [
            "Estimate the xG (expected goals) potential of this situation.",
            "What is the approximate passing completion probability here?",
            "Rate the defensive vulnerability on a 1-10 scale.",
            "Assess the transition speed index visible in this frame.",
            "Calculate approximate distances between defensive line players.",
        ],
    }

    # System prompt for LLM question generation
    SYSTEM_PROMPT = """You are a sports analytics expert specializing in tactical analysis.
Your task is to generate insightful questions that will extract maximum tactical information
from video frames of sports matches.

Generate questions that are:
1. Specific and actionable
2. Focused on tactical patterns, player movements, and spatial dynamics
3. Varied in perspective (offensive, defensive, transitional)
4. Graduated in complexity (basic observations to advanced tactical insights)

Always return questions in a structured format."""

    def __init__(
        self,
        api_url: str = os.getenv("LLM_BASELINE_URL", "http://vllm-baseline:8000/v1"),
        model: str = "aws-prototyping/MegaBeam-Mistral-7B-300k",
        timeout: int = 60,
    ):
        self.api_url = api_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def get_base_questions(self, sport: str = "soccer") -> list[GeneratedQuestion]:
        """Get predefined base questions for analysis."""
        questions = []
        question_id = 0

        for category, templates in self.QUESTION_CATEGORIES.items():
            for priority, template in enumerate(templates):
                question = template.format(
                    team=f"{sport} attacking team",
                    position="central midfielder",
                )
                questions.append(
                    GeneratedQuestion(
                        question_id=f"base_{question_id:04d}",
                        question=question,
                        category=category,
                        priority=priority + 1,
                        context_required="single_frame",
                        expected_detail_level="detailed",
                    )
                )
                question_id += 1

        return questions

    def generate_followup_questions(
        self,
        previous_analysis: str,
        context: Optional[str] = None,
        num_questions: int = 5,
    ) -> list[GeneratedQuestion]:
        """Use LLM to generate follow-up questions based on previous analysis."""
        prompt = f"""Based on the following analysis of a sports video frame, generate {num_questions}
follow-up questions that would extract additional tactical insights.

Previous Analysis:
{previous_analysis}

{f'Additional Context: {context}' if context else ''}

Generate questions that:
1. Dig deeper into observations mentioned in the analysis
2. Explore aspects not covered in the initial analysis
3. Connect tactical patterns to team strategy
4. Quantify or rate aspects of play
5. Predict outcomes or suggest alternatives

Return the questions as a numbered list, one per line."""

        try:
            response = self.client.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 512,
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Parse questions from response
            questions = []
            for idx, line in enumerate(content.strip().split("\n")):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    # Remove numbering or bullet
                    clean_q = line.lstrip("0123456789.-) ").strip()
                    if clean_q:
                        questions.append(
                            GeneratedQuestion(
                                question_id=f"followup_{idx:04d}",
                                question=clean_q,
                                category="followup",
                                priority=idx + 1,
                                context_required="previous_analysis",
                                expected_detail_level="detailed",
                            )
                        )

            return questions[:num_questions]

        except httpx.HTTPError as e:
            logger.error("LLM API error generating questions: %s", e)
            return []

    def generate_comparative_questions(
        self,
        frame_analyses: list[dict],
        num_questions: int = 5,
    ) -> list[GeneratedQuestion]:
        """Generate questions that compare multiple frames for temporal analysis."""
        summaries = []
        for idx, analysis in enumerate(frame_analyses[:5]):
            summaries.append(f"Frame {idx + 1} ({analysis.get('timestamp', 0)}s): " f"{analysis.get('summary', '')[:200]}")

        prompt = f"""Given analyses from multiple consecutive frames of a sports match,
generate {num_questions} questions that explore the temporal evolution and patterns.

Frame Summaries:
{chr(10).join(summaries)}

Generate questions that:
1. Compare tactical changes between frames
2. Identify movement patterns over time
3. Analyze the development of attacking/defensive plays
4. Track specific player movements across frames
5. Predict the outcome of developing situations

Return questions as a numbered list."""

        try:
            response = self.client.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 512,
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            questions = []
            for idx, line in enumerate(content.strip().split("\n")):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    clean_q = line.lstrip("0123456789.-) ").strip()
                    if clean_q:
                        questions.append(
                            GeneratedQuestion(
                                question_id=f"comparative_{idx:04d}",
                                question=clean_q,
                                category="comparative",
                                priority=idx + 1,
                                context_required="multi_frame",
                                expected_detail_level="comprehensive",
                            )
                        )

            return questions[:num_questions]

        except httpx.HTTPError as e:
            logger.error("LLM API error generating comparative questions: %s", e)
            return []

    def generate_deep_dive_questions(
        self,
        topic: str,
        existing_insights: str,
        num_questions: int = 10,
    ) -> list[GeneratedQuestion]:
        """Generate deep-dive questions on a specific tactical topic."""
        prompt = f"""Generate {num_questions} in-depth analytical questions about: {topic}

Existing insights to build upon:
{existing_insights[:1000]}

Generate increasingly specific questions that:
1. Start with observable facts
2. Progress to pattern recognition
3. Move to strategic implications
4. End with predictive/prescriptive insights

Make questions specific to sports tactical analysis. Return as numbered list."""

        try:
            response = self.client.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 768,
                    "temperature": 0.6,
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            questions = []
            for idx, line in enumerate(content.strip().split("\n")):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    clean_q = line.lstrip("0123456789.-) ").strip()
                    if clean_q:
                        questions.append(
                            GeneratedQuestion(
                                question_id=f"deepdive_{idx:04d}",
                                question=clean_q,
                                category="deep_dive",
                                priority=idx + 1,
                                context_required="topic_context",
                                expected_detail_level="expert",
                            )
                        )

            return questions[:num_questions]

        except httpx.HTTPError as e:
            logger.error("LLM API error generating deep dive questions: %s", e)
            return []

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
