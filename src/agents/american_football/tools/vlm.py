# Created by Metrum AI for Solidigm

"""
VLM-based analysis tools for American Football game footage.
Uses Qwen3-VL-30B-A3B-Thinking for visual analysis.
"""

import base64

import httpx

from src.agents.config import get_config
from src.agents.telemetry import trace_tool, trace_llm_call, record_tokens


def analyze_play_formation(frame_path: str) -> dict:
    """
    Analyze a single frame to identify offensive and defensive formations.

    Args:
        frame_path: Path to the frame image file

    Returns:
        Formation analysis including offensive/defensive setups
    """
    with trace_tool("analyze_play_formation", frame_path=frame_path):
        config = get_config()
        api_url = config.vlm.api_base_url.rstrip("/")

        with open(frame_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        analysis_prompt = """Briefly analyze this American Football frame (150 words max):
- Offensive formation (shotgun/I-form/spread)
- Defensive look (4-3/3-4/nickel)
- Key matchup or pre-snap read
Keep it short and tactical."""

        payload = {
            "model": config.vlm.served_model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                        },
                        {"type": "text", "text": analysis_prompt},
                    ],
                }
            ],
            "max_tokens": config.vlm.max_tokens,
            "temperature": 0.2,
        }

        try:
            with trace_llm_call(config.vlm.served_model_name, "vlm") as llm_span:
                with httpx.Client(timeout=config.vlm.timeout) as client:
                    response = client.post(f"{api_url}/chat/completions", json=payload)
                    response.raise_for_status()
                    result = response.json()

                    # Record token usage if available
                    if "usage" in result:
                        tokens = result["usage"].get("total_tokens", 0)
                        record_tokens(tokens, config.vlm.served_model_name)
                        llm_span.set_attribute("llm.tokens", tokens)

                    return {
                        "success": True,
                        "frame_path": frame_path,
                        "formation_analysis": result["choices"][0]["message"]["content"],
                    }
        except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError) as e:
            return {"success": False, "frame_path": frame_path, "error": str(e)}


def analyze_play_execution(frame_path: str, play_context: str = "") -> dict:
    """
    Analyze a frame showing play execution - routes, blocking, ball carrier.

    Args:
        frame_path: Path to the frame image
        play_context: Optional context (e.g., "3rd and 7, shotgun formation")

    Returns:
        Detailed play execution analysis
    """
    config = get_config()
    api_url = config.vlm.api_base_url.rstrip("/")

    with open(frame_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    context_str = f"\nPlay Context: {play_context}" if play_context else ""

    analysis_prompt = f"""Briefly analyze this play execution (150 words max):{context_str}
- Play type (run/pass/special)
- Key execution notes
- One coaching point
Be concise and tactical."""

    payload = {
        "model": config.vlm.served_model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    },
                    {"type": "text", "text": analysis_prompt},
                ],
            }
        ],
        "max_tokens": config.vlm.max_tokens,
        "temperature": 0.2,
    }

    try:
        with httpx.Client(timeout=config.vlm.timeout) as client:
            response = client.post(f"{api_url}/chat/completions", json=payload)
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "frame_path": frame_path,
                "play_analysis": result["choices"][0]["message"]["content"],
            }
    except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError) as e:
        return {"success": False, "frame_path": frame_path, "error": str(e)}


def identify_player_matchups(frame_path: str) -> dict:
    """
    Identify key player matchups and personnel groupings from a game frame.

    Args:
        frame_path: Path to the frame image

    Returns:
        Player matchup analysis
    """
    config = get_config()
    api_url = config.vlm.api_base_url.rstrip("/")

    with open(frame_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    analysis_prompt = """Briefly analyze matchups (100 words max):
- Personnel grouping (11/12/21)
- Key mismatch to exploit
- One tactical recommendation
Be concise."""

    payload = {
        "model": config.vlm.served_model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    },
                    {"type": "text", "text": analysis_prompt},
                ],
            }
        ],
        "max_tokens": config.vlm.max_tokens,
        "temperature": 0.2,
    }

    try:
        with httpx.Client(timeout=config.vlm.timeout) as client:
            response = client.post(f"{api_url}/chat/completions", json=payload)
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "frame_path": frame_path,
                "matchup_analysis": result["choices"][0]["message"]["content"],
            }
    except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError) as e:
        return {"success": False, "frame_path": frame_path, "error": str(e)}


def analyze_red_zone_play(frame_path: str, down_and_distance: str = "") -> dict:
    """
    Specialized analysis for red zone plays (inside the 20 yard line).

    Args:
        frame_path: Path to the frame image
        down_and_distance: e.g., "1st and Goal from the 5"

    Returns:
        Red zone specific tactical analysis
    """
    config = get_config()
    api_url = config.vlm.api_base_url.rstrip("/")

    with open(frame_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    context = f"\nSituation: {down_and_distance}" if down_and_distance else ""

    analysis_prompt = f"""Briefly analyze red zone play (100 words max):{context}
- Scoring opportunity
- Key defensive adjustment
- One play recommendation
Be concise and tactical."""

    payload = {
        "model": config.vlm.served_model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    },
                    {"type": "text", "text": analysis_prompt},
                ],
            }
        ],
        "max_tokens": config.vlm.max_tokens,
        "temperature": 0.2,
    }

    try:
        with httpx.Client(timeout=config.vlm.timeout) as client:
            response = client.post(f"{api_url}/chat/completions", json=payload)
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "frame_path": frame_path,
                "red_zone_analysis": result["choices"][0]["message"]["content"],
            }
    except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError) as e:
        return {"success": False, "frame_path": frame_path, "error": str(e)}
