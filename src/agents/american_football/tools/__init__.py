# Created by Metrum AI for Solidigm

"""
American Football Analytics Tools - Organized by category.
"""

from .video import (
    extract_game_frames,
    get_game_video_info,
    cleanup_analysis_frames,
)

from .vlm import (
    analyze_play_formation,
    analyze_play_execution,
    identify_player_matchups,
    analyze_red_zone_play,
)

from .research import (
    search_american_football_stats,
    search_team_tendencies,
    search_player_info,
    search_play_concepts,
    get_american_football_rules_info,
)

# Tool collections for easy access
VIDEO_TOOLS = [
    extract_game_frames,
    get_game_video_info,
    cleanup_analysis_frames,
]

VLM_TOOLS = [
    analyze_play_formation,
    analyze_play_execution,
    identify_player_matchups,
    analyze_red_zone_play,
]

RESEARCH_TOOLS = [
    search_american_football_stats,
    search_team_tendencies,
    search_player_info,
    search_play_concepts,
    get_american_football_rules_info,
]

ALL_TOOLS = VIDEO_TOOLS + VLM_TOOLS + RESEARCH_TOOLS

__all__ = [
    # Video tools
    "extract_game_frames",
    "get_game_video_info",
    "cleanup_analysis_frames",
    # VLM tools
    "analyze_play_formation",
    "analyze_play_execution",
    "identify_player_matchups",
    "analyze_red_zone_play",
    # Research tools
    "search_american_football_stats",
    "search_team_tendencies",
    "search_player_info",
    "search_play_concepts",
    "get_american_football_rules_info",
    # Collections
    "VIDEO_TOOLS",
    "VLM_TOOLS",
    "RESEARCH_TOOLS",
    "ALL_TOOLS",
]
