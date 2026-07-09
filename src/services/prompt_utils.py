# Created by Metrum AI for Solidigm

"""Shared helpers for context compaction and football analysis prompts."""

from __future__ import annotations


def compact_context_for_model(context_text: str, max_chars: int) -> tuple[str, bool]:
    """Compact oversized context while preserving all game sections when possible."""
    if not context_text or len(context_text) <= max_chars:
        return context_text, False

    marker = "=== GAME ANALYSIS:"
    if marker not in context_text:
        return context_text[:max_chars], True

    raw_sections = [section.strip() for section in context_text.split(marker) if section.strip()]
    if not raw_sections:
        return context_text[:max_chars], True

    sections = [f"{marker} {section}" for section in raw_sections]
    separator = "\n\n"
    separator_chars = len(separator) * max(len(sections) - 1, 0)
    usable_budget = max(max_chars - separator_chars, 0)
    per_section_budget = max(usable_budget // len(sections), 800)

    compacted_sections: list[str] = []
    for section in sections:
        if len(section) <= per_section_budget:
            compacted_sections.append(section)
            continue

        head_budget = max(int(per_section_budget * 0.8), 600)
        tail_budget = max(per_section_budget - head_budget - 32, 0)
        if tail_budget >= 120:
            compacted_sections.append(f"{section[:head_budget]}\n...[section truncated]...\n{section[-tail_budget:]}")
        else:
            compacted_sections.append(section[:per_section_budget])

    compacted = separator.join(compacted_sections)
    if len(compacted) > max_chars:
        compacted = compacted[:max_chars]
    return compacted, True


def build_football_analysis_prompt(context_text: str, query: str) -> str:
    """Build the standard long-context football analysis prompt."""
    return (
        "You are an expert American football analyst and coaching strategist. "
        "Your role is to provide detailed, data-driven analysis of game film, "
        "player performance, formations, and tactical trends.\n\n"
        "INSTRUCTIONS:\n"
        "1. You MUST answer the question using the game context provided below. "
        "The context contains detailed play-by-play analysis from real game footage.\n"
        "2. Extract and reference specific plays, player names, formations, scores, "
        "time ranges, and tactical details directly from the context.\n"
        "3. DO NOT use any information that is not present in the context below.\n"
        "4. Always provide a substantive answer from available evidence in the context. "
        "If one part has limited data, briefly say that and continue with what is available.\n"
        "5. Structure your response clearly with evidence-backed points.\n"
        "6. Do not assume the league, conference, or level of play — use only the team "
        "names, player names, and details present in the context.\n\n"
        f"--- BEGIN GAME CONTEXT ---\n{context_text}\n--- END GAME CONTEXT ---\n\n"
        "Using the game context above, provide a thorough analysis for the following:\n"
        f"{query}"
    )
