# Created by Metrum AI for Solidigm

"""
American Football Analytics Deep Agent - Main agent creation and analysis functions.
"""

import logging
import os
import time
from typing import Optional, Literal

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from src.agents.config import get_config, AgentConfig
from src.agents.telemetry import trace_agent, init_telemetry
from .tools import ALL_TOOLS, VIDEO_TOOLS, VLM_TOOLS
from .prompts import AMERICAN_FOOTBALL_COACHING_SYSTEM_PROMPT, ANALYSIS_FOCUS

logger = logging.getLogger(__name__)

# Initialize telemetry on module load
init_telemetry()


def create_american_football_analytics_agent(
    config: Optional[AgentConfig] = None,
    thread_id: str = "coaching_session",
    enable_research: bool = True,
):
    """
    Create an American Football analytics deep agent for coaching analysis.

    Args:
        config: Agent configuration
        thread_id: Session ID for conversation memory
        enable_research: Whether to enable internet research tools

    Returns:
        Tuple of (configured American Football analytics agent, thread_id)
    """
    config = config or get_config()

    model = ChatOpenAI(
        model=config.llm.served_model_name,
        base_url=config.llm.api_base_url,
        api_key=os.getenv("OPENAI_API_KEY") or "not-needed",  # pragma: allowlist secret
        temperature=0.3,
        max_tokens=config.llm.max_tokens,
    )

    checkpointer = MemorySaver()
    tools = ALL_TOOLS if enable_research else VIDEO_TOOLS + VLM_TOOLS

    agent = create_react_agent(
        model=model,
        tools=tools,
        state_modifier=AMERICAN_FOOTBALL_COACHING_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent, thread_id


def analyze_game_film(
    video_path: str,
    query: str,
    analysis_type: Literal["general", "offense", "defense", "red_zone", "matchups"] = "general",
    thread_id: str = "coaching_session",
) -> dict:
    """
    Analyze American Football game film with specific coaching focus.

    Args:
        video_path: Path to the American Football game video
        query: Coach's specific question or analysis request
        analysis_type: Type of analysis focus
        thread_id: Session ID for conversation continuity

    Returns:
        Comprehensive coaching analysis
    """
    start_time = time.time()

    with trace_agent("american_football_game_film", video_path, query, analysis_type) as span:
        agent, tid = create_american_football_analytics_agent(thread_id=thread_id)

        focus = ANALYSIS_FOCUS.get(analysis_type, ANALYSIS_FOCUS["general"])

        user_message = f"""COACHING ANALYSIS REQUEST

Game Film: {video_path}
Analysis Type: {analysis_type.upper()}
Focus: {focus}

Coach's Question: {query}

Instructions:
1. Extract and analyze key frames from the game film
2. Identify formations, personnel, and matchups
3. Research relevant statistics and tendencies for context
4. Provide specific coaching recommendations
5. Clean up temporary files when done

Deliver a professional coaching report with actionable insights."""

        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config={"configurable": {"thread_id": tid}},
        )

        duration = time.time() - start_time
        span.set_attribute("agent.total_duration", duration)

        return {
            "success": True,
            "video_path": video_path,
            "query": query,
            "analysis_type": analysis_type,
            "duration_seconds": round(duration, 2),
            "coaching_report": (result["messages"][-1].content if result.get("messages") else str(result)),
        }


def analyze_opponent_tendencies(
    video_path: str,
    opponent_team: str,
    situation: str = "all situations",
    thread_id: str = "scouting_session",
) -> dict:
    """
    Analyze opponent tendencies for game planning.

    Args:
        video_path: Path to opponent game film
        opponent_team: Name of the opponent team
        situation: Specific game situation to focus on
        thread_id: Session ID

    Returns:
        Opponent scouting report
    """
    agent, tid = create_american_football_analytics_agent(thread_id=thread_id)

    user_message = f"""OPPONENT SCOUTING REPORT

Game Film: {video_path}
Opponent: {opponent_team}
Situation Focus: {situation}

Generate a comprehensive scouting report:
1. Analyze their formations and personnel packages
2. Identify play-calling tendencies and patterns
3. Research their statistical tendencies
4. Find exploitable weaknesses
5. Recommend counter strategies

Provide a detailed scouting report suitable for game planning."""

    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"configurable": {"thread_id": tid}},
    )

    return {
        "success": True,
        "opponent": opponent_team,
        "situation": situation,
        "scouting_report": (result["messages"][-1].content if result.get("messages") else str(result)),
    }


def analyze_player_performance(
    video_path: str,
    player_focus: str,
    thread_id: str = "player_eval",
) -> dict:
    """
    Analyze a specific player's performance from game film.

    Args:
        video_path: Path to game film
        player_focus: Player name or position to focus on
        thread_id: Session ID

    Returns:
        Player performance evaluation
    """
    agent, tid = create_american_football_analytics_agent(thread_id=thread_id)

    user_message = f"""PLAYER PERFORMANCE EVALUATION

Game Film: {video_path}
Player Focus: {player_focus}

Evaluate this player's performance:
1. Analyze their technique and execution
2. Identify strengths and areas for improvement
3. Look up their recent statistics for context
4. Note key plays (both positive and negative)
5. Provide specific coaching points

Generate a player evaluation report suitable for position meetings."""

    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"configurable": {"thread_id": tid}},
    )

    return {
        "success": True,
        "player": player_focus,
        "evaluation": result["messages"][-1].content if result.get("messages") else str(result),
    }
