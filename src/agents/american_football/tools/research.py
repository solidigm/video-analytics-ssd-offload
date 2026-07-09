# Created by Metrum AI for Solidigm

"""
Internet research tools for American Football statistics and information.
Uses DuckDuckGo for web searches.
"""

from typing import Literal

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None


def _duckduckgo_text_search(search_query: str, max_results: int = 5) -> list[dict]:
    """Run a DuckDuckGo text search with graceful handling when dependency is missing."""
    if DDGS is None:
        raise RuntimeError("duckduckgo_search package is not installed")
    with DDGS() as ddgs:
        return list(ddgs.text(search_query, max_results=max_results))


def search_american_football_stats(
    query: str,
    stat_type: Literal["player", "team", "game", "historical"] = "player",
) -> dict:
    """
    Search for American Football statistics and player/team information.

    Args:
        query: Search query (player name, team, stat category)
        stat_type: Type of stats to search for

    Returns:
        American Football statistics and information from web sources
    """
    try:
        search_query = f"American Football {stat_type} stats {query} 2024 2025"
        results = _duckduckgo_text_search(search_query, max_results=5)

        return {
            "success": True,
            "query": query,
            "stat_type": stat_type,
            "results": results,
        }
    except (RuntimeError, OSError, ValueError, TypeError) as e:
        return {"success": False, "query": query, "error": str(e)}


def search_team_tendencies(
    team_name: str,
    situation: str = "general",
) -> dict:
    """
    Search for team tendencies and play-calling patterns.

    Args:
        team_name: American Football team name (e.g., "Kansas City Chiefs")
        situation: Specific situation (e.g., "red zone", "3rd down")

    Returns:
        Team tendency analysis and scouting information
    """
    try:
        search_query = f"American Football {team_name} {situation} tendencies play calling 2024"
        results = _duckduckgo_text_search(search_query, max_results=5)

        return {
            "success": True,
            "team": team_name,
            "situation": situation,
            "results": results,
        }
    except (RuntimeError, OSError, ValueError, TypeError) as e:
        return {"success": False, "team": team_name, "error": str(e)}


def search_player_info(
    player_name: str,
    info_type: Literal["stats", "injury", "history", "scouting"] = "stats",
) -> dict:
    """
    Search for detailed player information.

    Args:
        player_name: American Football player name
        info_type: Type of information to search

    Returns:
        Player information and statistics
    """
    try:
        search_query = f"American Football player {player_name} {info_type} 2024 2025"
        results = _duckduckgo_text_search(search_query, max_results=5)

        return {
            "success": True,
            "player": player_name,
            "info_type": info_type,
            "results": results,
        }
    except (RuntimeError, OSError, ValueError, TypeError) as e:
        return {"success": False, "player": player_name, "error": str(e)}


def search_play_concepts(concept: str) -> dict:
    """
    Search for information about specific play concepts and schemes.

    Args:
        concept: Play concept name (e.g., "RPO", "Cover 3", "Power run")

    Returns:
        Educational information about the play concept
    """
    try:
        search_query = f"American Football football {concept} play concept scheme explained"
        results = _duckduckgo_text_search(search_query, max_results=5)

        return {
            "success": True,
            "concept": concept,
            "results": results,
        }
    except (RuntimeError, OSError, ValueError, TypeError) as e:
        return {"success": False, "concept": concept, "error": str(e)}


def get_american_football_rules_info(rule_topic: str) -> dict:
    """
    Search for American Football rules and officiating information.

    Args:
        rule_topic: Rule topic (e.g., "pass interference")

    Returns:
        Official American Football rule information
    """
    try:
        search_query = f"American Football official rules {rule_topic} rulebook"
        results = _duckduckgo_text_search(search_query, max_results=5)

        return {
            "success": True,
            "rule_topic": rule_topic,
            "results": results,
        }
    except (RuntimeError, OSError, ValueError, TypeError) as e:
        return {"success": False, "rule_topic": rule_topic, "error": str(e)}
