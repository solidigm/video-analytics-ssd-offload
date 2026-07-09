# Created by Metrum AI for Solidigm

"""
American Football Sports Analytics Deep Agent Module.

A modular, production-ready agent for American Football game film analysis.
Uses Qwen3-VL-30B-A3B-Thinking for vision and MegaBeam-Mistral-7B-300k for reasoning.

Usage:
    from src.agents.american_football import analyze_game_film

    result = analyze_game_film(
        video_path="game.mp4",
        query="Analyze key formations",
        analysis_type="general"
    )
"""

from .agent import (
    create_american_football_analytics_agent,
    analyze_game_film,
    analyze_opponent_tendencies,
    analyze_player_performance,
)

from .constants import (
    PlayAnalysis,
    american_football_FORMATIONS,
    american_football_PLAY_TYPES,
    PERSONNEL_PACKAGES,
)

from .tools import (
    ALL_TOOLS,
    VIDEO_TOOLS,
    VLM_TOOLS,
    RESEARCH_TOOLS,
)

__all__ = [
    # Main analysis functions
    "create_american_football_analytics_agent",
    "analyze_game_film",
    "analyze_opponent_tendencies",
    "analyze_player_performance",
    # Constants
    "PlayAnalysis",
    "american_football_FORMATIONS",
    "american_football_PLAY_TYPES",
    "PERSONNEL_PACKAGES",
    # Tool collections
    "ALL_TOOLS",
    "VIDEO_TOOLS",
    "VLM_TOOLS",
    "RESEARCH_TOOLS",
]
