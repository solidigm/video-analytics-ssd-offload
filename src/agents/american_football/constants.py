# Created by Metrum AI for Solidigm

"""
American Football-specific constants and data structures.
"""

from dataclasses import dataclass


@dataclass
class PlayAnalysis:
    """Structure for a single play analysis."""

    play_number: int
    timestamp: float
    formation: str
    play_type: str
    players_identified: list
    key_matchups: list
    analysis: str


american_football_FORMATIONS = {
    "offense": [
        "I-Formation",
        "Shotgun",
        "Pistol",
        "Single Back",
        "Pro Set",
        "Spread",
        "Empty Backfield",
        "Wildcat",
        "Goal Line",
        "Jumbo",
    ],
    "defense": [
        "4-3",
        "3-4",
        "Nickel",
        "Dime",
        "Quarter",
        "46 Defense",
        "Cover 2",
        "Cover 3",
        "Cover 4",
        "Man-to-Man",
        "Zone Blitz",
    ],
}

american_football_PLAY_TYPES = [
    "Run - Inside Zone",
    "Run - Outside Zone",
    "Run - Power",
    "Run - Counter",
    "Run - Draw",
    "Run - Sweep",
    "Pass - Screen",
    "Pass - Slant",
    "Pass - Deep",
    "Pass - Play Action",
    "Pass - RPO",
    "Pass - Bootleg",
    "Special Teams - Punt",
    "Special Teams - Kickoff",
    "Special Teams - Field Goal",
]

PERSONNEL_PACKAGES = {
    "11": "1 RB, 1 TE, 3 WR",
    "12": "1 RB, 2 TE, 2 WR",
    "21": "2 RB, 1 TE, 2 WR",
    "22": "2 RB, 2 TE, 1 WR",
    "13": "1 RB, 3 TE, 1 WR",
}
